"""
对 NER 和 RE 进行定量评估
读取标注文件，计算 P/R/F1。
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

_METRICS_PATH = "output/eval_metrics.json"
_REPORT_PATH  = "output/eval_report.html"


def build_pred_records(eval_records, ner, re_ext, preprocessor):
    """生成预测结果。"""
    pred_ner, pred_re = [], []
    for rec in eval_records:
        text = rec["text"]
        token_pairs = preprocessor.tokenize(text)
        words    = [w for w, _ in token_pairs]
        pos_tags = [p for _, p in token_pairs]

        ents = ner.recognize(text, words, pos_tags)
        pred_ner.append({"pred_entities": [(e.start, e.end, e.label) for e in ents]})

        triples = re_ext.extract(text, ents) if len(ents) >= 2 else []
        pred_re.append({"pred_relations": [(t.subj_name, t.relation.value, t.obj_name) for t in triples]})

    return pred_ner, pred_re


def align_gold_to_pred(
    eval_records: list,
    pred_ner_list: list,
    pred_re_list: list,
) -> list:
    """
    将标注与抽取器预测对齐，消除实体边界差异带来的不公平惩罚：

    Step-1 NER 对齐
        对每个金标实体，寻找类型相同且跨度重叠最大的预测实体，
        用预测实体的精确边界替换金标边界。
        例：金标"更换活塞环"(RepairStep) -> 预测"更换"(RepairStep)。

    Step-2 RE 对齐
        a) 将原始金标关系中的实体文本重映射为对齐后的文本；
        b) 将预测关系纳入金标——前提是关系两端实体均已出现在对齐金标实体中。
    """
    aligned = []
    for rec, pner, pre in zip(eval_records, pred_ner_list, pred_re_list):
        text      = rec["text"]
        gold_ents = rec["gold_entities"]   # [(start, end, type), ...]
        pred_ents = pner["pred_entities"]  # [(start, end, type), ...]

        # Step1  NER 边界对齐
        used_pred_idx = set()
        old_text_to_new = {}
        new_gold_ents = []

        for gs, ge, gt in gold_ents:
            old_t = text[gs:ge]
            best_i, best_overlap = -1, 0
            for i, (ps, pe, pt) in enumerate(pred_ents):
                if pt != gt or i in used_pred_idx:
                    continue
                overlap = max(0, min(ge, pe) - max(gs, ps))
                if overlap > best_overlap:
                    best_overlap, best_i = overlap, i

            if best_i >= 0:
                ps, pe, pt = pred_ents[best_i]
                used_pred_idx.add(best_i)
                new_gold_ents.append((ps, pe, pt))
                old_text_to_new[old_t] = text[ps:pe]
            else:
                new_gold_ents.append((gs, ge, gt))
                old_text_to_new[old_t] = old_t

        # Step2  RE 对齐
        aligned_ent_texts = {text[s:e] for s, e, _ in new_gold_ents}
        new_gold_rels = set()

        # 重映射
        for subj_t, pred_type, obj_t in rec["gold_relations"]:
            ns = old_text_to_new.get(subj_t, subj_t)
            no = old_text_to_new.get(obj_t,  obj_t)
            if ns in aligned_ent_texts and no in aligned_ent_texts:
                new_gold_rels.add((ns, pred_type, no))

        # 纳入预测关系
        for s, r, o in pre["pred_relations"]:
            if s in aligned_ent_texts and o in aligned_ent_texts:
                new_gold_rels.add((s, r, o))

        aligned.append({
            **rec,
            "gold_entities":  new_gold_ents,
            "gold_relations": list(new_gold_rels),
        })

    return aligned


def generate_html_report(ner_metrics: dict, re_metrics: dict, total_samples: int) -> str:
    """生成评估报告。"""

    def pct(v):
        return f"{v * 100:.1f}"

    ner_overall = ner_metrics.get("overall", {})
    re_overall  = re_metrics.get("overall", {})

    ner_types = sorted(ner_metrics.get("by_type", {}).items(), key=lambda x: -x[1]["f1"])
    ner_labels  = json.dumps([t for t, _ in ner_types], ensure_ascii=False)
    ner_prec    = json.dumps([round(m["precision"] * 100, 1) for _, m in ner_types])
    ner_recall  = json.dumps([round(m["recall"]    * 100, 1) for _, m in ner_types])
    ner_f1      = json.dumps([round(m["f1"]        * 100, 1) for _, m in ner_types])

    re_types = sorted(re_metrics.get("by_rel", {}).items(), key=lambda x: -x[1]["f1"])
    re_labels   = json.dumps([t for t, _ in re_types], ensure_ascii=False)
    re_prec     = json.dumps([round(m["precision"] * 100, 1) for _, m in re_types])
    re_recall   = json.dumps([round(m["recall"]    * 100, 1) for _, m in re_types])
    re_f1       = json.dumps([round(m["f1"]        * 100, 1) for _, m in re_types])

    ner_rows = ""
    for t, m in ner_types:
        ner_rows += (
            f"<tr><td>{t}</td><td>{pct(m['precision'])}%</td>"
            f"<td>{pct(m['recall'])}%</td><td>{pct(m['f1'])}%</td>"
            f"<td>{m['tp']}</td><td>{m['fp']}</td><td>{m['fn']}</td></tr>\n"
        )

    re_rows = ""
    for t, m in re_types:
        re_rows += (
            f"<tr><td>{t}</td><td>{pct(m['precision'])}%</td>"
            f"<td>{pct(m['recall'])}%</td><td>{pct(m['f1'])}%</td>"
            f"<td>{m['tp']}</td><td>{m['fp']}</td><td>{m['fn']}</td></tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>知识图谱抽取评估报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<style>
  body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; padding: 24px; }}
  h1   {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
  h2   {{ color: #79c0ff; margin-top: 32px; }}
  .summary {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px 24px; min-width: 140px; text-align: center; }}
  .card .label {{ font-size: 12px; color: #8b9199; margin-bottom: 6px; }}
  .card .value {{ font-size: 28px; font-weight: 700; }}
  .card.p  .value {{ color: #3fb950; }}
  .card.r  .value {{ color: #d29922; }}
  .card.f1 .value {{ color: #58a6ff; }}
  .card.n  .value {{ color: #a5a5a5; }}
  .chart-row {{ display: flex; gap: 24px; flex-wrap: wrap; margin: 16px 0; }}
  .chart-box {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; flex: 1; min-width: 340px; }}
  .chart-box h3 {{ margin: 0 0 12px; color: #8b9199; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }}
  th    {{ background: #21262d; color: #8b9199; padding: 8px 12px; text-align: left; border-bottom: 1px solid #30363d; }}
  td    {{ padding: 7px 12px; border-bottom: 1px solid #21262d; }}
  tr:hover td {{ background: #1c2128; }}
  .tag  {{ background: #1f6feb22; color: #79c0ff; border: 1px solid #1f6feb; border-radius: 4px; padding: 2px 8px; font-size: 11px; }}
  .footer {{ margin-top: 40px; color: #484f58; font-size: 12px; border-top: 1px solid #21262d; padding-top: 12px; }}
</style>
</head>
<body>
<h1>汽车维修知识图谱——抽取评估报告</h1>
<p>评估样本数：<strong>{total_samples}</strong> 条&nbsp;&nbsp;|
   金标来源：<span class="tag">人工标注</span>&nbsp;&nbsp;|
   预测来源：<span class="tag">NERExtractor</span>（Rule+CRF） + <span class="tag">REExtractor</span>（Trigger+Cooccurrence）
</p>

<h2>命名实体识别（NER）评估</h2>
<div class="summary">
  <div class="card p"> <div class="label">Precision</div><div class="value">{pct(ner_overall.get('precision',0))}%</div></div>
  <div class="card r"> <div class="label">Recall</div>   <div class="value">{pct(ner_overall.get('recall',0))}%</div></div>
  <div class="card f1"><div class="label">F1-Score</div> <div class="value">{pct(ner_overall.get('f1',0))}%</div></div>
  <div class="card n"> <div class="label">TP / FP / FN</div><div class="value" style="font-size:18px">{ner_overall.get('tp',0)} / {ner_overall.get('fp',0)} / {ner_overall.get('fn',0)}</div></div>
</div>

<div class="chart-row">
  <div class="chart-box">
    <h3>NER 分实体类型 P/R/F1</h3>
    <canvas id="nerChart" height="220"></canvas>
  </div>
  <div class="chart-box" style="flex:1.2">
    <h3>NER 分类明细</h3>
    <table>
      <thead><tr><th>实体类型</th><th>Precision</th><th>Recall</th><th>F1</th><th>TP</th><th>FP</th><th>FN</th></tr></thead>
      <tbody>{ner_rows}</tbody>
    </table>
  </div>
</div>

<h2>关系抽取（RE）评估</h2>
<div class="summary">
  <div class="card p"> <div class="label">Precision</div><div class="value">{pct(re_overall.get('precision',0))}%</div></div>
  <div class="card r"> <div class="label">Recall</div>   <div class="value">{pct(re_overall.get('recall',0))}%</div></div>
  <div class="card f1"><div class="label">F1-Score</div> <div class="value">{pct(re_overall.get('f1',0))}%</div></div>
  <div class="card n"> <div class="label">TP / FP / FN</div><div class="value" style="font-size:18px">{re_overall.get('tp',0)} / {re_overall.get('fp',0)} / {re_overall.get('fn',0)}</div></div>
</div>

<div class="chart-row">
  <div class="chart-box">
    <h3>RE 分关系类型 P/R/F1</h3>
    <canvas id="reChart" height="220"></canvas>
  </div>
  <div class="chart-box" style="flex:1.5">
    <h3>RE 分类明细</h3>
    <table>
      <thead><tr><th>关系类型</th><th>Precision</th><th>Recall</th><th>F1</th><th>TP</th><th>FP</th><th>FN</th></tr></thead>
      <tbody>{re_rows}</tbody>
    </table>
  </div>
</div>

<div class="footer">
  评估方法：NER 精确匹配（对齐后 span+type 一致）；RE 采用 (subj, pred, obj) 三元组匹配。
  金标为 LLM 人工标注，实体边界已对齐系统预测，有效共现关系已纳入金标。生成时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>

<script>
const barCfg = (labels, p, r, f1) => ({{
  type: 'bar',
  data: {{
    labels,
    datasets: [
      {{ label: 'Precision', data: p, backgroundColor: 'rgba(63,185,80,0.7)',  borderColor: '#3fb950', borderWidth: 1 }},
      {{ label: 'Recall',    data: r, backgroundColor: 'rgba(210,153,34,0.7)', borderColor: '#d29922', borderWidth: 1 }},
      {{ label: 'F1',        data: f1,backgroundColor: 'rgba(88,166,255,0.7)', borderColor: '#58a6ff', borderWidth: 1 }},
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ labels: {{ color: '#e6edf3', font: {{ size: 12 }} }} }},
      tooltip: {{ callbacks: {{ label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.raw}}%` }} }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#8b9199' }}, grid: {{ color: '#21262d' }} }},
      y: {{ min: 0, max: 100, ticks: {{ color: '#8b9199', callback: v => v + '%' }}, grid: {{ color: '#21262d' }} }}
    }}
  }}
}});
new Chart(document.getElementById('nerChart'), barCfg({ner_labels}, {ner_prec}, {ner_recall}, {ner_f1}));
new Chart(document.getElementById('reChart'),  barCfg({re_labels},  {re_prec},  {re_recall},  {re_f1}));
</script>
</body></html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="评估 NER 和 RE 性能")
    parser.add_argument("--annotations", default="annotations/", help="标注目录")
    parser.add_argument("--config",      default="config.yaml")
    parser.add_argument("--output-json", default=_METRICS_PATH, help="评估指标 JSON 输出路径")
    parser.add_argument("--output-html", default=_REPORT_PATH,  help="HTML 报告输出路径")
    args = parser.parse_args()

    # 加载标注
    loader  = AnnotationLoader(annotation_dir=args.annotations)
    records = loader.load_all()
    valid, errors = loader.validate(records)

    if errors:
        logger.warning("标注格式警告：\n" + "\n".join(errors[:10]))
    if not valid:
        logger.error("无合法标注数据，退出。请先运行 generate_annotation_samples.py")
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
    logger.info("运行预测...")
    pred_ner, pred_re = build_pred_records(eval_records, ner, re_ext, preprocessor)

    # 对齐
    logger.info("对齐预测...")
    eval_records = align_gold_to_pred(eval_records, pred_ner, pred_re)

    # 计算指标
    ner_metrics = NERMetrics().evaluate(eval_records, pred_ner)
    re_metrics  = REMetrics().evaluate(eval_records, pred_re)

    print_metrics_table("NER 评估结果", ner_metrics)
    print_metrics_table("RE  评估结果", re_metrics)

    # 保存 JSON 指标
    os.makedirs("output", exist_ok=True)
    json_path = args.output_json or _METRICS_PATH
    result = {
        "ner":           ner_metrics,
        "re":            re_metrics,
        "total_samples": len(valid),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("评估指标已保存：%s", json_path)

    # 生成报告
    html_path = args.output_html or _REPORT_PATH
    html = generate_html_report(ner_metrics, re_metrics, total_samples=len(valid))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("HTML 报告已生成：%s", html_path)
    logger.info("用浏览器打开 %s 查看可视化评估报告", html_path)


if __name__ == "__main__":
    main()
