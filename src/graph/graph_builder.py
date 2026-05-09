"""
graph_builder.py — 图谱构建器
接收抽取管线产出的节点/三元组列表，批量写入 Neo4j。
解耦抽取逻辑与存储逻辑，可独立替换任一侧。
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from src.graph.neo4j_connector import Neo4jConnector
from src.graph.schema import NodeLabel, Triple

logger = logging.getLogger(__name__)

# 批次大小：避免单次事务过大
BATCH_SIZE = 200


class GraphBuilder:
    """
    图谱构建器：
      1. 调用 build_constraints() 初始化约束
      2. 调用 ingest_nodes() 批量写入节点
      3. 调用 ingest_triples() 批量写入关系
      4. 调用 ingest_all() 一次性完成全流程
    """

    def __init__(self, connector: Neo4jConnector):
        self._db = connector

    # ── 初始化 ────────────────────────────────────────────────────
    def build_constraints(self):
        self._db.create_constraints()

    # ── 节点写入 ──────────────────────────────────────────────────
    def ingest_nodes(self, label: str, nodes: List[Dict[str, Any]]):
        """
        批量写入单种标签节点。
        nodes: 每条为 dataclass.to_dict() 产出的字典。
        """
        if not nodes:
            return
        # 去重（按 name 去重，保留属性最多的那条）
        deduped: Dict[str, Dict] = {}
        for n in nodes:
            name = n.get("name", "").strip()
            if not name:
                continue
            if name not in deduped or len(n) > len(deduped[name]):
                deduped[name] = n

        unique_nodes = list(deduped.values())
        for i in range(0, len(unique_nodes), BATCH_SIZE):
            batch = unique_nodes[i: i + BATCH_SIZE]
            self._db.batch_merge_nodes(label, batch)
            logger.info("[%s] 写入节点 %d/%d", label, min(i + BATCH_SIZE, len(unique_nodes)), len(unique_nodes))

    def ingest_nodes_from_triples(self, triples: List[Triple]):
        """从三元组列表中自动提取并写入所有节点（携带实体属性）。"""
        node_buckets: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        for t in triples:
            sl, sn = t.subj_label.value, t.subj_name.strip()
            ol, on = t.obj_label.value,  t.obj_name.strip()
            if sn:
                base = {"name": sn, "source_doc": t.source_doc}
                if t.source_sent:
                    base["description"] = t.source_sent[:200]
                # 合并实体属性（如 value/unit/fault_code/component_no）
                base.update({k: v for k, v in t.subj_props.items() if v})
                existing = node_buckets[sl].get(sn, {})
                # 保留属性最多的版本；新版本属性更多则覆盖
                if len(base) >= len(existing):
                    node_buckets[sl][sn] = base
            if on:
                base = {"name": on, "source_doc": t.source_doc}
                if t.source_sent:
                    base["description"] = t.source_sent[:200]
                base.update({k: v for k, v in t.obj_props.items() if v})
                existing = node_buckets[ol].get(on, {})
                if len(base) >= len(existing):
                    node_buckets[ol][on] = base

        for label, nodes_map in node_buckets.items():
            self.ingest_nodes(label, list(nodes_map.values()))

    # ── 关系写入 ──────────────────────────────────────────────────
    def ingest_triples(self, triples: List[Triple]):
        """批量写入三元组（先确保节点存在）。"""
        if not triples:
            return
        # 先写节点
        self.ingest_nodes_from_triples(triples)
        # 去重三元组
        seen = set()
        unique: List[Dict] = []
        for t in triples:
            key = (t.subj_label.value, t.subj_name, t.relation.value, t.obj_label.value, t.obj_name)
            if key not in seen:
                seen.add(key)
                unique.append(t.to_dict())

        for i in range(0, len(unique), BATCH_SIZE):
            batch = unique[i: i + BATCH_SIZE]
            self._db.batch_merge_relations(batch)
            logger.info("写入关系 %d/%d", min(i + BATCH_SIZE, len(unique)), len(unique))

    # ── 全流程 ────────────────────────────────────────────────────
    def ingest_all(
        self,
        triples: List[Triple],
        extra_nodes: Optional[Dict[str, List[Dict]]] = None,
    ):
        """
        一次性完成：约束初始化 → 额外节点写入 → 三元组写入。
        extra_nodes: {label: [node_dict, ...]} 用于传入带完整属性的节点。
        """
        self.build_constraints()
        if extra_nodes:
            for label, nodes in extra_nodes.items():
                self.ingest_nodes(label, nodes)
        self.ingest_triples(triples)
        logger.info(
            "图谱构建完成：共写入 %d 条三元组（去重后）",
            len(set((t.subj_name, t.relation.value, t.obj_name) for t in triples)),
        )
