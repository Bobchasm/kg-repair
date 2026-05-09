"""
schema.py — 知识图谱本体定义
定义所有节点类型、关系类型及其属性规范。
遵循开闭原则：新增实体/关系只需在此文件扩展。
"""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────────────────────────
# 节点标签枚举
# ──────────────────────────────────────────────────────────────────
class NodeLabel(str, Enum):
    VEHICLE      = "Vehicle"       # 车辆/车型
    COMPONENT    = "Component"     # 零部件
    FAULT        = "Fault"         # 故障
    SYMPTOM      = "Symptom"       # 故障症状
    REPAIR_STEP  = "RepairStep"    # 维修步骤/程序
    TOOL         = "Tool"          # 工具/仪器
    SYSTEM       = "System"        # 车辆系统（发动机系统等）
    PARAMETER    = "Parameter"     # 技术参数


# ──────────────────────────────────────────────────────────────────
# 关系类型枚举
# ──────────────────────────────────────────────────────────────────
class RelationType(str, Enum):
    HAS_COMPONENT      = "HAS_COMPONENT"      # 车辆/系统 -[含有]-> 零部件
    PART_OF            = "PART_OF"            # 零部件 -[属于]-> 系统/车辆
    BELONGS_TO_SYSTEM  = "BELONGS_TO_SYSTEM"  # 零部件 -[属于系统]-> 系统
    CAUSES_FAULT       = "CAUSES_FAULT"       # 零部件故障 -[导致]-> 故障
    HAS_SYMPTOM        = "HAS_SYMPTOM"        # 故障 -[表现为]-> 症状
    DIAGNOSED_BY       = "DIAGNOSED_BY"       # 故障 -[诊断方式]-> 维修步骤
    REPAIRED_BY        = "REPAIRED_BY"        # 故障 -[修复通过]-> 维修步骤
    REQUIRES_TOOL      = "REQUIRES_TOOL"      # 维修步骤 -[需要]-> 工具
    AFFECTS            = "AFFECTS"            # 零部件 -[影响]-> 零部件
    PRECEDES           = "PRECEDES"           # 步骤 -[前置于]-> 步骤
    HAS_PARAMETER      = "HAS_PARAMETER"      # 零部件/车辆 -[具有参数]-> 参数
    INDICATES          = "INDICATES"          # 症状 -[指示]-> 故障


# ──────────────────────────────────────────────────────────────────
# 节点数据类（属性规范）
# ──────────────────────────────────────────────────────────────────
@dataclass
class VehicleNode:
    name: str
    brand: str = ""                  # 品牌
    model: str = ""                  # 型号
    engine_type: str = ""            # 发动机类型
    displacement: str = ""           # 排量
    fuel_type: str = ""              # 燃油类型
    year: str = ""                   # 年份/年代
    source_doc: str = ""             # 来源文档

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class ComponentNode:
    name: str
    component_no: str = ""           # 零件编号
    system: str = ""                 # 所属系统
    specs: str = ""                  # 规格参数
    material: str = ""               # 材质
    description: str = ""
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class FaultNode:
    name: str
    fault_code: str = ""             # 故障码（如OBD码）
    severity: str = "medium"         # low / medium / high
    fault_type: str = ""             # 故障类别
    description: str = ""
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class SymptomNode:
    name: str
    observable_method: str = ""      # 观测方式（听、看、测量）
    description: str = ""
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class RepairStepNode:
    name: str
    step_no: int = 0                 # 步骤序号
    operation: str = ""              # 操作说明
    precaution: str = ""             # 注意事项
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class ToolNode:
    name: str
    tool_spec: str = ""              # 规格型号
    tool_type: str = ""              # 工具类型（手动/电动/仪器）
    usage: str = ""                  # 用途说明
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class SystemNode:
    name: str
    description: str = ""
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class ParameterNode:
    name: str
    value: str = ""                  # 参数值
    unit: str = ""                   # 单位
    source_doc: str = ""

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v}


# ──────────────────────────────────────────────────────────────────
# 关系数据类
# ──────────────────────────────────────────────────────────────────
@dataclass
class Triple:
    """一条知识三元组"""
    subj_label: NodeLabel
    subj_name: str
    relation: RelationType
    obj_label: NodeLabel
    obj_name: str
    confidence: float = 1.0          # 抽取置信度
    source_doc: str = ""
    source_sent: str = ""            # 来源句子（可溯源）

    def to_dict(self):
        return {
            "subj_label": self.subj_label.value,
            "subj_name":  self.subj_name,
            "relation":   self.relation.value,
            "obj_label":  self.obj_label.value,
            "obj_name":   self.obj_name,
            "confidence": self.confidence,
            "source_doc": self.source_doc,
            "source_sent": self.source_sent,
        }


# ──────────────────────────────────────────────────────────────────
# 节点标签 → 默认数据类的映射
# ──────────────────────────────────────────────────────────────────
LABEL_TO_DATACLASS = {
    NodeLabel.VEHICLE:     VehicleNode,
    NodeLabel.COMPONENT:   ComponentNode,
    NodeLabel.FAULT:       FaultNode,
    NodeLabel.SYMPTOM:     SymptomNode,
    NodeLabel.REPAIR_STEP: RepairStepNode,
    NodeLabel.TOOL:        ToolNode,
    NodeLabel.SYSTEM:      SystemNode,
    NodeLabel.PARAMETER:   ParameterNode,
}

# 各标签的颜色（供前端使用）
LABEL_COLORS = {
    NodeLabel.VEHICLE.value:      "#4A90D9",
    NodeLabel.COMPONENT.value:    "#7EC8A4",
    NodeLabel.FAULT.value:        "#E85D5D",
    NodeLabel.SYMPTOM.value:      "#F4A261",
    NodeLabel.REPAIR_STEP.value:  "#9B59B6",
    NodeLabel.TOOL.value:         "#F1C40F",
    NodeLabel.SYSTEM.value:       "#1ABC9C",
    NodeLabel.PARAMETER.value:    "#95A5A6",
}
