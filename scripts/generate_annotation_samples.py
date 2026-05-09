"""
generate_annotation_samples.py — 生成人工标注样本
从 PDF 中采样句子，附带系统初步 NER 结果，供人工校正。
输出到 annotations/samples.json

用法：python scripts/generate_annotation_samples.py --n 300
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extraction.pipeline import ExtractionPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="生成标注样本")
    parser.add_argument("--n",      type=int, default=300, help="采样句子数量")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output", default="annotations/samples.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    pipeline = ExtractionPipeline(config_path=args.config)
    samples  = pipeline.sample_sentences(n=args.n)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    logger.info("已生成 %d 条标注样本 → %s", len(samples), args.output)
    logger.info(
        "\n标注说明：\n"
        "  1. 打开 %s\n"
        "  2. 检查每条 'entities' 列表，修正 type/start/end\n"
        "  3. 在 'relations' 列表中填写关系（参考下方格式）\n"
        "  4. 关系格式：{\"id\": \"R0\", \"subj\": \"E0\", \"pred\": \"HAS_SYMPTOM\", \"obj\": \"E1\"}\n"
        "  5. 完成后运行 python scripts/evaluate.py 进行评估",
        args.output,
    )


if __name__ == "__main__":
    main()
