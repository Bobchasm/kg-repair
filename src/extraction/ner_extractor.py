"""
ner_extractor.py — 命名实体识别模块（双路融合）
路径A：规则NER（正则 + 领域词典精确匹配）
路径B：CRF-NER（sklearn-crfsuite，BIO序列标注）
最终结果取并集，CRF 置信度低时以规则结果覆盖。
"""
import logging
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sklearn_crfsuite

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """识别出的实体"""
    text: str
    label: str           # 与 NodeLabel 值对齐
    start: int           # 在原句中的字符起始位置
    end: int             # 结束位置（不含）
    confidence: float = 1.0
    method: str = "rule" # "rule" | "crf"


# ──────────────────────────────────────────────────────────────────
# 规则 NER：正则 + 词典
# ──────────────────────────────────────────────────────────────────
# 格式：(pattern, label, confidence)
_RULE_PATTERNS: List[Tuple[re.Pattern, str, float]] = [
    # 故障码
    (re.compile(r"\b[A-Z][0-9]{4}\b"), "Fault", 0.95),
    # 规格参数（如 125cc、0.8mm、12V）
    (re.compile(r"\d+(?:\.\d+)?\s*(?:cc|ml|mm|cm|m|kg|N·m|rpm|kPa|MPa|bar|V|A|W|Hz|℃|°C)"), "Parameter", 0.90),
    # 零件编号（如 12100-KGH-900）
    (re.compile(r"\b\d{4,6}-[A-Z]{2,4}-\d{3,5}\b"), "Component", 0.92),
]

# 领域词典分类（词 → 实体类型）
_DICT_ENTITIES: Dict[str, str] = {
    # ── 车辆系统 ──────────────────────────────────────────────────
    "发动机系统": "System", "制动系统": "System", "冷却系统": "System",
    "润滑系统": "System", "燃油系统": "System", "点火系统": "System",
    "传动系统": "System", "悬挂系统": "System", "转向系统": "System",
    "排气系统": "System", "电气系统": "System", "液压系统": "System",
    # ── 零部件 ────────────────────────────────────────────────────
    "活塞": "Component", "活塞环": "Component", "活塞销": "Component",
    "气缸": "Component", "气缸盖": "Component", "气缸体": "Component",
    "曲轴": "Component", "曲轴箱": "Component", "凸轮轴": "Component",
    "连杆": "Component", "连杆轴承": "Component", "主轴承": "Component",
    "正时链条": "Component", "正时皮带": "Component", "张紧器": "Component",
    "气门": "Component", "气门弹簧": "Component", "摇臂": "Component",
    "火花塞": "Component", "点火线圈": "Component", "分电器": "Component",
    "节气门": "Component", "节气门体": "Component", "喷油嘴": "Component",
    "燃油泵": "Component", "燃油滤清器": "Component", "空气滤清器": "Component",
    "机油滤清器": "Component", "机油泵": "Component", "水泵": "Component",
    "散热器": "Component", "节温器": "Component", "风扇": "Component",
    "变速箱": "Component", "离合器": "Component", "飞轮": "Component",
    "传动轴": "Component", "半轴": "Component", "差速器": "Component",
    "刹车片": "Component", "制动盘": "Component", "制动鼓": "Component",
    "制动钳": "Component", "主缸": "Component", "轮缸": "Component",
    "减震器": "Component", "弹簧": "Component", "稳定杆": "Component",
    "方向机": "Component", "转向拉杆": "Component", "球头": "Component",
    "蓄电池": "Component", "发电机": "Component", "起动机": "Component",
    "保险丝": "Component", "继电器": "Component", "传感器": "Component",
    "氧传感器": "Component", "曲轴位置传感器": "Component", "水温传感器": "Component",
    "电子控制单元": "Component", "ECU": "Component",
    # ── 故障 ──────────────────────────────────────────────────────
    "磨损": "Fault", "烧蚀": "Fault", "漏油": "Fault", "漏水": "Fault",
    "漏气": "Fault", "断裂": "Fault", "变形": "Fault", "腐蚀": "Fault",
    "堵塞": "Fault", "卡滞": "Fault", "松动": "Fault", "失效": "Fault",
    "老化": "Fault", "氧化": "Fault", "过热": "Fault", "烧损": "Fault",
    "开裂": "Fault", "渗漏": "Fault", "脱落": "Fault", "抱死": "Fault",
    "爆缸": "Fault", "拉缸": "Fault", "烧瓦": "Fault", "曲轴断裂": "Fault",
    "活塞环磨损": "Fault", "气门烧蚀": "Fault", "正时链条跳齿": "Fault",
    # ── 症状 ──────────────────────────────────────────────────────
    "异响": "Symptom", "抖动": "Symptom", "冒烟": "Symptom", "冒白烟": "Symptom",
    "冒黑烟": "Symptom", "冒蓝烟": "Symptom", "油耗增加": "Symptom",
    "启动困难": "Symptom", "怠速不稳": "Symptom", "加速无力": "Symptom",
    "发动机异响": "Symptom", "制动跑偏": "Symptom", "方向盘抖动": "Symptom",
    "发热": "Symptom", "过热": "Symptom", "温度升高": "Symptom",
    # ── 工具 ──────────────────────────────────────────────────────
    "扭矩扳手": "Tool", "力矩扳手": "Tool", "活塞环压缩工具": "Tool",
    "气门研磨工具": "Tool", "拉马": "Tool", "压力表": "Tool",
    "万用表": "Tool", "示波器": "Tool", "诊断仪": "Tool", "OBD扫描仪": "Tool",
    "千分尺": "Tool", "游标卡尺": "Tool", "塞尺": "Tool", "深度尺": "Tool",
    "气缸压力表": "Tool", "燃油压力表": "Tool", "真空表": "Tool",
    "举升机": "Tool", "千斤顶": "Tool", "支撑架": "Tool",
    # ── 维修步骤关键词 ────────────────────────────────────────────
    "拆卸": "RepairStep", "安装": "RepairStep", "更换": "RepairStep",
    "检查": "RepairStep", "调整": "RepairStep", "清洗": "RepairStep",
    "研磨": "RepairStep", "测量": "RepairStep", "校准": "RepairStep",
    "紧固": "RepairStep", "润滑": "RepairStep", "充气": "RepairStep",
}


