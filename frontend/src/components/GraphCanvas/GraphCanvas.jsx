import React, {
  useEffect, useRef, useCallback, forwardRef, useImperativeHandle,
} from 'react'
import cytoscape from 'cytoscape'
import fcose     from 'cytoscape-fcose'
import cola      from 'cytoscape-cola'
import { getCytoscapeStyles } from './graphStyles'
import { graphApi } from '../../services/api'
import { message }  from 'antd'
import styles from './GraphCanvas.module.css'

cytoscape.use(fcose)
cytoscape.use(cola)

// ── Cola 布局（真实物理碰撞 + 拖拽响应） ─────────────────────────────
const COLA_LAYOUT = {
  name: 'cola',
  animate: true,
  animationDuration: 1200,
  fit: true,
  padding: 60,
  nodeSpacing: 12,          // 节点最小间距（碰撞检测）
  edgeLength: 130,          // 理想边长
  maxSimulationTime: 5000,  // 物理模拟运行时长
  ungrabifyWhileSimulating: false,
  handleDisconnected: true,
  randomize: true,
  convergenceThreshold: 0.005,
  avoidOverlap: true,
}

// 增量布局（展开子图时不打乱已有节点）
const COLA_INCREMENTAL = {
  ...COLA_LAYOUT,
  randomize: false,
  maxSimulationTime: 2500,
  animationDuration: 700,
}

