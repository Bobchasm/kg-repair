/**
 * GraphCanvas.jsx — ECharts graph 可视化组件
 * 仿 docs/index.html 风格：force 布局 / 可拖拽 / 曲线边 / adjacency 高亮
 */
import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import * as echarts from 'echarts'
import s from './GraphCanvas.module.css'

export const NODE_COLORS = {
  Vehicle:    '#5470c6',
  Component:  '#73c0de',
  Fault:      '#fac858',
  Symptom:    '#ee6666',
  RepairStep: '#3ba272',
  Tool:       '#fc8452',
  System:     '#9a60b4',
  Parameter:  '#ea7ccc',
  Unknown:    '#666677',
}
const NODE_SIZES = {
  Vehicle: 42, System: 40, Fault: 36, Symptom: 32,
  Component: 30, RepairStep: 28, Tool: 26, Parameter: 24,
}
export const NODE_LABELS = {
  Vehicle: '车辆', Component: '零部件', Fault: '故障', Symptom: '症状',
  RepairStep: '维修步骤', Tool: '工具', System: '系统', Parameter: '参数',
}
const REL_LABELS_MAP = {
  HAS_COMPONENT: '包含', PART_OF: '属于', BELONGS_TO_SYSTEM: '属于系统',
  CAUSES_FAULT: '导致故障', HAS_SYMPTOM: '表现为', DIAGNOSED_BY: '诊断方式',
  REPAIRED_BY: '修复通过', REQUIRES_TOOL: '需要工具', AFFECTS: '影响',
  PRECEDES: '前置步骤', HAS_PARAMETER: '具有参数', INDICATES: '指示',
}

// ── 基础 ECharts 配置（仿 docs/index.html） ───────────────────────────
const BASE_OPTIONS = {
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'item',
    formatter: (p) => {
      if (p.dataType === 'node') {
        const color = NODE_COLORS[p.data.nodeType] || '#aaa'
        return `<strong style="font-size:13px">${p.name}</strong><br/>
          <span style="color:${color}">${NODE_LABELS[p.data.nodeType] || p.data.nodeType || ''}</span>`
      }
      if (p.dataType === 'edge') {
        return `<span style="color:#00d2ff">${REL_LABELS_MAP[p.data.value] || p.data.value || '关系'}</span>`
      }
      return p.name
    },
    backgroundColor: 'rgba(20,20,35,0.97)',
    borderColor: '#00d2ff',
    borderWidth: 1,
    textStyle: { color: '#fff', fontSize: 12 },
    extraCssText: 'box-shadow: 0 0 12px rgba(0,210,255,0.25); border-radius:8px;',
  },
  series: [{
    type: 'graph',
    layout: 'force',
    force: {
      repulsion:       700,
      edgeLength:      [80, 200],
      gravity:         0.08,
      friction:        0.12,
      layoutAnimation: true,
    },
    roam:      true,
    draggable: true,
    data:  [],
    links: [],
    categories: Object.keys(NODE_COLORS).map(k => ({
      name: k, itemStyle: { color: NODE_COLORS[k] }
    })),
    label: {
      show:     true,
      position: 'right',
      fontSize: 11,
      color:    '#c0ccd8',
      formatter: (p) => p.name.length > 14 ? p.name.slice(0, 13) + '…' : p.name,
    },
    emphasis: {
      focus: 'adjacency',
      label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#fff' },
      lineStyle: { width: 3 },
    },
    lineStyle: {
      color:     '#4a4a6a',
      curveness: 0.2,
      width:     1.5,
      opacity:   0.75,
    },
    edgeSymbol:     ['none', 'arrow'],
    edgeSymbolSize: [0, 10],
    edgeLabel:      { show: false },
  }],
}

// ── 原始数据合并（不去重 id 冲突）────────────────────────────────────
const mergeRaw = (old, incoming) => {
  const nodeMap = new Map(old.nodes.map(n => [n.id, n]))
  const edgeSet = new Set(old.edges.map(e => e.id))
  incoming.nodes.forEach(n => { if (!nodeMap.has(n.id)) nodeMap.set(n.id, n) })
  const newEdges = incoming.edges.filter(e => !edgeSet.has(e.id))
  return { nodes: [...nodeMap.values()], edges: [...old.edges, ...newEdges] }
}

// ── API 格式 → ECharts 格式（显示全部节点，包括孤立节点） ─────────────
const toEcharts = ({ nodes = [], edges = [] }) => {
  const eNodes = nodes
    .map(n => ({
      id:         n.id,
      name:       n.name,
      nodeType:   n.label,   // 重命名避免与 ECharts label 属性冲突
      props:      n.props || {},
      symbolSize: NODE_SIZES[n.label] || 28,
      category:   n.label || 'Unknown',
      itemStyle:  { color: NODE_COLORS[n.label] || NODE_COLORS.Unknown },
    }))
  const eEdges = edges.map(e => ({
    source: e.source,
    target: e.target,
    value:  e.type,
    lineStyle: { color: (NODE_COLORS[e.type] ? NODE_COLORS[e.type] : '#4a4a6a') + '88' },
  }))
  return { eNodes, eEdges }
}

const GraphCanvas = forwardRef(({ onNodeClick, onNodeDblClick }, ref) => {
  const containerRef  = useRef(null)
  const chartRef      = useRef(null)
  const rawDataRef    = useRef({ nodes: [], edges: [] })
  const callbacksRef  = useRef({ onNodeClick, onNodeDblClick })

  // 始终保持最新回调引用
  useEffect(() => { callbacksRef.current = { onNodeClick, onNodeDblClick } }, [onNodeClick, onNodeDblClick])

  // ── 初始化 ECharts ─────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return
    const chart = echarts.init(containerRef.current)
    chartRef.current = chart
    chart.setOption(BASE_OPTIONS)

    chart.on('click', (p) => {
      if (p.dataType === 'node') callbacksRef.current.onNodeClick?.(p.name, p.data)
    })
    chart.on('dblclick', (p) => {
      if (p.dataType === 'node') callbacksRef.current.onNodeDblClick?.(p.name)
    })

    const resize = () => chart.resize()
    window.addEventListener('resize', resize)
    return () => { chart.dispose(); window.removeEventListener('resize', resize) }
  }, [])

  // ── 暴露方法给父组件 ───────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    /** 加载新数据（replace=false 则合并到现有图谱） */
    loadData: (apiData, replace = true) => {
      const chart = chartRef.current
      if (!chart) return
      let raw
      if (replace) {
        raw = apiData
        rawDataRef.current = raw
      } else {
        raw = mergeRaw(rawDataRef.current, apiData)
        rawDataRef.current = raw
      }
      const { eNodes, eEdges } = toEcharts(raw)
      chart.setOption({ series: [{ data: eNodes, links: eEdges }] })
    },
    resetView: () => {
      chartRef.current?.dispatchAction({ type: 'restore' })
    },
    exportPng: () => {
      const url = chartRef.current?.getDataURL({ type: 'png', backgroundColor: '#0a0a12' })
      if (!url) return
      const a = document.createElement('a')
      a.href = url; a.download = 'knowledge-graph.png'; a.click()
    },
  }))

  return <div ref={containerRef} className={s.canvas} />
})

export default GraphCanvas
