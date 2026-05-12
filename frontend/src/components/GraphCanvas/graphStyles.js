
export const NODE_COLORS = {
  Vehicle:     '#2979FF',
  Component:   '#00E676',
  Fault:       '#FF1744',
  Symptom:     '#FF6D00',
  RepairStep:  '#D500F9',
  Tool:        '#FFD600',
  System:      '#1DE9B6',
  Parameter:   '#90A4AE',
  Unknown:     '#546E7A',
}

export const REL_COLORS = {
  HAS_COMPONENT:     '#00E676bb',
  PART_OF:           '#2979FFbb',
  BELONGS_TO_SYSTEM: '#1DE9B6bb',
  CAUSES_FAULT:      '#FF1744cc',
  HAS_SYMPTOM:       '#FF6D00bb',
  DIAGNOSED_BY:      '#D500F9bb',
  REPAIRED_BY:       '#D500F9cc',
  REQUIRES_TOOL:     '#FFD600bb',
  AFFECTS:           '#FF174499',
  PRECEDES:          '#90A4AEbb',
  HAS_PARAMETER:     '#90A4AE99',
  INDICATES:         '#FF6D0099',
}

export const REL_LABELS = {
  HAS_COMPONENT:     '包含',
  PART_OF:           '属于',
  BELONGS_TO_SYSTEM: '属于系统',
  CAUSES_FAULT:      '导致故障',
  HAS_SYMPTOM:       '表现为',
  DIAGNOSED_BY:      '诊断方式',
  REPAIRED_BY:       '修复通过',
  REQUIRES_TOOL:     '需要工具',
  AFFECTS:           '影响',
  PRECEDES:          '前置步骤',
  HAS_PARAMETER:     '具有参数',
  INDICATES:         '指示',
}