const GraphCanvas = forwardRef(function GraphCanvas(
  { onNodeSelect, onLoadingChange, pathHighlight, filterState },
  ref
) {
  const containerRef = useRef(null)
  const cyRef        = useRef(null)
  const tooltipRef   = useRef(null)

  useImperativeHandle(ref, () => ({
    loadOverview,
    expandNode,
    highlightPath,
    clearPath,
    fit:       () => cyRef.current?.fit(undefined, 50),
    resetZoom: () => cyRef.current?.reset(),
    exportPng: () => {
      const cy = cyRef.current
      if (!cy) return
      const png = cy.png({ full: true, scale: 2, bg: '#f5f7fa' })
      const a = document.createElement('a')
      a.href = png
      a.download = 'knowledge-graph.png'
      a.click()
    },
  }))

  // ── 初始化 ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return

    const cy = cytoscape({
      container:        containerRef.current,
      elements:         [],
      style:            getCytoscapeStyles(),
      minZoom:          0.04,
      maxZoom:          5,
      wheelSensitivity: 0.3,
    })
    cyRef.current = cy

    // tooltip 容器
    const tooltip = document.createElement('div')
    tooltip.className = styles.tooltip
    tooltip.style.display = 'none'
    containerRef.current.appendChild(tooltip)
    tooltipRef.current = tooltip

    // 悬浮 → 邻居高亮
    cy.on('mouseover', 'node', (e) => {
      const node = e.target
      const neighbors = node.neighborhood()
      cy.elements().addClass('faded')
      node.removeClass('faded').addClass('highlighted')
      neighbors.nodes().removeClass('faded').addClass('highlighted')
      neighbors.edges().removeClass('faded').addClass('highlighted-edge show-label')

      const { x, y } = e.renderedPosition
      tooltip.innerHTML = _buildTooltipHtml(node.data())
      tooltip.style.display = 'block'
      tooltip.style.left = `${x + 16}px`
      tooltip.style.top  = `${y - 12}px`
    })

    cy.on('mouseout', 'node', () => {
      cy.elements().removeClass('faded highlighted highlighted-edge show-label')
      tooltip.style.display = 'none'
    })

    cy.on('mousemove', 'node', (e) => {
      const { x, y } = e.renderedPosition
      tooltip.style.left = `${x + 16}px`
      tooltip.style.top  = `${y - 12}px`
    })

    // 单击 → 详情面板
    cy.on('tap', 'node', (e) => {
      onNodeSelect?.({ type: 'node', data: e.target.data() })
    })
    cy.on('tap', 'edge', (e) => {
      onNodeSelect?.({ type: 'edge', data: e.target.data() })
    })

    // 双击 → 展开子图
    cy.on('dbltap', 'node', (e) => {
      expandNode(e.target.data('name'))
    })

    // 点击空白 → 取消选中
    cy.on('tap', (e) => {
      if (e.target === cy) {
        onNodeSelect?.(null)
        cy.elements().removeClass('path-node path-edge')
      }
    })

    loadOverview()
    return () => cy.destroy()
  }, []) // eslint-disable-line

  // ── 加载全景图 ────────────────────────────────────────────────────
  const loadOverview = useCallback(async () => {
    onLoadingChange?.(true)
    try {
      const data = await graphApi.getOverview(400)
      _updateGraph(data)
    } catch (err) {
      message.error('加载图谱失败：' + err.message)
    } finally {
      onLoadingChange?.(false)
    }
  }, [onLoadingChange])

  // ── 展开节点子图 ──────────────────────────────────────────────────
  const expandNode = useCallback(async (nodeName) => {
    onLoadingChange?.(true)
    try {
      const data = await graphApi.getSubgraph(nodeName, 2, 80)
      _mergeGraph(data)
    } catch (err) {
      message.error('展开子图失败：' + err.message)
    } finally {
      onLoadingChange?.(false)
    }
  }, [onLoadingChange])

  // ── 路径高亮 ──────────────────────────────────────────────────────
  const highlightPath = useCallback((pathItems) => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().removeClass('path-node path-edge')
    const nodeIds = new Set(pathItems.filter(i => i.type === 'node').map(i => i.id))
    const edgeIds = new Set(pathItems.filter(i => i.type === 'relation').map(i => i.id))
    cy.nodes().filter(n => nodeIds.has(n.id())).addClass('path-node')
    cy.edges().filter(e => edgeIds.has(e.id())).addClass('path-edge')
    const pathEles = cy.collection([
      ...cy.nodes().filter(n => nodeIds.has(n.id())),
      ...cy.edges().filter(e => edgeIds.has(e.id())),
    ])
    if (pathEles.length > 0) cy.fit(pathEles, 80)
  }, [])

  const clearPath = useCallback(() => {
    cyRef.current?.elements().removeClass('path-node path-edge')
  }, [])

  // ── 数据更新 ──────────────────────────────────────────────────────
  const _updateGraph = (data) => {
    const cy = cyRef.current
    if (!cy) return
    cy.elements().remove()
    _addElements(data)
    cy.layout(COLA_LAYOUT).run()
  }

  const _mergeGraph = (data) => {
    const cy = cyRef.current
    if (!cy) return
    _addElements(data)
    cy.layout(COLA_INCREMENTAL).run()
  }

  const _addElements = ({ nodes = [], edges = [] }) => {
    const cy = cyRef.current
    if (!cy) return

    // 先统计所有将添加的节点 id（含已有节点）
    const existingIds = new Set(cy.nodes().map(n => n.id()))
    const newNodeIds  = new Set(nodes.map(n => n.id))
    const allIds      = new Set([...existingIds, ...newNodeIds])

    // 只保留两端节点都在图中的边
    const validEdges = edges.filter(e =>
      allIds.has(e.source) && allIds.has(e.target)
    )
    // 只有"至少有一条有效边"的新节点才加入
    const connectedNodeIds = new Set([
      ...validEdges.map(e => e.source),
      ...validEdges.map(e => e.target),
    ])

    const newNodes = nodes
      .filter(n => !existingIds.has(n.id) && connectedNodeIds.has(n.id))
      .map(n  => ({ group: 'nodes', data: { id: n.id, ...n } }))

    const newEdges = validEdges
      .filter(e => !cy.getElementById(e.id).length)
      .map(e  => ({ group: 'edges', data: { id: e.id, source: e.source, target: e.target, ...e } }))

    cy.add([...newNodes, ...newEdges])

    // 再次清理：已有节点若现在变成孤立节点，也移除
    cy.nodes().forEach(n => { if (n.degree() === 0) n.remove() })
  }

  // ── 过滤器联动 ────────────────────────────────────────────────────
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !filterState) return

    const { visibleNodes, visibleRels } = filterState

    // 显示/隐藏节点和边
    cy.nodes().forEach(n => {
      const label = n.data('label')
      if (!visibleNodes.includes(label)) n.hide(); else n.show()
    })
    cy.edges().forEach(e => {
      const type = e.data('type')
      if (!visibleRels.includes(type)) e.hide(); else e.show()
    })

    // 隐藏因边被隐藏而变为孤立的节点
    cy.nodes().filter(n => n.visible() && n.connectedEdges(':visible').length === 0).hide()
  }, [filterState])

  // ── Tooltip HTML ──────────────────────────────────────────────────
  const _buildTooltipHtml = (data) => {
    const props = data.props || {}
    const entries = Object.entries(props)
      .filter(([k, v]) => v && !['id', 'name', 'source_sent'].includes(k))
      .slice(0, 5)
    const rows = entries.map(([k, v]) =>
      `<div class="${styles.tooltipRow}">
        <span class="${styles.tooltipKey}">${k}</span>
        <span class="${styles.tooltipVal}">${String(v).slice(0, 30)}</span>
      </div>`
    ).join('')
    return `
      <div class="${styles.tooltipHeader}">
        <span class="${styles.tooltipLabel}">${data.label || ''}</span>
        <strong class="${styles.tooltipName}">${data.name || ''}</strong>
      </div>
      ${rows || '<div style="color:#78909c;font-size:10px">暂无附加属性</div>'}
    `
  }

  useEffect(() => {
    if (pathHighlight) highlightPath(pathHighlight)
    else clearPath()
  }, [pathHighlight, highlightPath, clearPath])

  return <div ref={containerRef} className={styles.canvas} />
})

export default GraphCanvas
