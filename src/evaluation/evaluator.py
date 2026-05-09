"""
evaluator.py — NER 和 RE 评估模块
计算 Precision / Recall / F1，支持按实体类型分类报告。
"""
import logging
from collections import defaultdict
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

MetricDict = Dict[str, float]


def _prf(tp: int, fp: int, fn: int) -> MetricDict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall    = tp / (tp + fn) if tp + fn else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if precision + recall else 0.0)
    return {"precision": round(precision, 4),
            "recall":    round(recall, 4),
            "f1":        round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


class NERMetrics:
    """
    NER 评估：精确匹配（span + type 均一致才算正确）
    支持：整体指标 + 分类型指标
    """

    def evaluate(
        self,
        gold_records: List[Dict],
        pred_records: List[Dict],
    ) -> Dict[str, Any]:
        """
        Args:
            gold_records: [{text, gold_entities: [(start,end,type)]}]
            pred_records: [{text, pred_entities: [(start,end,type)]}]
        Returns:
            {overall: MetricDict, by_type: {type: MetricDict}}
        """
        overall_tp = overall_fp = overall_fn = 0
        by_type: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

        assert len(gold_records) == len(pred_records), "gold 与 pred 记录数不一致"

        for gold, pred in zip(gold_records, pred_records):
            gold_set = set(gold["gold_entities"])
            pred_set = set(pred.get("pred_entities", []))
            tp = gold_set & pred_set
            fp = pred_set - gold_set
            fn = gold_set - pred_set

            overall_tp += len(tp)
            overall_fp += len(fp)
            overall_fn += len(fn)

            for _, _, typ in tp:
                by_type[typ]["tp"] += 1
            for _, _, typ in fp:
                by_type[typ]["fp"] += 1
            for _, _, typ in fn:
                by_type[typ]["fn"] += 1

        return {
            "overall":  _prf(overall_tp, overall_fp, overall_fn),
            "by_type":  {
                t: _prf(v["tp"], v["fp"], v["fn"])
                for t, v in by_type.items()
            },
        }


class REMetrics:
    """
    RE 评估：(subj_text, pred_type, obj_text) 三元组精确匹配
    支持：整体指标 + 分关系类型指标
    """

    def evaluate(
        self,
        gold_records: List[Dict],
        pred_records: List[Dict],
    ) -> Dict[str, Any]:
        """
        Args:
            gold_records: [{gold_relations: [(subj,pred,obj)]}]
            pred_records: [{pred_relations: [(subj,pred,obj)]}]
        """
        overall_tp = overall_fp = overall_fn = 0
        by_rel: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

        for gold, pred in zip(gold_records, pred_records):
            gold_set = set(gold["gold_relations"])
            pred_set = set(pred.get("pred_relations", []))
            tp = gold_set & pred_set
            fp = pred_set - gold_set
            fn = gold_set - pred_set

            overall_tp += len(tp)
            overall_fp += len(fp)
            overall_fn += len(fn)

            for _, rel, _ in tp:
                by_rel[rel]["tp"] += 1
            for _, rel, _ in fp:
                by_rel[rel]["fp"] += 1
            for _, rel, _ in fn:
                by_rel[rel]["fn"] += 1

        return {
            "overall": _prf(overall_tp, overall_fp, overall_fn),
            "by_rel":  {
                r: _prf(v["tp"], v["fp"], v["fn"])
                for r, v in by_rel.items()
            },
        }


def print_metrics_table(title: str, metrics: Dict[str, Any]):
    """将评估结果格式化打印为表格。"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    overall = metrics.get("overall", {})
    print(f"  整体指标：P={overall.get('precision',0):.4f}  "
          f"R={overall.get('recall',0):.4f}  "
          f"F1={overall.get('f1',0):.4f}  "
          f"(TP={overall.get('tp',0)}, FP={overall.get('fp',0)}, FN={overall.get('fn',0)})")
    sub_key = "by_type" if "by_type" in metrics else "by_rel"
    if sub_key in metrics:
        print(f"\n  分类指标：")
        print(f"  {'类别':<20} {'P':>8} {'R':>8} {'F1':>8} {'TP':>6} {'FP':>6} {'FN':>6}")
        print(f"  {'-'*64}")
        for name, m in sorted(metrics[sub_key].items(), key=lambda x: -x[1]["f1"]):
            print(f"  {name:<20} {m['precision']:>8.4f} {m['recall']:>8.4f} "
                  f"{m['f1']:>8.4f} {m['tp']:>6} {m['fp']:>6} {m['fn']:>6}")
    print(f"{'='*60}\n")
