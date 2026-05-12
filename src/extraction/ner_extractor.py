"""
命名实体识别模块（双路融合）
路径A：规则NER（正则 + 领域词典精确匹配）
路径B：CRF-NER（sklearn-crfsuite，BIO序列标注）
最终结果取并集，CRF 置信度低时以规则结果覆盖
"""
import logging
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import sklearn_crfsuite

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    text: str
    label: str           # 与 NodeLabel 值对齐
    start: int           # 在原句中的字符起始位置
    end: int             # 结束位置（不含）
    confidence: float = 1.0
    method: str = "rule" # "rule" | "crf"
    props: Dict = field(default_factory=dict)  # 实体属性


# 规则 NER：正则 + 词典
# 格式：(pattern, label, confidence, props_fn)
# props_fn(match) 返回额外属性字典

def _param_props(m: re.Match) -> Dict:
    raw = m.group().strip()
    mv = re.match(r"(\d+(?:\.\d+)?)\s*(.*)", raw)
    if mv:
        return {"value": mv.group(1), "unit": mv.group(2).strip()}
    return {}

def _fault_code_props(m: re.Match) -> Dict:
    return {"fault_code": m.group()}

def _part_no_props(m: re.Match) -> Dict:
    return {"component_no": m.group()}

def _range_param_props(m: re.Match) -> Dict:
    raw = m.group().strip()
    mv = re.match(r"(\d[^A-Za-z]*?)\s*(N\.?m|kgf|mm|cm|\u03bcm|\u2103|°C|V|A|rpm|MPa|kPa|cc|ml)", raw)
    if mv:
        return {"value": mv.group(1).strip(), "unit": mv.group(2)}
    return {}

_RULE_PATTERNS: List[Tuple] = [
    # 零件编号（如 12100-KGH-900）
    (re.compile(r"\b\d{4,6}-[A-Z]{2,4}-\d{3,5}\b"), "Component", 0.92, _part_no_props),
]

