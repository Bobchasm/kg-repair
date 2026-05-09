"""
neo4j_connector.py — Neo4j 数据库连接与操作封装
使用连接池，支持事务批量写入，统一异常处理。
"""
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

import yaml
from neo4j import GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable, AuthError, TransientError

logger = logging.getLogger(__name__)


def _load_config(config_path: str = "config.yaml") -> Dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Neo4jConnector:
    """
    Neo4j 连接器，封装驱动生命周期和常用 Cypher 操作。
    使用单例模式：整个应用共享一个实例。
    """

    _instance: Optional["Neo4jConnector"] = None

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        self._uri = uri
        self._username = username
        self._password = password
        self._database = database
        self._driver = None
        self._connect()

    # ── 单例工厂 ──────────────────────────────────────────────────
    @classmethod
    def from_config(cls, config_path: str = "config.yaml") -> "Neo4jConnector":
        if cls._instance is None:
            cfg = _load_config(config_path)["neo4j"]
            cls._instance = cls(
                uri=cfg["uri"],
                username=cfg["username"],
                password=cfg["password"],
                database=cfg.get("database", "neo4j"),
            )
        return cls._instance

    # ── 连接管理 ──────────────────────────────────────────────────
    def _connect(self):
        try:
            if self._driver:
                try:
                    self._driver.close()
                except Exception:
                    pass
            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
                max_connection_pool_size=10,
                connection_timeout=30,
                max_transaction_retry_time=30,
            )
            self._driver.verify_connectivity()
            logger.info("Neo4j 连接成功：%s", self._uri)
        except (ServiceUnavailable, AuthError) as e:
            logger.error("Neo4j 连接失败：%s", e)
            raise

    def _reconnect(self):
        """断线重连，最多重试 3 次。"""
        for attempt in range(1, 4):
            try:
                logger.warning("正在重连 Neo4j（第 %d 次）...", attempt)
                time.sleep(2 * attempt)
                self._connect()
                return
            except Exception as e:
                logger.error("重连失败：%s", e)
        raise ServiceUnavailable("Neo4j 多次重连均失败，请检查网络")

    def close(self):
        if self._driver:
            self._driver.close()
            logger.info("Neo4j 连接已关闭")

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """获取 Session，若连接已断则自动重连。"""
        try:
            with self._driver.session(database=self._database) as s:
                yield s
        except ServiceUnavailable:
            self._reconnect()
            with self._driver.session(database=self._database) as s:
                yield s

    def _run_with_retry(
        self, cypher: str, max_retries: int = 3, **params
    ):
        """执行单条 Cypher，失败时自动重连重试。"""
        for attempt in range(1, max_retries + 1):
            try:
                with self._driver.session(database=self._database) as s:
                    s.run(cypher, **params).consume()
                return
            except (ServiceUnavailable, OSError) as e:
                logger.warning("Cypher 执行失败（第 %d 次）：%s", attempt, e)
                if attempt == max_retries:
                    raise
                self._reconnect()

    # ── 索引/约束初始化 ───────────────────────────────────────────
    def create_constraints(self):
        """在首次运行时创建唯一约束与索引，保证幂等性。"""
        labels = [
            "Vehicle", "Component", "Fault", "Symptom",
            "RepairStep", "Tool", "System", "Parameter",
        ]
        with self.session() as s:
            for label in labels:
                # 唯一约束（name 作为业务主键）
                s.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE"
                )
                # 全文索引（用于搜索）
                try:
                    s.run(
                        f"CREATE FULLTEXT INDEX {label.lower()}_ft IF NOT EXISTS "
                        f"FOR (n:{label}) ON EACH [n.name, n.description]"
                    )
                except Exception:
                    pass  # CE 版不支持全文索引时静默跳过
        logger.info("约束和索引初始化完成")

    # ── 节点操作 ──────────────────────────────────────────────────
    def merge_node(self, label: str, props: Dict[str, Any]) -> Dict:
        """MERGE 节点（name 作为主键），存在则更新属性。"""
        cypher = (
            f"MERGE (n:{label} {{name: $name}}) "
            f"SET n += $props "
            f"RETURN id(n) AS neo4j_id, n"
        )
        with self.session() as s:
            result = s.run(cypher, name=props["name"], props=props)
            record = result.single()
            return dict(record["n"]) if record else {}

    def batch_merge_nodes(self, label: str, nodes: List[Dict[str, Any]]):
        """批量 MERGE 节点，利用 UNWIND 提升性能。"""
        cypher = (
            f"UNWIND $nodes AS props "
            f"MERGE (n:{label} {{name: props.name}}) "
            f"SET n += props"
        )
        with self.session() as s:
            s.run(cypher, nodes=nodes)
        logger.debug("批量写入 %d 个 %s 节点", len(nodes), label)

    # ── 关系操作 ──────────────────────────────────────────────────
    def merge_relation(
        self,
        subj_label: str,
        subj_name: str,
        rel_type: str,
        obj_label: str,
        obj_name: str,
        rel_props: Optional[Dict] = None,
    ):
        """MERGE 一条关系，不重复创建。"""
        rel_props = rel_props or {}
        cypher = (
            f"MATCH (a:{subj_label} {{name: $sn}}), (b:{obj_label} {{name: $on}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            f"SET r += $rp"
        )
        with self.session() as s:
            s.run(cypher, sn=subj_name, on=obj_name, rp=rel_props)

    def batch_merge_relations(self, triples: List[Dict[str, Any]]):
        """
        批量 MERGE 关系，每个关系类型组独立 session + 重试，
        避免长时间占用单连接导致超时断开。
        """
        from collections import defaultdict
        groups: Dict[str, list] = defaultdict(list)
        for t in triples:
            key = f"{t['subj_label']}|{t['relation']}|{t['obj_label']}"
            groups[key].append(t)

        total = 0
        for key, batch in groups.items():
            subj_label, rel_type, obj_label = key.split("|")
            cypher = (
                f"UNWIND $batch AS t "
                f"MATCH (a:{subj_label} {{name: t.subj_name}}), "
                f"      (b:{obj_label}  {{name: t.obj_name}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r.confidence  = t.confidence, "
                f"    r.source_doc  = t.source_doc, "
                f"    r.source_sent = t.source_sent"
            )
            # 每个分组独立 session，超时后重试
            for attempt in range(1, 4):
                try:
                    with self._driver.session(database=self._database) as s:
                        s.run(cypher, batch=batch).consume()
                    total += len(batch)
                    break
                except (ServiceUnavailable, OSError) as e:
                    logger.warning(
                        "写入关系 %s 失败（第 %d 次）：%s", rel_type, attempt, e
                    )
                    if attempt == 3:
                        logger.error("放弃写入关系类型 %s，共丢失 %d 条", rel_type, len(batch))
                    else:
                        self._reconnect()
        logger.debug("批量写入 %d 条关系", total)

    # ── 查询操作 ──────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        """返回图谱统计信息。"""
        with self.session() as s:
            node_cnt = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
            rel_cnt  = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
            labels   = s.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt "
                "ORDER BY cnt DESC"
            ).data()
            rels     = s.run(
                "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt "
                "ORDER BY cnt DESC"
            ).data()
        return {
            "node_count":  node_cnt,
            "rel_count":   rel_cnt,
            "node_labels": labels,
            "rel_types":   rels,
        }

    def get_subgraph(
        self,
        node_name: str,
        hops: int = 2,
        max_nodes: int = 300,
    ) -> Dict[str, List]:
        """以指定节点为中心返回 N 跳子图。"""
        cypher = (
            f"MATCH path = (center)-[*1..{hops}]-(neighbor) "
            f"WHERE center.name = $name "
            f"WITH nodes(path) AS ns, relationships(path) AS rs "
            f"UNWIND ns AS n UNWIND rs AS r "
            f"RETURN DISTINCT n, r LIMIT {max_nodes * 4}"
        )
        nodes_map, edges = {}, []
        with self.session() as s:
            result = s.run(cypher, name=node_name)
            for record in result:
                n = record["n"]
                e = record["r"]
                nid = str(n.element_id)
                if nid not in nodes_map:
                    nodes_map[nid] = {
                        "id":     nid,
                        "name":   n.get("name", ""),
                        "label":  list(n.labels)[0] if n.labels else "Unknown",
                        "props":  dict(n),
                    }
                edges.append({
                    "id":     str(e.element_id),
                    "source": str(e.start_node.element_id),
                    "target": str(e.end_node.element_id),
                    "type":   e.type,
                    "props":  dict(e),
                })
        return {"nodes": list(nodes_map.values())[:max_nodes], "edges": edges}

    def search_nodes(self, keyword: str, limit: int = 30) -> List[Dict]:
        """按 name 模糊搜索节点。"""
        cypher = (
            "MATCH (n) WHERE n.name CONTAINS $kw "
            "RETURN id(n) AS neo4j_id, n.name AS name, labels(n)[0] AS label, properties(n) AS props "
            "LIMIT $lim"
        )
        with self.session() as s:
            return s.run(cypher, kw=keyword, lim=limit).data()

    def get_shortest_path(self, from_name: str, to_name: str) -> List[Dict]:
        """返回两个节点之间的最短路径（节点+关系列表）。"""
        cypher = (
            "MATCH (a {name: $a}), (b {name: $b}) "
            "MATCH path = shortestPath((a)-[*..10]-(b)) "
            "RETURN nodes(path) AS ns, relationships(path) AS rs"
        )
        with self.session() as s:
            record = s.run(cypher, a=from_name, b=to_name).single()
        if not record:
            return []
        result = []
        ns = record["ns"]
        rs = record["rs"]
        for i, n in enumerate(ns):
            result.append({
                "type": "node",
                "id":    str(n.element_id),
                "name":  n.get("name", ""),
                "label": list(n.labels)[0] if n.labels else "Unknown",
                "props": dict(n),
            })
            if i < len(rs):
                r = rs[i]
                result.append({
                    "type":   "relation",
                    "id":     str(r.element_id),
                    "rel":    r.type,
                    "source": str(r.start_node.element_id),
                    "target": str(r.end_node.element_id),
                })
        return result

    def get_all_nodes_paginated(
        self, label: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Dict]:
        label_clause = f":{label}" if label else ""
        cypher = (
            f"MATCH (n{label_clause}) "
            f"RETURN id(n) AS neo4j_id, n.name AS name, labels(n)[0] AS label, properties(n) AS props "
            f"SKIP $skip LIMIT $lim"
        )
        with self.session() as s:
            return s.run(cypher, skip=skip, lim=limit).data()

    def get_overview_graph(self, limit: int = 300) -> Dict[str, List]:
        """获取图谱概览（随机采样节点及其关系）。"""
        cypher = (
            "MATCH (n)-[r]->(m) "
            "WITH n, r, m ORDER BY rand() "
            "RETURN n, r, m LIMIT $lim"
        )
        nodes_map, edges = {}, []
        with self.session() as s:
            for rec in s.run(cypher, lim=limit):
                for node in [rec["n"], rec["m"]]:
                    nid = str(node.element_id)
                    if nid not in nodes_map:
                        nodes_map[nid] = {
                            "id":    nid,
                            "name":  node.get("name", ""),
                            "label": list(node.labels)[0] if node.labels else "Unknown",
                            "props": dict(node),
                        }
                e = rec["r"]
                edges.append({
                    "id":     str(e.element_id),
                    "source": str(e.start_node.element_id),
                    "target": str(e.end_node.element_id),
                    "type":   e.type,
                    "props":  dict(e),
                })
        return {"nodes": list(nodes_map.values()), "edges": edges}
