import React, { useRef, useState, useCallback } from 'react'
import {
  Layout, Button, Tooltip, Tabs, Spin, Space, Typography,
} from 'antd'
import {
  ReloadOutlined, CompressOutlined, DownloadOutlined,
  FilterOutlined, BarChartOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
} from '@ant-design/icons'

import GraphCanvas     from './components/GraphCanvas/GraphCanvas'
import DetailPanel     from './components/DetailPanel/DetailPanel'
import FilterPanel     from './components/FilterPanel/FilterPanel'
import SearchBar       from './components/SearchBar/SearchBar'
import StatsPanel      from './components/StatsPanel/StatsPanel'
import { NODE_COLORS } from './components/GraphCanvas/graphStyles'
import styles          from './App.module.css'

const { Header, Sider, Content } = Layout
const { Text } = Typography

const ALL_NODE_TYPES = [
  'Vehicle', 'Component', 'Fault', 'Symptom',
  'RepairStep', 'Tool', 'System', 'Parameter',
]
const ALL_REL_TYPES = [
  'HAS_COMPONENT', 'PART_OF', 'BELONGS_TO_SYSTEM', 'CAUSES_FAULT',
  'HAS_SYMPTOM', 'DIAGNOSED_BY', 'REPAIRED_BY', 'REQUIRES_TOOL',
  'AFFECTS', 'PRECEDES', 'HAS_PARAMETER', 'INDICATES',
]

const NODE_TYPE_CN = {
  Vehicle: '车辆', Component: '零部件', Fault: '故障',
  Symptom: '症状', RepairStep: '维修步骤', Tool: '工具',
  System: '系统', Parameter: '参数',
}

export default function App() {
  const graphRef = useRef(null)

  const [loading,       setLoading]      = useState(false)
  const [selection,     setSelection]    = useState(null)
  const [pathHighlight, setPathHigh]     = useState(null)
  const [siderTab,      setSiderTab]     = useState('filter')
  const [siderOpen,     setSiderOpen]    = useState(false)   // 默认折叠
  const [filterState,   setFilterState]  = useState({
    visibleNodes: [...ALL_NODE_TYPES],
    visibleRels:  [...ALL_REL_TYPES],
  })

  const handleReload   = () => graphRef.current?.loadOverview()
  const handleFit      = () => graphRef.current?.fit()
  const handleExport   = () => graphRef.current?.exportPng()

  const handleNodeFocus = useCallback((nodeName) => {
    graphRef.current?.expandNode(nodeName)
  }, [])

  const handlePathFound = useCallback((path) => {
    setPathHigh(path)
  }, [])

  const handleClearPath = useCallback(() => {
    setPathHigh(null)
    graphRef.current?.clearPath()
  }, [])

  const handleExpandFromDetail = useCallback((nodeName) => {
    graphRef.current?.expandNode(nodeName)
  }, [])

  const siderItems = [
    {
      key: 'filter',
      label: <Tooltip title="过滤" placement="right"><FilterOutlined /></Tooltip>,
      children: (
        <FilterPanel
          visibleNodes={filterState.visibleNodes}
          visibleRels={filterState.visibleRels}
          onChange={setFilterState}
        />
      ),
    },
    {
      key: 'stats',
      label: <Tooltip title="统计" placement="right"><BarChartOutlined /></Tooltip>,
      children: <StatsPanel />,
    },
  ]

  return (
    <Layout className={styles.app}>
      {/* ── 顶部工具栏 ──────────────────────────────────────── */}
      <Header className={styles.header}>
        {/* 折叠按钮 */}
        <Button
          type="text"
          icon={siderOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
          onClick={() => setSiderOpen(v => !v)}
          className={styles.siderToggle}
        />

        {/* Logo */}
        <div className={styles.logo}>
          <span className={styles.logoGlow}>⚙</span>
          <Text strong className={styles.logoText}>汽车维修知识图谱</Text>
        </div>

        {/* 搜索栏 */}
        <div className={styles.searchArea}>
          <SearchBar onNodeFocus={handleNodeFocus} onPathFound={handlePathFound} />
          {pathHighlight && (
            <Button
              size="small"
              onClick={handleClearPath}
              className={styles.clearPathBtn}
            >
              清除路径
            </Button>
          )}
        </div>

        {/* 工具按钮 */}
        <Space className={styles.tools}>
          {loading && <Spin size="small" />}
          <Tooltip title="刷新图谱">
            <Button icon={<ReloadOutlined />} type="text" className={styles.toolBtn} onClick={handleReload} />
          </Tooltip>
          <Tooltip title="适应视图">
            <Button icon={<CompressOutlined />} type="text" className={styles.toolBtn} onClick={handleFit} />
          </Tooltip>
          <Tooltip title="导出图片">
            <Button icon={<DownloadOutlined />} type="text" className={styles.toolBtn} onClick={handleExport} />
          </Tooltip>
        </Space>
      </Header>

      <Layout className={styles.body}>
        {/* ── 左侧面板（可折叠） ────────────────────────────── */}
        <Sider
          width={220}
          collapsedWidth={0}
          collapsed={!siderOpen}
          className={styles.sider}
          trigger={null}
        >
          <Tabs
            activeKey={siderTab}
            onChange={setSiderTab}
            items={siderItems}
            tabPosition="left"
            size="small"
            className={styles.siderTabs}
            style={{ height: '100%' }}
          />
        </Sider>

        {/* ── 主画布（全屏网状图谱） ───────────────────────── */}
        <Content className={styles.canvas}>
          <GraphCanvas
            ref={graphRef}
            onNodeSelect={setSelection}
            onLoadingChange={setLoading}
            pathHighlight={pathHighlight}
            filterState={filterState}
          />

          {/* 左下角图例（悬浮卡片） */}
          <div className={styles.legend}>
            <div className={styles.legendTitle}>节点类型</div>
            <div className={styles.legendGrid}>
              {ALL_NODE_TYPES.map((t) => (
                <div key={t} className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: NODE_COLORS[t], boxShadow: `0 0 6px ${NODE_COLORS[t]}` }} />
                  <span className={styles.legendLabel}>{NODE_TYPE_CN[t] || t}</span>
                </div>
              ))}
            </div>
          </div>
        </Content>

        {/* ── 右侧详情面板 ────────────────────────────────── */}
        <DetailPanel
          selection={selection}
          onClose={() => setSelection(null)}
          onExpand={handleExpandFromDetail}
        />
      </Layout>
    </Layout>
  )
}