# 领域词典分类（词 -> 实体类型）
_DICT_ENTITIES: Dict[str, str] = {
    # 车辆系统
    "发动机系统": "System", "制动系统": "System", "冷却系统": "System",
    "润滑系统": "System", "燃油系统": "System", "点火系统": "System",
    "传动系统": "System", "悬挂系统": "System", "转向系统": "System",
    "排气系统": "System", "电气系统": "System", "液压系统": "System",
    "进气系统": "System", "供油系统": "System", "充电系统": "System",
    "启动系统": "System", "操纵系统": "System", "悬架系统": "System",
    "制冷系统": "System", "空调系统": "System", "油料系统": "System",
    # 车辆
    "摩托车": "Vehicle", "轿车": "Vehicle", "越野车": "Vehicle", "SUV": "Vehicle",
    "货车": "Vehicle", "卡车": "Vehicle", "面包车": "Vehicle", "客车": "Vehicle",
    "装甲车": "Vehicle", "坦克": "Vehicle", "履带车辆": "Vehicle",
    "轮式装甲车": "Vehicle", "步兵战车": "Vehicle", "装甲输送车": "Vehicle",
    "自行车": "Vehicle", "电动车": "Vehicle", "汽车": "Vehicle",
    # 发动机零部件
    "活塞": "Component", "活塞环": "Component", "活塞销": "Component",
    "气缸": "Component", "气缸盖": "Component", "气缸体": "Component",
    "曲轴": "Component", "曲轴箱": "Component", "凸轮轴": "Component",
    "连杆": "Component", "连杆轴承": "Component", "主轴承": "Component",
    "正时链条": "Component", "正时皮带": "Component", "张紧器": "Component",
    "气门": "Component", "气门弹簧": "Component", "摇臂": "Component",
    "气门导管": "Component", "气门座": "Component", "气门盖": "Component",
    "推杆": "Component", "挺柱": "Component", "凸轮": "Component",
    "飞轮盖": "Component", "正时盖": "Component", "油底壳": "Component",
    "缸盖垫": "Component", "缸套": "Component",
    # 点火系统
    "火花塞": "Component", "点火线圈": "Component", "分电器": "Component",
    "点火提前器": "Component", "点火器": "Component",
    "高压包": "Component", "配电器": "Component",
    # 燃油系统
    "节气门": "Component", "节气门体": "Component", "喷油嘴": "Component",
    "燃油泵": "Component", "燃油滤清器": "Component", "空气滤清器": "Component",
    "化油器": "Component", "浮子室": "Component", "主量孔": "Component",
    "怠速量孔": "Component", "阻风门": "Component", "油针": "Component",
    "进气歧管": "Component", "排气歧管": "Component", "进气管": "Component",
    "排气管": "Component", "消声器": "Component",
    "燃油箱": "Component", "油箱": "Component", "油管": "Component",
    "节气门位置传感器": "Component",
    # 冷却润滑系统
    "机油滤清器": "Component", "机油泵": "Component", "水泵": "Component",
    "散热器": "Component", "节温器": "Component", "风扇": "Component",
    "冷却液": "Component", "机油": "Component", "润滑油": "Component",
    "油冷器": "Component", "水温传感器": "Component", "水箱": "Component",
    "机油墨": "Component", "油压传感器": "Component",
    # 传动系统
    "变速箱": "Component", "离合器": "Component", "飞轮": "Component",
    "传动轴": "Component", "半轴": "Component", "差速器": "Component",
    "万向节": "Component", "传动皮带": "Component", "链条": "Component",
    "链轮": "Component", "驱动轮": "Component", "从动轮": "Component",
    "CVT变速器": "Component", "无级变速器": "Component",
    "换档叉": "Component", "拨叉": "Component", "同步器": "Component",
    "传动装置": "Component", "超越离合器": "Component",
    # 制动系统
    "刹车片": "Component", "制动盘": "Component", "制动鼓": "Component",
    "制动钳": "Component", "主缸": "Component", "轮缸": "Component",
    "制动软管": "Component", "制动拉线": "Component", "刹车总泵": "Component",
    "刹车分泵": "Component", "ABS": "Component",
    # 悬挂转向系统
    "减震器": "Component", "弹簧": "Component", "稳定杆": "Component",
    "方向机": "Component", "转向拉杆": "Component", "球头": "Component",
    "前叉": "Component", "后减震": "Component", "前减震器": "Component",
    "后减震器": "Component", "减振器": "Component",
    # 车轮系统
    "前轮": "Component", "后轮": "Component", "轮毂": "Component",
    "轮胎": "Component", "轮辋": "Component", "轮圈": "Component",
    "气门嘴": "Component", "车轮轴承": "Component",
    # 电气系统
    "蓄电池": "Component", "发电机": "Component", "起动机": "Component",
    "保险丝": "Component", "继电器": "Component", "传感器": "Component",
    "氧传感器": "Component", "曲轴位置传感器": "Component",
    "电子控制单元": "Component", "ECU": "Component",
    "整流器": "Component", "调节器": "Component", "充电器": "Component",
    "点火开关": "Component", "保险盒": "Component", "线束": "Component",
    "电瓶": "Component", "电皮": "Component",
    # 照明仪表
    "前照灯": "Component", "尾灯": "Component", "转向灯": "Component",
    "刹车灯": "Component", "大灯": "Component",
    "仪表盘": "Component", "转速表": "Component", "油量表": "Component",
    "水温表": "Component", "时速表": "Component",
    # 其他密封件
    "油封": "Component", "密封圈": "Component", "轴承": "Component",
    "发动机仓": "Component", "空滤": "Component", "气滤": "Component",
    # 故障
    "磨损": "Fault", "烧蚀": "Fault", "漏油": "Fault", "漏水": "Fault",
    "漏气": "Fault", "断裂": "Fault", "变形": "Fault", "腐蚀": "Fault",
    "堵塞": "Fault", "卡滞": "Fault", "松动": "Fault", "失效": "Fault",
    "老化": "Fault", "氧化": "Fault", "过热": "Fault", "烧损": "Fault",
    "开裂": "Fault", "渗漏": "Fault", "脱落": "Fault", "抱死": "Fault",
    "爆缸": "Fault", "拉缸": "Fault", "烧瓦": "Fault", "曲轴断裂": "Fault",
    "活塞环磨损": "Fault", "气门烧蚀": "Fault", "正时链条跳齿": "Fault",
    "打滑": "Fault", "空转": "Fault", "卡死": "Fault", "卡住": "Fault",
    "熄火": "Fault", "不点火": "Fault", "烧机油": "Fault", "窜油": "Fault",
    "跑偏": "Fault", "偏磨": "Fault", "漏电": "Fault", "短路": "Fault",
    "断路": "Fault", "接触不良": "Fault", "接地不良": "Fault",
    "轴承损坏": "Fault", "油封损坏": "Fault", "密封圈损坏": "Fault",
    "弹簧断裂": "Fault", "皮带断裂": "Fault", "链条断裂": "Fault",
    "点火失败": "Fault", "供油不足": "Fault", "油压不足": "Fault",
    "水温过高": "Fault", "机油压力不足": "Fault",
    # 症状
    "异响": "Symptom", "抖动": "Symptom", "冒烟": "Symptom", "冒白烟": "Symptom",
    "冒黑烟": "Symptom", "冒蓝烟": "Symptom", "油耗增加": "Symptom",
    "启动困难": "Symptom", "怠速不稳": "Symptom", "加速无力": "Symptom",
    "发动机异响": "Symptom", "制动跑偏": "Symptom", "方向盘抖动": "Symptom",
    "发热": "Symptom", "温度升高": "Symptom",
    "噪音": "Symptom", "振动": "Symptom", "异味": "Symptom",
    "排烟异常": "Symptom", "电压异常": "Symptom", "充电异常": "Symptom",
    "油压报警": "Symptom", "水温报警": "Symptom", "怠速过高": "Symptom",
    "怠速过低": "Symptom", "转速不稳": "Symptom", "车辆抖动": "Symptom",
    "方向沉重": "Symptom", "刹车跑偏": "Symptom", "刹车异响": "Symptom",
    "冷却液渗漏": "Symptom", "机油消耗": "Symptom",
    "不起火": "Symptom", "怠速不稳": "Symptom",
    # 工具
    "扭矩扳手": "Tool", "力矩扳手": "Tool", "活塞环压缩工具": "Tool",
    "气门研磨工具": "Tool", "拉马": "Tool", "压力表": "Tool",
    "万用表": "Tool", "示波器": "Tool", "诊断仪": "Tool", "OBD扫描仪": "Tool",
    "千分尺": "Tool", "游标卡尺": "Tool", "塞尺": "Tool", "深度尺": "Tool",
    "气缸压力表": "Tool", "燃油压力表": "Tool", "真空表": "Tool",
    "举升机": "Tool", "千斤顶": "Tool", "支撑架": "Tool",
    "内六角扳手": "Tool", "梅花扳手": "Tool", "呆扳手": "Tool",
    "螺丝刀": "Tool", "十字螺丝刀": "Tool", "一字螺丝刀": "Tool",
    "钢丝钳": "Tool", "尖嘴钳": "Tool",
    "活动扳手": "Tool", "套筒扳手": "Tool",
    "橡皮锤": "Tool", "铜锤": "Tool",
    "磁性吸盘": "Tool", "轴承拉马": "Tool",
    # 维修步骤
    "拆卸": "RepairStep", "安装": "RepairStep", "更换": "RepairStep",
    "检查": "RepairStep", "调整": "RepairStep", "清洗": "RepairStep",
    "研磨": "RepairStep", "测量": "RepairStep", "校准": "RepairStep",
    "紧固": "RepairStep", "润滑": "RepairStep", "充气": "RepairStep",
    "拆解": "RepairStep", "组装": "RepairStep", "保养": "RepairStep",
    "维护": "RepairStep", "修理": "RepairStep", "加注": "RepairStep",
    "排放": "RepairStep", "预热": "RepairStep", "打磨": "RepairStep",
    "焊接": "RepairStep", "校正": "RepairStep", "试验": "RepairStep",
    "试车": "RepairStep", "检测": "RepairStep", "修复": "RepairStep",
    "重装": "RepairStep", "分解": "RepairStep", "拆取": "RepairStep",
    "拧紧": "RepairStep", "涂抹": "RepairStep",
}


