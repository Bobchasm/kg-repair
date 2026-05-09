"""
re_extractor.py — 关系抽取模块（双路融合）
路径A：触发词模板匹配（高精度）
路径B：依存句法模式（覆盖更多结构）
"""
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 避免循环导入
from src.extraction.ner_extractor import Entity
from src.graph.schema import NodeLabel, RelationType, Triple


# ──────────────────────────────────────────────────────────────────
# 关系触发词词典
# 格式：关系类型 → [触发词列表]
# ──────────────────────────────────────────────────────────────────
_TRIGGER_DICT: Dict[str, List[str]] = {
    RelationType.HAS_COMPONENT.value: [
        "由", "包含", "包括", "含有", "组成", "构成", "主要部件",
        "零件有", "部件包括", "主要由",
    ],
    RelationType.PART_OF.value: [
        "属于", "是.*的一部分", "隶属于", "安装在", "位于",
    ],
    RelationType.BELONGS_TO_SYSTEM.value: [
        "属于.*系统", "是.*系统的", "纳入.*系统",
    ],
    RelationType.CAUSES_FAULT.value: [
        "导致", "引起", "造成", "引发", "产生故障", "发生故障",
        "出现故障", "引起故障",
    ],
    RelationType.HAS_SYMPTOM.value: [
        "表现为", "症状为", "出现", "产生", "伴随", "引起.*症状",
    ],
    RelationType.DIAGNOSED_BY.value: [
        "通过.*检查", "检测方法", "诊断方法", "使用.*诊断",
    ],
    RelationType.REPAIRED_BY.value: [
        "维修方法", "修复方法", "通过.*修复", "处理方法", "更换.*修复",
        "进行.*维修", "采用.*方法",
    ],
    RelationType.REQUIRES_TOOL.value: [
        "使用", "需要", "借助", "利用", "配合.*工具", "用.*工具",
    ],
    RelationType.AFFECTS.value: [
        "影响", "损坏.*会导致", "损伤.*影响",
    ],
    RelationType.PRECEDES.value: [
        "之前", "先", "然后", "接着", "再", "首先.*然后",
    ],
}

# 主语-谓语-宾语型模式的实体类型约束
# (subj_allowed_labels, relation, obj_allowed_labels)
_TYPE_CONSTRAINTS: List[Tuple] = [
    ({"Vehicle", "System"}, RelationType.HAS_COMPONENT, {"Component"}),
    ({"Component"}, RelationType.PART_OF, {"System", "Vehicle"}),
    ({"Component"}, RelationType.BELONGS_TO_SYSTEM, {"System"}),
    ({"Component", "Fault"}, RelationType.CAUSES_FAULT, {"Fault"}),
    ({"Fault"}, RelationType.HAS_SYMPTOM, {"Symptom"}),
    ({"Symptom"}, RelationType.INDICATES, {"Fault"}),
    ({"Fault"}, RelationType.DIAGNOSED_BY, {"RepairStep"}),
    ({"Fault"}, RelationType.REPAIRED_BY, {"RepairStep"}),
    ({"RepairStep"}, RelationType.REQUIRES_TOOL, {"Tool"}),
    ({"Component"}, RelationType.AFFECTS, {"Component"}),
    ({"RepairStep"}, RelationType.PRECEDES, {"RepairStep"}),
]


def _check_type_constraint(
    subj_label: str,
    obj_label: str,
    relation: RelationType,
) -> bool:
    """检查三元组是否满足类型约束。"""
    for sl, rel, ol in _TYPE_CONSTRAINTS:
        if rel == relation and subj_label in sl and obj_label in ol:
            return True
    return False


