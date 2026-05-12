"""
训练 CRF-NER 模型
"""
import json
import sys
import logging
from pathlib import Path

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extraction.text_preprocessor import TextPreprocessor
from src.extraction.ner_extractor import CRFNer, sentence_to_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# CRFNer 内部用的标签缩写映射
_LABEL_MAP = {
    "Vehicle": "VEH", "Component": "COM", "Fault": "FLT",
    "Symptom": "SYM", "RepairStep": "REP", "Tool": "TOL",
    "System": "SYS", "Parameter": "PAR",
}


def build_bio_labels(text: str, words: list[str], entities: list[dict]) -> list[str]:
    """
    将字符级实体偏移量映射到 token 级 BIO 标签。

    steps:
      1.计算每个 token 在原文中的字符起始位置
      2.对每个 token，检查它是否落在某个实体 span 内
      3.分配 B-TYPE / I-TYPE / O 标签
    """
    # 计算每个 token 的字符起始位置
    token_char_starts = []
    offset = 0
    for w in words:
        idx = text.find(w, offset)
        if idx == -1:
            # 找不到时用当前 offset
            token_char_starts.append(offset)
        else:
            token_char_starts.append(idx)
            offset = idx + len(w)

    # 按实体起始位置建立 (start, end, abbr) 列表
    ent_spans = []
    for e in entities:
        abbr = _LABEL_MAP.get(e["type"])
        if abbr:
            ent_spans.append((e["start"], e["end"], abbr))

    bio = ["O"] * len(words)
    for ent_start, ent_end, abbr in ent_spans:
        first = True
        for ti, cs in enumerate(token_char_starts):
            tw = words[ti]
            ce = cs + len(tw)
            # token 与实体 span 有重叠
            if cs < ent_end and ce > ent_start:
                bio[ti] = ("B-" if first else "I-") + abbr
                first = False

    return bio


def load_train_data(samples_path: str, preprocessor: TextPreprocessor):
    """加载"""
    samples = json.load(open(samples_path, encoding="utf-8"))
    train_data = []
    skipped = 0

    for sample in samples:
        text = sample["text"]
        entities = sample.get("entities", [])

        token_pairs = preprocessor.tokenize(text)
        if not token_pairs:
            skipped += 1
            continue

        words    = [w for w, _ in token_pairs]
        pos_tags = [p for _, p in token_pairs]
        bio      = build_bio_labels(text, words, entities)

        train_data.append((words, pos_tags, bio))

    logger.info("加载训练样本 %d 条，跳过 %d 条", len(train_data), skipped)
    return train_data


def evaluate_on_train(crf_ner: CRFNer, train_data):
    """评估"""
    tp = fp = fn = 0
    for words, pos_tags, gold_bio in train_data:
        pred_entities = crf_ner.recognize(words, pos_tags)
        pred_set = {(e.start, e.end, e.label) for e in pred_entities}

        gold_set = set()
        char_starts = []
        offset = 0
        for w in words:
            char_starts.append(offset)
            offset += len(w)

        i = 0
        while i < len(gold_bio):
            tag = gold_bio[i]
            if tag.startswith("B-"):
                abbr = tag[2:]
                j = i + 1
                while j < len(gold_bio) and gold_bio[j] == f"I-{abbr}":
                    j += 1
                start = char_starts[i]
                end   = char_starts[j-1] + len(words[j-1])
                from src.extraction.ner_extractor import CRFNer as _C
                label = _C._INV_LABEL_MAP.get(abbr, abbr)
                gold_set.add((start, end, label))
                i = j
            else:
                i += 1

        tp += len(pred_set & gold_set)
        fp += len(pred_set - gold_set)
        fn += len(gold_set - pred_set)

    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = 2*p*r / (p+r) if p+r else 0
    logger.info("训练集自评：P=%.4f  R=%.4f  F1=%.4f  (TP=%d FP=%d FN=%d)",
                p, r, f1, tp, fp, fn)


def main():
    samples_path = ROOT / "annotations" / "samples.json"
    model_path   = str(ROOT / "models" / "crf_ner.pkl")

    if not samples_path.exists():
        logger.error("找不到标注文件：%s", samples_path)
        sys.exit(1)

    logger.info("初始化预处理器...")
    preprocessor = TextPreprocessor()

    logger.info("构建 BIO 训练数据...")
    train_data = load_train_data(str(samples_path), preprocessor)

    if len(train_data) < 10:
        logger.error("训练样本过少（%d），中止", len(train_data))
        sys.exit(1)

    logger.info("开始训练 CRF 模型（%d 条样本）...", len(train_data))
    crf_ner = CRFNer(model_path)
    crf_ner.train(train_data)

    logger.info("训练完成，模型已保存至：%s", model_path)

    logger.info("在训练集上验证...")
    evaluate_on_train(crf_ner, train_data)


if __name__ == "__main__":
    main()
