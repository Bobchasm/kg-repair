"""
evaluate.py — 对 NER 和 RE 进行定量评估
读取标注文件，用系统重新识别，与标注对比，计算 P/R/F1。

用法：python scripts/evaluate.py [--annotations annotations/] [--split 0.8]
"""
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation.annotator import AnnotationLoader
from src.evaluation.evaluator import NERMetrics, REMetrics, print_metrics_table
from src.extraction.ner_extractor import NERExtractor
from src.extraction.re_extractor  import REExtractor
from src.extraction.text_preprocessor import TextPreprocessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_pred_records(eval_records, ner, re_ext, preprocessor):
    """对标注句子运行系统，生成预测结果。"""
    pred_ner, pred_re = [], []
    for rec in eval_records:
        text = rec["text"]
        token_pairs = preprocessor.tokenize(text)
        words    = [w for w, _ in token_pairs]
        pos_tags = [p for _, p in token_pairs]

        # NER 预测
        ents = ner.recognize(text, words, pos_tags)
        pred_ner.append({
            "pred_entities": [(e.start, e.end, e.label) for e in ents]
        })

        # RE 预测
        triples = re_ext.extract(text, ents) if len(ents) >= 2 else []
        pred_re.append({
            "pred_relations": [(t.subj_name, t.relation.value, t.obj_name) for t in triples]
        })

    return pred_ner, pred_re


def main():
    parser = argparse.ArgumentParser(description="评估 NER 和 RE 性能")
    parser.add_argument("--annotations", default="annotations/", help="标注目录")
    parser.add_argument("--config",      default="config.yaml")
    parser.add_argument("--output-json", default="", help="评估结果输出 JSON（可选）")
    args = parser.parse_args()

    # 加载标注
    loader  = AnnotationLoader(annotation_dir=args.annotations)
    records = loader.load_all()
    valid, errors = loader.validate(records)

    if errors:
        logger.warning("标注格式警告：\n" + "\n".join(errors[:10]))
    if not valid:
        logger.error("无合法标注数据，退出")
        return

    logger.info("合法标注记录：%d 条", len(valid))
    eval_records = loader.to_eval_format(valid)

    # 初始化系统组件
    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ext_cfg = cfg.get("extraction", {})

    preprocessor = TextPreprocessor(domain_dict_path=ext_cfg.get("domain_dict_path", ""))
    ner          = NERExtractor(crf_model_path=ext_cfg.get("crf_model_path", "models/crf_ner.pkl"))
    re_ext       = REExtractor()

    # 生成预测
    logger.info("运行系统预测...")
    pred_ner, pred_re = build_pred_records(eval_records, ner, re_ext, preprocessor)

    # 计算指标
    ner_metrics = NERMetrics().evaluate(eval_records, pred_ner)
    re_metrics  = REMetrics().evaluate(eval_records, pred_re)

    print_metrics_table("NER 评估结果", ner_metrics)
    print_metrics_table("RE  评估结果", re_metrics)

    # 可选：保存 JSON
    if args.output_json:
        result = {"ner": ner_metrics, "re": re_metrics}
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info("评估结果已保存至：%s", args.output_json)


if __name__ == "__main__":
    main()