class RuleNER:
    """基于规则和词典的命名实体识别器。"""

    def recognize(self, sentence: str) -> List[Entity]:
        entities: List[Entity] = []

        # 1. 正则匹配
        for pattern, label, conf in _RULE_PATTERNS:
            for m in pattern.finditer(sentence):
                entities.append(Entity(
                    text=m.group(), label=label,
                    start=m.start(), end=m.end(),
                    confidence=conf, method="rule",
                ))

        # 2. 词典匹配（最长优先）
        for term, label in sorted(_DICT_ENTITIES.items(), key=lambda x: -len(x[0])):
            start = 0
            while True:
                idx = sentence.find(term, start)
                if idx == -1:
                    break
                # 避免重叠
                overlap = any(e.start <= idx < e.end or e.start < idx + len(term) <= e.end
                              for e in entities)
                if not overlap:
                    entities.append(Entity(
                        text=term, label=label,
                        start=idx, end=idx + len(term),
                        confidence=0.88, method="rule",
                    ))
                start = idx + 1

        return sorted(entities, key=lambda e: e.start)


# ──────────────────────────────────────────────────────────────────
# CRF NER：特征工程 + sklearn-crfsuite
# ──────────────────────────────────────────────────────────────────
def _word_features(words: List[str], pos_tags: List[str], i: int) -> Dict:
    """为位置 i 的词生成 CRF 特征向量。"""
    word = words[i]
    pos  = pos_tags[i] if pos_tags else "x"

    feats = {
        "word":      word,
        "pos":       pos,
        "word_len":  str(len(word)),
        "is_digit":  word.isdigit(),
        "prefix2":   word[:2],
        "suffix2":   word[-2:],
    }
    # 上下文特征
    if i > 0:
        feats["word-1"] = words[i - 1]
        feats["pos-1"]  = pos_tags[i - 1] if pos_tags else "x"
        feats["bigram-1"] = words[i - 1] + "_" + word
    else:
        feats["BOS"] = True

    if i < len(words) - 1:
        feats["word+1"] = words[i + 1]
        feats["pos+1"]  = pos_tags[i + 1] if pos_tags else "x"
    else:
        feats["EOS"] = True

    if i > 1:
        feats["word-2"] = words[i - 2]
    if i < len(words) - 2:
        feats["word+2"] = words[i + 2]

    return feats


