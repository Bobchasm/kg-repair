/**
 * graphStyles.js — Cytoscape.js 样式定义（浅色主题 + 曲线边）
 */

export const NODE_COLORS = {
  Vehicle:     '#3a7bd5',
  Component:   '#27ae60',
  Fault:       '#e74c3c',
  Symptom:     '#e67e22',
  RepairStep:  '#8e44ad',
  Tool:        '#d4a017',
  System:      '#16a085',
  Parameter:   '#7f8c8d',
  Unknown:     '#95a5a6',
}

// 边颜色（浅色背景下需更高不透明度）
export const REL_COLORS = {
  HAS_COMPONENT:     '#27ae60bb',
  PART_OF:           '#3a7bd5bb',
  BELONGS_TO_SYSTEM: '#16a085bb',
  CAUSES_FAULT:      '#e74c3ccc',
  HAS_SYMPTOM:       '#e67e22bb',
  DIAGNOSED_BY:      '#8e44adbb',
  REPAIRED_BY:       '#8e44adcc',
  REQUIRES_TOOL:     '#d4a017bb',
  AFFECTS:           '#e74c3c99',
  PRECEDES:          '#7f8c8dbb',
  HAS_PARAMETER:     '#7f8c8d99',
  INDICATES:         '#e67e2299',
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

// 根据 edge id 末位决定曲线方向，实现自然交错效果
const _curveDistance = (ele) => {
  const code = ele.id().charCodeAt(ele.id().length - 1) || 0
  return [code % 2 === 0 ? 35 : -35]
}

export const getCytoscapeStyles = () => [
  // ── 节点（浅色背景下减弱 shadow，保留彩色） ─────────────────────
  {
    selector: 'node',
    style: {
      'background-color':   (ele) => NODE_COLORS[ele.data('label')] || NODE_COLORS.Unknown,
      'background-opacity': 0.95,
      'label':              'data(name)',
      'text-valign':        'center',
      'text-halign':        'center',
      'color':              '#ffffff',
      'font-size':          '10px',
      'font-weight':        '700',
      'text-outline-width': 1.5,
      'text-outline-color': (ele) => NODE_COLORS[ele.data('label')] || NODE_COLORS.Unknown,
      'width':  (ele) => Math.max(38, Math.min(70, 28 + ele.data('name').length * 3.5)),
      'height': (ele) => Math.max(38, Math.min(70, 28 + ele.data('name').length * 3.5)),
      'border-width':   2,
      'border-color':   '#ffffff',
      'border-opacity': 0.7,
      // 浅色背景下 shadow 偏弱，体现立体感而非发光
      'shadow-blur':    10,
      'shadow-color':   (ele) => NODE_COLORS[ele.data('label')] || NODE_COLORS.Unknown,
      'shadow-opacity': 0.30,
      'shadow-offset-x': 0,
      'shadow-offset-y': 2,
      'text-max-width': '80px',
      'text-wrap':      'ellipsis',
      'transition-property': 'shadow-blur, shadow-opacity, border-width',
      'transition-duration': '0.2s',
      'z-index': 10,
    },
  },
  // ── 边：曲线 + 关系类型着色 ───────────────────────────────────────
  {
    selector: 'edge',
    style: {
      'width':                1.6,
      'line-color':           (ele) => REL_COLORS[ele.data('type')] || '#aab4be99',
      'target-arrow-color':   (ele) => REL_COLORS[ele.data('type')] || '#aab4be',
      'target-arrow-shape':   'triangle',
      'arrow-scale':          0.75,
      // 关键：所有边使用曲线，方向交错
      'curve-style':               'unbundled-bezier',
      'control-point-distances':   _curveDistance,
      'control-point-weights':     [0.5],
      'label':              '',
      'font-size':          '9px',
      'color':              '#546e7a',
      'text-background-color':   '#ffffffcc',
      'text-background-opacity': 1,
      'text-background-padding': '2px',
      'text-rotation':      'autorotate',
      'z-index': 1,
    },
  },
  // ── 悬浮节点 ─────────────────────────────────────────────────────
  {
    selector: 'node:hover',
    style: {
      'border-width':   3,
      'border-color':   '#ffffff',
      'shadow-blur':    20,
      'shadow-opacity': 0.55,
      'z-index': 9999,
    },
  },
  // ── 选中节点 ──────────────────────────────────────────────────────
  {
    selector: 'node:selected',
    style: {
      'border-width':   3,
      'border-color':   '#ffffff',
      'shadow-blur':    22,
      'shadow-opacity': 0.65,
      'z-index': 9999,
    },
  },
  // ── 邻居高亮 ──────────────────────────────────────────────────────
  {
    selector: '.highlighted',
    style: {
      'border-width':   3,
      'border-color':   '#f39c12',
      'shadow-color':   '#f39c12',
      'shadow-blur':    16,
      'shadow-opacity': 0.6,
      'z-index': 1000,
    },
  },
  {
    selector: '.highlighted-edge',
    style: {
      'line-color':         '#f39c12cc',
      'target-arrow-color': '#f39c12',
      'width':              2.5,
      'label':              (ele) => REL_LABELS[ele.data('type')] || ele.data('type'),
      'z-index': 1000,
    },
  },
  // ── 路径高亮 ──────────────────────────────────────────────────────
  {
    selector: '.path-node',
    style: {
      'border-width':   4,
      'border-color':   '#1565c0',
      'shadow-color':   '#1565c0',
      'shadow-blur':    24,
      'shadow-opacity': 0.7,
      'z-index': 2000,
    },
  },
  {
    selector: '.path-edge',
    style: {
      'line-color':         '#1565c0cc',
      'target-arrow-color': '#1565c0',
      'width':              3,
      'label':              (ele) => REL_LABELS[ele.data('type')] || ele.data('type'),
      'z-index': 2000,
    },
  },
  // ── 淡出 ──────────────────────────────────────────────────────────
  {
    selector: '.faded',
    style: {
      'opacity':        0.12,
      'shadow-opacity': 0,
    },
  },
  // ── 显示边标签模式 ────────────────────────────────────────────────
  {
    selector: '.show-label',
    style: {
      'label': (ele) => REL_LABELS[ele.data('type')] || ele.data('type'),
    },
  },
]
