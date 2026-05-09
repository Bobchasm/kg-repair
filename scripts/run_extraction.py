"""
run_extraction.py — 一键运行完整知识抚取并写入 Neo4j
用法：python scripts/run_extraction.py [--config config.yaml] [--max-pages 50]
"""
import argparse
import json
import logging
import sys
import os
from collections import defaultdict
from datetime import datetime

# 确保项目根目录在 PATH 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extraction.pipeline import ExtractionPipeline
from src.graph.neo4j_connector import Neo4jConnector
from src.graph.graph_builder import GraphBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("extraction.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="汽车维修知识图谱 — 自动抽取脚本")
    parser.add_argument("--config",    default="config.yaml", help="配置文件路径")
    parser.add_argument("--max-pages", type=int, default=-1,  help="每个PDF最大处理页数（调试用）")
    parser.add_argument("--dry-run",   action="store_true",   help="仅抽取，不写入 Neo4j")
    return parser.parse_args()


def _save_output(result, output_dir: str):
    """\u5c06\u629a\u53d6\u7ed3\u679c\u4fdd\u5b58\u5230 output/ \u76ee\u5f55\u4e0b\uff08entities.json / triples.json / summary.json\uff09\u3002"""
    os.makedirs(output_dir, exist_ok=True)

    # \u4ece\u4e09\u5143\u7ec4\u62c6\u89e3\u53bb\u91cd\u5b9e\u4f53
    entity_map: dict = {}
    for t in result.triples:
        sk = (t.subj_label.value, t.subj_name)
        ok = (t.obj_label.value,  t.obj_name)
        if sk not in entity_map:
            entity_map[sk] = {"label": t.subj_label.value, "name": t.subj_name, **t.subj_props}
        if ok not in entity_map:
            entity_map[ok] = {"label": t.obj_label.value,  "name": t.obj_name,  **t.obj_props}

    entities_list = list(entity_map.values())
    triples_list  = [t.to_dict() for t in result.triples]

    entity_type_dist: dict = defaultdict(int)
    for e in entities_list:
        entity_type_dist[e["label"]] += 1
    rel_type_dist: dict = defaultdict(int)
    for t in result.triples:
        rel_type_dist[t.relation.value] += 1

    summary = {
        "generated_at":              datetime.now().isoformat(),
        "chunks_total":              result.chunks_total,
        "sentences_total":           result.sentences_total,
        "entity_count":              len(entities_list),
        "triple_count":              len(triples_list),
        "entity_type_distribution":  dict(entity_type_dist),
        "relation_type_distribution": dict(rel_type_dist),
        "errors":                    result.errors[:20],
    }

    with open(os.path.join(output_dir, "entities.json"), "w", encoding="utf-8") as f:
        json.dump(entities_list, f, ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "triples.json"), "w", encoding="utf-8") as f:
        json.dump(triples_list, f, ensure_ascii=False, indent=2)
    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info(
        "\u8f93\u51fa\u5b8c\u6210\uff1aentities.json (%d\u6761) | triples.json (%d\u6761) | summary.json \u2192 %s",
        len(entities_list), len(triples_list), output_dir,
    )


def main():
    args = parse_args()

    # 临时覆盖 max_pages（调试时使用）
    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if args.max_pages > 0:
        cfg["extraction"]["max_pages"] = args.max_pages
        # 写回临时配置
        tmp_cfg = "config_tmp.yaml"
        with open(tmp_cfg, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True)
        config_path = tmp_cfg
    else:
        config_path = args.config

    # ── Step 1: 抽取 ──────────────────────────────────────────────
    logger.info(">>> Step 1: 启动知识抽取管线")
    pipeline = ExtractionPipeline(config_path=config_path)
    result = pipeline.run()

    logger.info(
        "抽取结果：文本块=%d | 句子=%d | 实体=%d | 三元组=%d | 错误=%d",
        result.chunks_total,
        result.sentences_total,
        result.entity_count,
        result.triple_count,
        len(result.errors),
    )

    if args.dry_run:
        logger.info("dry-run 模式，跳过写入 Neo4j")
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        _save_output(result, output_dir)
        return

    if result.triple_count == 0:
        logger.warning("未抽取到任何三元组，检查 PDF 路径或分词配置")
        return

    # ── Step 2: 输出文件 ────────────────────────────────────────────
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    _save_output(result, output_dir)

    # ── Step 3: 写入 Neo4j ─────────────────────────────────────────
    logger.info(">>> Step 3: 写入 Neo4j")
    connector = Neo4jConnector.from_config(config_path)
    builder   = GraphBuilder(connector)
    builder.ingest_all(result.triples)

    # ── Step 4: 统计汇报 ───────────────────────────────────────────
    stats = connector.get_stats()
    logger.info(
        ">>> 图谱构建完成：节点=%d | 关系=%d",
        stats["node_count"], stats["rel_count"],
    )
    connector.close()

    # 清理临时配置
    if args.max_pages > 0 and os.path.exists("config_tmp.yaml"):
        os.remove("config_tmp.yaml")


if __name__ == "__main__":
    main()
