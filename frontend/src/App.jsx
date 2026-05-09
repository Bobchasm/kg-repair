/**
 * App.jsx — 主布局（仿 docs/index.html 风格）
 * 固定顶栏 + 左侧边栏（搜索/详情/统计）+ 右侧 ECharts 图谱
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import GraphCanvas, { NODE_COLORS, NODE_LABELS } from './components/GraphCanvas/GraphCanvas'
import { graphApi, searchApi, statsApi, pathApi } from './services/api'
import s from './App.module.css'

// 去掉 Parameter（已折叠为实体属性，不再是独立节点）
const ALL_TYPES = ['Vehicle', 'Component', 'Fault', 'Symptom', 'RepairStep', 'Tool', 'System']
const TYPE_ICONS = {
  Vehicle: '🚗', Component: '🔧', Fault: '⚠️', Symptom: '🩺',
  RepairStep: '🛠️', Tool: '🔩', System: '🏭', Parameter: '📐',
}
const REL_LABELS = {
  HAS_COMPONENT: '包含', PART_OF: '属于', BELONGS_TO_SYSTEM: '属于系统',
  CAUSES_FAULT: '导致故障', HAS_SYMPTOM: '表现为', DIAGNOSED_BY: '诊断方式',
  REPAIRED_BY: '修复通过', REQUIRES_TOOL: '需要工具', AFFECTS: '影响',
  PRECEDES: '前置步骤', HAS_PARAMETER: '具有参数', INDICATES: '指示',
}

export default function App() {
  const graphRef = useRef(null)

  const [searchQ,       setSearchQ]       = useState('')
  const [searchType,    setSearchType]     = useState('all')
  const [searchResults, setSearchResults]  = useState(null)
  const [detail,        setDetail]         = useState(null)
  const [relations,     setRelations]      = useState([])
  const [statsData,     setStatsData]      = useState({})
  const [graphStats,    setGraphStats]     = useState('加载中...')
  const [loading,       setLoading]        = useState(false)
  // 新增：统计模态 + 最短路径
  const [showStats,     setShowStats]      = useState(false)
  const [pathFrom,      setPathFrom]       = useState('')
  const [pathTo,        setPathTo]         = useState('')
  const [pathResult,    setPathResult]     = useState(null)

  // ── 初始化：加载全景图 + 统计 ─────────────────────────────────────
  useEffect(() => {
    loadOverview()
    fetchStats()
  }, [])

  const loadOverview = async () => {
    setLoading(true)
    try {
      const data = await graphApi.getOverview(5000)
      graphRef.current?.loadData(data, true)
      setGraphStats(`节点: ${data.nodes?.length ?? 0} | 关系: ${data.edges?.length ?? 0}`)
    } catch (e) {
      setGraphStats('❌ 加载失败，请确认后端服务已启动')
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const data = await statsApi.getStats()
      // Transform node_labels [{label,cnt}] → node_counts {label:cnt}
      const node_counts = {}
      ;(data.node_labels || []).forEach(item => { node_counts[item.label] = item.cnt })
      setStatsData({ ...data, node_counts, total_edges: data.rel_count })
    } catch {}
  }

  // ── 搜索 ──────────────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    const q = searchQ.trim()
    if (!q) { setSearchResults([]); return }
    setLoading(true)
    try {
      const raw = await searchApi.search(q, 30)
      // 兼容 array 或 {nodes:[...]} 两种响应格式
      const list = Array.isArray(raw) ? raw : (raw?.nodes ?? raw?.results ?? [])
      const filtered = searchType === 'all' ? list : list.filter(n => n.label === searchType)
      setSearchResults(filtered)
    } catch {
      setSearchResults([])
    } finally {
      setLoading(false)
    }
  }, [searchQ, searchType])

  // ── 聚焦展开节点 ──────────────────────────────────────────────────
  const focusNode = useCallback(async (nodeName) => {
    setLoading(true)
    try {
      const data = await graphApi.getSubgraph(nodeName, 2, 100)
      graphRef.current?.loadData(data, true)
      setGraphStats(`聚焦: ${nodeName} | 节点: ${data.nodes?.length ?? 0} | 关系: ${data.edges?.length ?? 0}`)
      // 找到中心节点设为 detail
      const center = data.nodes?.find(n => n.name === nodeName)
      if (center) {
        const rels = data.edges?.filter(e => e.source === center.id || e.target === center.id) ?? []
        setDetail(center)
        setRelations(rels.slice(0, 12))
      }
    } catch {}
    setLoading(false)
  }, [])

  // ── 图谱节点单击 → 显示详情（不展开子图） ─────────────────────────
  const handleNodeClick = useCallback((name, echartsData) => {
    setDetail({
      id:    echartsData.id,
      name:  echartsData.name ?? name,
      label: echartsData.nodeType,
      props: echartsData.props ?? {},
    })
    setRelations([])
  }, [])

  // ── 图谱节点双击 → 展开子图 ───────────────────────────────────────
  const handleNodeDblClick = useCallback((name) => {
    focusNode(name)
  }, [focusNode])

  // ── 最短路径查询 ────────────────────────────────────────────────
  const handlePathSearch = useCallback(async () => {
    const from = pathFrom.trim()
    const to   = pathTo.trim()
    if (!from || !to) return
    setLoading(true)
    setPathResult(null)
    try {
      const data = await pathApi.shortestPath(from, to)
      setPathResult(data)
      // 把路径子图渲染到画布
      const pNodes = (data.path || []).filter(p => p.type === 'node')
      const pEdges = (data.path || []).filter(p => p.type === 'relation')
      graphRef.current?.loadData({
        nodes: pNodes.map(n => ({ id: n.id, name: n.name, label: n.label, props: n.props })),
        edges: pEdges.map(e => ({ id: e.id, source: e.source, target: e.target, type: e.rel })),
      }, true)
      setGraphStats(`路径：${from} → ${to} | 步数：${data.length}`)
    } catch (e) {
      setPathResult({ error: true })
    }
    setLoading(false)
  }, [pathFrom, pathTo])

  // ── 渲染 ──────────────────────────────────────────────────────────
  return (
    <div className={s.app}>
      {/* ── 顶部导航栏 ────────────────────────────────────────────── */}
      <nav className={s.navbar}>
        <div className={s.logo}>
          <span className={s.logoIcon}>⚙️</span>
          <span className={s.logoText}>汽车维修知识图谱</span>
        </div>
        <div className={s.navLinks}>
          <span onClick={loadOverview}>图谱视图</span>
          <span onClick={() => { fetchStats(); setShowStats(true) }}>统计信息</span>
          <span onClick={() => graphRef.current?.exportPng()}>导出图像</span>
        </div>
      </nav>

      {/* ── 主体：侧边栏 + 图谱区 ─────────────────────────────────── */}
      <div className={s.container}>

        {/* ── 左侧边栏 ──────────────────────────────────────────── */}
        <aside className={s.sidebar}>

          {/* 实体搜索 */}
          <div className={s.section}>
            <h3>🔍 实体搜索</h3>
            <div className={s.searchBox}>
              <input
                value={searchQ}
                onChange={e => setSearchQ(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="输入实体名称，如：发动机、漏油..."
              />
              <button onClick={handleSearch}>搜索</button>
            </div>

            {/* 类型过滤 */}
            <div className={s.typeFilters}>
              <button
                className={searchType === 'all' ? s.typeActive : s.typeBtn}
                onClick={() => setSearchType('all')}
              >全部</button>
              {ALL_TYPES.map(t => (
                <button
                  key={t}
                  className={searchType === t ? s.typeActive : s.typeBtn}
                  style={searchType === t ? {} : { borderColor: NODE_COLORS[t] + '60', color: NODE_COLORS[t] }}
                  onClick={() => setSearchType(t)}
                >
                  {TYPE_ICONS[t]} {NODE_LABELS[t]}
                </button>
              ))}
            </div>

            {/* 搜索结果列表 */}
            <div className={s.resultList}>
              {searchResults === null && (
                <div className={s.empty}>💡 输入关键词开始搜索</div>
              )}
              {searchResults !== null && searchResults.length === 0 && (
                <div className={s.empty}>🔍 未找到相关实体</div>
              )}
              {searchResults?.map(r => (
                <div key={r.neo4j_id ?? r.id ?? r.name} className={s.resultItem} onClick={() => focusNode(r.name)}>
                  <div className={s.resultName}>{r.name}</div>
                  <div className={s.resultType} style={{ color: NODE_COLORS[r.label] }}>
                    {TYPE_ICONS[r.label]} {NODE_LABELS[r.label] || r.label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 最短路径查询 */}
          <div className={s.section}>
            <h3>🔗 最短路径</h3>
            <div className={s.pathBox}>
              <input
                value={pathFrom}
                onChange={e => setPathFrom(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handlePathSearch()}
                placeholder="起始节点…"
              />
              <span className={s.pathArrow}>→</span>
              <input
                value={pathTo}
                onChange={e => setPathTo(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handlePathSearch()}
                placeholder="目标节点…"
              />
              <button onClick={handlePathSearch}>查询</button>
            </div>
            {pathResult && !pathResult.error && (
              <div className={s.pathResult}>
                <div className={s.pathLen}>路径长度：{pathResult.length} 步</div>
                <div className={s.pathNodes}>
                  {(pathResult.path || [])
                    .filter(p => p.type === 'node')
                    .map((p, i, arr) => (
                      <span
                        key={i}
                        className={s.pathNode}
                        style={{ color: NODE_COLORS[p.label] ?? '#aaa' }}
                        onClick={() => focusNode(p.name)}
                      >
                        {p.name}{i < arr.length - 1 ? ' →' : ''}
                      </span>
                    ))}
                </div>
              </div>
            )}
            {pathResult?.error && <div className={s.empty}>⚠️ 未找到两节点间的路径</div>}
          </div>

          {/* 实体详情 */}
          <div className={s.section}>
            <h3>📋 实体详情</h3>
            <div className={s.detailBox}>
              {!detail ? (
                <div className={s.empty}>✨ 点击图谱节点查看详情</div>
              ) : (
                <>
                  <h4 className={s.detailName}>{detail.name}</h4>
                  {detail.label && (
                    <span
                      className={s.detailBadge}
                      style={{
                        background: (NODE_COLORS[detail.label] ?? '#666') + '22',
                        borderColor: (NODE_COLORS[detail.label] ?? '#666') + '55',
                        color: NODE_COLORS[detail.label] ?? '#aaa',
                      }}
                    >
                      {TYPE_ICONS[detail.label]} {NODE_LABELS[detail.label] || detail.label}
                    </span>
                  )}

                  {Object.entries(detail.props ?? {})
                    .filter(([k, v]) => v && k !== 'id' && k !== 'name')
                    .slice(0, 8)
                    .map(([k, v]) => (
                      <div key={k} className={s.detailRow}>
                        <span className={s.detailKey}>{k}</span>
                        <span className={s.detailVal}>{String(v).slice(0, 60)}</span>
                      </div>
                    ))}

                  <button className={s.focusBtn} onClick={() => focusNode(detail.name)}>
                    🎯 在图谱中聚焦
                  </button>

                  {relations.length > 0 && (
                    <div className={s.relSection}>
                      <div className={s.relTitle}>🔗 关联关系 ({relations.length})</div>
                      {relations.map((r, i) => (
                        <div key={i} className={s.relItem}>
                          <span className={s.relType}>{REL_LABELS[r.type] || r.type}</span>
                          <span className={s.relArrow}>→</span>
                          <span className={s.relTarget}>{r.target}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* 图谱统计 */}
          <div className={s.section}>
            <h3>📊 图谱统计</h3>
            <div className={s.statsGrid}>
              {Object.entries(statsData.node_counts ?? {}).map(([type, count]) => (
                <div key={type} className={s.statRow}>
                  <span className={s.statDot} style={{ background: NODE_COLORS[type] ?? '#666' }} />
                  <span className={s.statLabel}>{NODE_LABELS[type] || type}</span>
                  <span className={s.statCount}>{count}</span>
                </div>
              ))}
              {statsData.total_edges != null && (
                <div className={s.statRow}>
                  <span className={s.statDot} style={{ background: '#4a4a6a' }} />
                  <span className={s.statLabel}>关系总数</span>
                  <span className={s.statCount}>{statsData.total_edges}</span>
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* ── 右侧图谱区域 ──────────────────────────────────────── */}
        <main className={s.main}>
          <GraphCanvas
            ref={graphRef}
            onNodeClick={handleNodeClick}
            onNodeDblClick={handleNodeDblClick}
          />
          <div className={s.statsBar}>📊 {graphStats}</div>
          <div className={s.infoTip}>🖱️ 拖拽节点查看连接 | 双击节点聚焦展开</div>
        </main>
      </div>

      {/* ── 统计信息模态弹窗 ─────────────────────────────────────── */}
      {showStats && (
        <div className={s.modalOverlay} onClick={() => setShowStats(false)}>
          <div className={s.statsModal} onClick={e => e.stopPropagation()}>
            <div className={s.modalHeader}>
              <h3>📊 图谱统计信息</h3>
              <button className={s.modalClose} onClick={() => setShowStats(false)}>✕</button>
            </div>
            <div className={s.modalBody}>
              {/* 总计卡片 */}
              <div className={s.modalSummary}>
                <div className={s.modalCard}>
                  <span className={s.modalCardNum}>{statsData.node_count ?? 0}</span>
                  <span className={s.modalCardLbl}>节点总数</span>
                </div>
                <div className={s.modalCard}>
                  <span className={s.modalCardNum}>{statsData.total_edges ?? 0}</span>
                  <span className={s.modalCardLbl}>关系总数</span>
                </div>
              </div>
              {/* 实体类型分布 */}
              <div className={s.modalSection}>
                <h4>实体类型分布</h4>
                <div className={s.barChart}>
                  {Object.entries(statsData.node_counts ?? {}).map(([type, count]) => {
                    const maxV = Math.max(...Object.values(statsData.node_counts ?? { _: 1 }), 1)
                    return (
                      <div key={type} className={s.barRow}>
                        <span className={s.barLabel} style={{ color: NODE_COLORS[type] }}>
                          {NODE_LABELS[type] || type}
                        </span>
                        <div className={s.barTrack}>
                          <div className={s.barFill} style={{ width: `${(count / maxV) * 100}%`, background: NODE_COLORS[type] ?? '#666' }} />
                        </div>
                        <span className={s.barCount}>{count}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
              {/* 关系类型分布 */}
              <div className={s.modalSection}>
                <h4>关系类型分布</h4>
                <div className={s.barChart}>
                  {(statsData.rel_types ?? []).map(({ rel, cnt }) => {
                    const maxV = Math.max(...(statsData.rel_types ?? [{ cnt: 1 }]).map(r => r.cnt), 1)
                    return (
                      <div key={rel} className={s.barRow}>
                        <span className={s.barLabel}>{REL_LABELS[rel] || rel}</span>
                        <div className={s.barTrack}>
                          <div className={s.barFill} style={{ width: `${(cnt / maxV) * 100}%`, background: '#00d2ff' }} />
                        </div>
                        <span className={s.barCount}>{cnt}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 加载遮罩 */}
      {loading && (
        <div className={s.loadingOverlay}>
          <div className={s.spinner} />
        </div>
      )}
    </div>
  )
}
