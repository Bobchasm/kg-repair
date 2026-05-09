/**
 * graphStyles.js — 图谱颜色常量（G6 版，Material Accent 配色）
 */

// 节点颜色：Material Design Accent，深色背景下最炫
export const NODE_COLORS = {
  Vehicle:     '#2979FF',  // 亮蓝
  Component:   '#00E676',  // 亮绿
  Fault:       '#FF1744',  // 亮红
  Symptom:     '#FF6D00',  // 亮橙
  RepairStep:  '#D500F9',  // 亮紫
  Tool:        '#FFD600',  // 亮黄
  System:      '#1DE9B6',  // 亮青
  Parameter:   '#90A4AE',  // 蓝灰
  Unknown:     '#546E7A',
}

// 边颜色（半透明）
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
