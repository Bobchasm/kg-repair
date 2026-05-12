"""
标注数据加载与格式转换
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


# 标注文件格式（schema）
# {
#   "doc_id": "sample_00001",
#   "source": "xxx.pdf",
#   "text": "发动机异响通常由活塞环磨损引起...",
#   "entities": [
#     {"id": "E0", "start": 0, "end": 5, "text": "发动机异响", "type": "Symptom"},
#     ...
#   ],
#   "relations": [
#     {"id": "R0", "subj": "E1", "pred": "HAS_SYMPTOM", "obj": "E0"},
#     ...
#   ]
# }

# 合法的实体类型（与 NodeLabel 值对齐）
VALID_ENTITY_TYPES = {
    "Vehicle", "Component", "Fault", "Symptom",
    "RepairStep", "Tool", "System", "Parameter",
}

# CRF 标签映射（实体类型 -> BIO前缀）
_TYPE_ABBR = {
    "Vehicle":    "VEH",
    "Component":  "COM",
    "Fault":      "FLT",
    "Symptom":    "SYM",
    "RepairStep": "REP",
    "Tool":       "TOL",
    "System":     "SYS",
    "Parameter":  "PAR",
}


class AnnotationLoader:
    """
    标注文件加载器
    """

    def __init__(self, annotation_dir: str = "annotations"):
        self._dir = Path(annotation_dir)

    def load_all(self) -> List[Dict[str, Any]]:
        if not self._dir.exists():
            logger.warning("标注目录不存在：%s", self._dir)
            return []
        records = []
        for fp in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    records.extend(data)
                else:
                    records.append(data)
            except Exception as e:
                logger.warning("读取标注文件失败 [%s]：%s", fp.name, e)
        logger.info("加载标注记录 %d 条（来自 %s）", len(records), self._dir)
        return records

    def validate(self, records: List[Dict]) -> Tuple[List[Dict], List[str]]:
        valid, errors = [], []
        for r in records:
            errs = self._validate_record(r)
            if errs:
                errors.extend(errs)
            else:
                valid.append(r)
        return valid, errors

    def _validate_record(self, r: Dict) -> List[str]:
        errs = []
        if "text" not in r:
            errs.append(f"[{r.get('doc_id')}] 缺少 text 字段")
            return errs
        text = r["text"]
        for e in r.get("entities", []):
            if e["type"] not in VALID_ENTITY_TYPES:
                errs.append(f"[{r['doc_id']}] 未知实体类型：{e['type']}")
            if text[e["start"]: e["end"]] != e["text"]:
                errs.append(
                    f"[{r['doc_id']}] 实体 span 与 text 不一致：{e}"
                )
        return errs

    def to_crf_format(
        self, records: List[Dict]
    ) -> List[Tuple[List[str], List[str], List[str]]]:
        import jieba.posseg as pseg
        results = []
        for r in records:
            text     = r["text"]
            entities = sorted(r.get("entities", []), key=lambda e: e["start"])
            # 字符级 BIO 标签
            char_labels = ["O"] * len(text)
            for ent in entities:
                abbr = _TYPE_ABBR.get(ent["type"], "COM")
                start, end = ent["start"], ent["end"]
                char_labels[start] = f"B-{abbr}"
                for i in range(start + 1, end):
                    char_labels[i] = f"I-{abbr}"

            # 分词，将字符级标签对齐到词级
            tokens = list(pseg.cut(text))
            words, pos_tags, bio_labels = [], [], []
            offset = 0
            for word, pos in tokens:
                words.append(word)
                pos_tags.append(str(pos))
                # 取词首字符的标签
                bio_labels.append(char_labels[offset] if offset < len(char_labels) else "O")
                offset += len(word)

            results.append((words, pos_tags, bio_labels))
        return results

    def to_eval_format(self, records: List[Dict]) -> List[Dict]:
        result = []
        for r in records:
            ent_map = {e["id"]: e for e in r.get("entities", [])}
            gold_ents = [(e["start"], e["end"], e["type"]) for e in r.get("entities", [])]
            gold_rels = [
                (
                    ent_map[rel["subj"]]["text"],
                    rel["pred"],
                    ent_map[rel["obj"]]["text"],
                )
                for rel in r.get("relations", [])
                if rel["subj"] in ent_map and rel["obj"] in ent_map
            ]
            result.append({
                "doc_id":        r.get("doc_id", ""),
                "text":          r["text"],
                "gold_entities": gold_ents,
                "gold_relations": gold_rels,
            })
        return result
