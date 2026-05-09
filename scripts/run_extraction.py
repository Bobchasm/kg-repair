"""
run_extraction.py — 一键运行完整知识抽取并写入 Neo4j
用法：python scripts/run_extraction.py [--config config.yaml] [--max-pages 50]
"""
import argparse
import logging
import sys
import os

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
        return

    if result.triple_count == 0:
        logger.warning("未抽取到任何三元组，检查 PDF 路径或分词配置")
        return

    # ── Step 2: 写入 Neo4j ────────────────────────────────────────
    logger.info(">>> Step 2: 写入 Neo4j")
    connector = Neo4jConnector.from_config(config_path)
    builder   = GraphBuilder(connector)
    builder.ingest_all(result.triples)

    # ── Step 3: 统计汇报 ──────────────────────────────────────────
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