def sentence_to_features(words: List[str], pos_tags: List[str]) -> List[Dict]:
    return [_word_features(words, pos_tags, i) for i in range(len(words))]


class CRFNer:
    """
    CRF 序列标注 NER。
    训练时使用标注数据，推理时对任意句子打 BIO 标签。
    """

    _LABEL_MAP = {
        "Vehicle": "VEH", "Component": "COM", "Fault": "FLT",
        "Symptom": "SYM", "RepairStep": "REP", "Tool": "TOL",
        "System": "SYS", "Parameter": "PAR",
    }
    _INV_LABEL_MAP = {v: k for k, v in _LABEL_MAP.items()}

    def __init__(self, model_path: str = "models/crf_ner.pkl"):
        self._model_path = model_path
        self._crf: Optional[sklearn_crfsuite.CRF] = None
        self._load_model()

    def _load_model(self):
        if Path(self._model_path).exists():
            with open(self._model_path, "rb") as f:
                self._crf = pickle.load(f)
            logger.info("CRF 模型已加载：%s", self._model_path)
        else:
            logger.warning("CRF 模型未找到，将跳过 CRF 识别：%s", self._model_path)

    def is_available(self) -> bool:
        return self._crf is not None

    def train(self, train_data: List[Tuple[List[str], List[str], List[str]]]):
        """
        训练 CRF 模型。
        train_data: [(words, pos_tags, bio_labels), ...]
        """
        X = [sentence_to_features(w, p) for w, p, _ in train_data]
        y = [labels for _, _, labels in train_data]

        self._crf = sklearn_crfsuite.CRF(
            algorithm="lbfgs",
            c1=0.1, c2=0.1,
            max_iterations=200,
            all_possible_transitions=True,
        )
        self._crf.fit(X, y)
        Path(self._model_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._model_path, "wb") as f:
            pickle.dump(self._crf, f)
        logger.info("CRF 模型训练完成，已保存至：%s", self._model_path)

    def recognize(self, words: List[str], pos_tags: List[str]) -> List[Entity]:
        """对已分词的句子进行 CRF 识别，返回实体列表。"""
        if not self.is_available() or not words:
            return []
        features = sentence_to_features(words, pos_tags)
        bio_labels = self._crf.predict_single(features)

        entities: List[Entity] = []
        i, char_offset = 0, 0
        while i < len(bio_labels):
            tag = bio_labels[i]
            if tag.startswith("B-"):
                entity_type_abbr = tag[2:]
                entity_label = self._INV_LABEL_MAP.get(entity_type_abbr, "Component")
                j = i + 1
                while j < len(bio_labels) and bio_labels[j] == f"I-{entity_type_abbr}":
                    j += 1
                entity_text = "".join(words[i:j])
                start = sum(len(w) for w in words[:i])
                end   = sum(len(w) for w in words[:j])
                entities.append(Entity(
                    text=entity_text, label=entity_label,
                    start=start, end=end,
                    confidence=0.75, method="crf",
                ))
                i = j
            else:
                i += 1
        return entities


# ──────────────────────────────────────────────────────────────────
# 融合 NER：规则优先，CRF 填补空白
# ──────────────────────────────────────────────────────────────────
class NERExtractor:
    """
    双路融合 NER：
      - 规则 NER 负责高精度匹配
      - CRF NER 负责识别规则未覆盖的实体
      - 结果合并时以规则为主，CRF 只添加无重叠实体
    """

    def __init__(self, crf_model_path: str = "models/crf_ner.pkl"):
        self._rule_ner = RuleNER()
        self._crf_ner  = CRFNer(crf_model_path)

    def recognize(
        self, sentence: str,
        words: Optional[List[str]] = None,
        pos_tags: Optional[List[str]] = None,
    ) -> List[Entity]:
        rule_entities = self._rule_ner.recognize(sentence)

        crf_entities: List[Entity] = []
        if self._crf_ner.is_available() and words:
            crf_entities = self._crf_ner.recognize(words, pos_tags or [])

        # 合并：CRF 实体若与规则实体无重叠则纳入
        merged = list(rule_entities)
        for ce in crf_entities:
            overlap = any(
                re.start <= ce.start < re.end or re.start < ce.end <= re.end
                for re in merged
            )
            if not overlap and len(ce.text) >= 2:
                merged.append(ce)

        return sorted(merged, key=lambda e: e.start)

    def get_crf(self) -> CRFNer:
        return self._crf_ner