class RuleNER:
    """基于规则和词典的命名实体识别器。"""

    def recognize(self, sentence: str) -> List[Entity]:
        entities: List[Entity] = []

        # 1.正则匹配
        for pattern, label, conf, props_fn in _RULE_PATTERNS:
            for m in pattern.finditer(sentence):
                entities.append(Entity(
                    text=m.group(), label=label,
                    start=m.start(), end=m.end(),
                    confidence=conf, method="rule",
                    props=props_fn(m),
                ))

        # 2.词典匹配（最长优先）
        for term, label in sorted(_DICT_ENTITIES.items(), key=lambda x: -len(x[0])):
            start = 0
            while True:
                idx = sentence.find(term, start)
                if idx == -1:
                    break
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


# CRF NER：特征工程 + sklearn-crfsuite
def _word_features(words: List[str], pos_tags: List[str], i: int) -> Dict:
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


# 融合 NER：规则优先，CRF 填补空白
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

        # CRF 实体若与规则实体无重叠则纳入
        merged = list(rule_entities)
        for ce in crf_entities:
            overlap = any(
                re.start <= ce.start < re.end or re.start < ce.end <= re.end
                for re in merged
            )
            if not overlap and len(ce.text) >= 2:
                merged.append(ce)

        # 去掉无意义短实体和低质量实体
        def _is_noise(e: Entity) -> bool:
            txt = e.text.strip()
            if e.label == "Parameter":
                return True
            if len(txt) < 2:
                return True
            if e.label == "Fault" and re.search(r"^[a-z][0-9]+$", txt):
                return True
            if e.label == "Fault" and re.match(r"^[A-Z]\d{3,5}$", txt):
                return True
            if txt.isdigit():
                return True
            if len(txt) == 1 and e.method == "crf":
                return True
            return False

        merged = [e for e in merged if not _is_noise(e)]
        return sorted(merged, key=lambda e: e.start)

    def get_crf(self) -> CRFNer:
        return self._crf_ner
