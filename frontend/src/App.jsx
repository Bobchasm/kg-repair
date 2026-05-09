/**
 * App.jsx — 主布局（仿 docs/index.html 风格）
 * 固定顶栏 + 左侧边栏（搜索/详情/统计）+ 右侧 ECharts 图谱
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import GraphCanvas, { NODE_COLORS, NODE_LABELS } from './components/GraphCanvas/GraphCanvas'
import { graphApi, searchApi, statsApi } from './services/api'
import s from './App.module.css'

const ALL_TYPES = ['Vehicle', 'Component', 'Fault', 'Symptom', 'RepairStep', 'Tool', 'System', 'Parameter']
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
  const [searchResults, setSearchResults]  = useState(null)   // null=未搜索, []=[]=无结果
  const [detail,        setDetail]         = useState(null)
  const [relations,     setRelations]      = useState([])
  const [statsData,     setStatsData]      = useState({})
  const [graphStats,    setGraphStats]     = useState('加载中...')
  const [loading,       setLoading]        = useState(false)

  // ── 初始化：加载全景图 + 统计 ─────────────────────────────────────
  useEffect(() => {
    loadOverview()
    fetchStats()
  }, [])

  const loadOverview = async () => {
    setLoading(true)
    try {
      const data = await graphApi.getOverview(400)
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
      setStatsData(data)
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
          <span onClick={fetchStats}>统计信息</span>
          <span onClick={() => graphRef.current?.exportPng()}>导出图像</span>
          <span className={s.divider}>|</span>
          <span onClick={() => graphRef.current?.resetView()}>重置视图</span>
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
                <div key={r.id} className={s.resultItem} onClick={() => focusNode(r.name)}>
                  <div className={s.resultName}>{r.name}</div>
                  <div className={s.resultType} style={{ color: NODE_COLORS[r.label] }}>
                    {TYPE_ICONS[r.label]} {NODE_LABELS[r.label] || r.label}
                  </div>
                </div>
              ))}
            </div>
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

      {/* 加载遮罩 */}
      {loading && (
        <div className={s.loadingOverlay}>
          <div className={s.spinner} />
        </div>
      )}
    </div>
  )
}