# ──────────────────────────────────────────────────────────────────
# 触发词模式匹配
# ──────────────────────────────────────────────────────────────────
class TriggerRE:
    """基于触发词的关系抽取器。"""

    def extract(
        self,
        sentence: str,
        entities: List[Entity],
        source_doc: str = "",
    ) -> List[Triple]:
        """
        对句子中的所有实体对枚举可能关系。
        策略：
          1. 遍历触发词词典
          2. 若触发词在句子中出现，且触发词两侧有对应类型实体
          3. 按类型约束过滤，生成三元组
        """
        triples: List[Triple] = []
        if len(entities) < 2:
            return triples

        for rel_str, triggers in _TRIGGER_DICT.items():
            rel = RelationType(rel_str)
            for trigger in triggers:
                # 支持简单正则
                if re.search(trigger, sentence):
                    # 找触发词在句子中的位置
                    m = re.search(trigger, sentence)
                    if not m:
                        continue
                    trig_start, trig_end = m.start(), m.end()

                    # 触发词左侧实体作主语，右侧实体作宾语
                    left_ents  = [e for e in entities if e.end <= trig_start]
                    right_ents = [e for e in entities if e.start >= trig_end]

                    if not left_ents or not right_ents:
                        continue

                    subj = left_ents[-1]    # 最近左侧实体
                    obj  = right_ents[0]    # 最近右侧实体

                    if subj.text == obj.text:
                        continue
                    if not _check_type_constraint(subj.label, obj.label, rel):
                        continue

                    triples.append(Triple(
                        subj_label=NodeLabel(subj.label),
                        subj_name=subj.text,
                        relation=rel,
                        obj_label=NodeLabel(obj.label),
                        obj_name=obj.text,
                        confidence=min(subj.confidence, obj.confidence) * 0.9,
                        source_doc=source_doc,
                        source_sent=sentence[:200],
                    ))
        return triples


# ──────────────────────────────────────────────────────────────────
# 共现 + 距离启发式关系抽取
# ──────────────────────────────────────────────────────────────────
class CooccurrenceRE:
    """
    基于共现距离的启发式关系抽取。
    当两个实体在同一短句（50字内）共现时，
    根据类型组合推断关系。
    """

    # (subj_type, obj_type) → 推断关系
    _CO_RULES: Dict[Tuple[str, str], RelationType] = {
        ("Vehicle",   "Component"):  RelationType.HAS_COMPONENT,
        ("Component", "System"):     RelationType.BELONGS_TO_SYSTEM,
        ("System",    "Component"):  RelationType.HAS_COMPONENT,
        ("Component", "Fault"):      RelationType.CAUSES_FAULT,
        ("Fault",     "Symptom"):    RelationType.HAS_SYMPTOM,
        ("Symptom",   "Fault"):      RelationType.INDICATES,
        ("Fault",     "RepairStep"): RelationType.REPAIRED_BY,
        ("RepairStep","Tool"):       RelationType.REQUIRES_TOOL,
        ("Component", "Component"):  RelationType.AFFECTS,
    }
    _MAX_DIST = 50  # 字符距离阈值

    def extract(
        self,
        sentence: str,
        entities: List[Entity],
        source_doc: str = "",
    ) -> List[Triple]:
        triples: List[Triple] = []
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                dist = abs(e1.start - e2.start)
                if dist > self._MAX_DIST:
                    continue
                key = (e1.label, e2.label)
                if key not in self._CO_RULES:
                    key = (e2.label, e1.label)
                    if key not in self._CO_RULES:
                        continue
                    e1, e2 = e2, e1  # 调换主宾
                rel = self._CO_RULES[key]
                # 距离越近，置信度越高
                conf = max(0.4, 0.7 - dist / 200)
                triples.append(Triple(
                    subj_label=NodeLabel(e1.label),
                    subj_name=e1.text,
                    relation=rel,
                    obj_label=NodeLabel(e2.label),
                    obj_name=e2.text,
                    confidence=conf,
                    source_doc=source_doc,
                    source_sent=sentence[:200],
                ))
        return triples


# ──────────────────────────────────────────────────────────────────
# 融合关系抽取器
# ──────────────────────────────────────────────────────────────────
class REExtractor:
    """
    双路融合关系抽取：
      触发词 RE（高精度）+ 共现 RE（高召回）
    置信度阈值过滤：低于 0.4 的三元组丢弃。
    """

    MIN_CONFIDENCE = 0.4

    def __init__(self):
        self._trigger_re     = TriggerRE()
        self._cooccurrence_re = CooccurrenceRE()

    def extract(
        self,
        sentence: str,
        entities: List[Entity],
        source_doc: str = "",
    ) -> List[Triple]:
        # 双路抽取
        t_triples = self._trigger_re.extract(sentence, entities, source_doc)
        c_triples = self._cooccurrence_re.extract(sentence, entities, source_doc)

        # 合并去重（按 subj+rel+obj 去重，保留置信度高的）
        seen: Dict[Tuple, Triple] = {}
        for t in t_triples + c_triples:
            key = (t.subj_name, t.relation.value, t.obj_name)
            if key not in seen or t.confidence > seen[key].confidence:
                seen[key] = t

        result = [t for t in seen.values() if t.confidence >= self.MIN_CONFIDENCE]
        return result
