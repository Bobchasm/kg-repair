/**
 * 图谱统计仪表盘 + NER/RE 评估可视化
 */
import React, { useEffect, useState } from 'react'
import { Tabs } from 'antd'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { Statistic, Row, Col, Spin, Alert } from 'antd'
import { NodeIndexOutlined, ShareAltOutlined, ExperimentOutlined } from '@ant-design/icons'
import { statsApi, evalApi } from '../../services/api'
import { NODE_COLORS } from '../GraphCanvas/graphStyles'
import styles from './StatsPanel.module.css'

const RADIAN = Math.PI / 180
const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.04) return null
  const r = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={10}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

// 图谱统计 Tab
function GraphStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    statsApi.getStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className={styles.loading}><Spin /></div>
  if (!stats) return null

  const nodeData = (stats.node_labels || []).map((d) => ({
    name: d.label,
    value: d.cnt,
    color: NODE_COLORS[d.label] || '#7f8c8d',
  }))

  const relData = (stats.rel_types || []).slice(0, 8).map((d, i) => ({
    name: d.rel,
    value: d.cnt,
    color: `hsl(${i * 30 + 180}, 60%, 55%)`,
  }))

  return (
    <>
      <Row gutter={8} className={styles.totals}>
        <Col span={12}>
          <div className={styles.statCard}>
            <NodeIndexOutlined style={{ color: '#4A90D9', fontSize: 18 }} />
            <Statistic
              value={stats.node_count}
              valueStyle={{ color: '#e6edf3', fontSize: 22 }}
              suffix={<span style={{ fontSize: 11, color: '#8b9199' }}>节点</span>}
            />
          </div>
        </Col>
        <Col span={12}>
          <div className={styles.statCard}>
            <ShareAltOutlined style={{ color: '#7EC8A4', fontSize: 18 }} />
            <Statistic
              value={stats.rel_count}
              valueStyle={{ color: '#e6edf3', fontSize: 22 }}
              suffix={<span style={{ fontSize: 11, color: '#8b9199' }}>关系</span>}
            />
          </div>
        </Col>
      </Row>

      <div className={styles.chartTitle}>节点类型分布</div>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={nodeData}
            cx="50%" cy="50%"
            outerRadius={70}
            dataKey="value"
            labelLine={false}
            label={renderCustomLabel}
          >
            {nodeData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: '#1c2128', border: '1px solid #30363d', fontSize: 12 }}
            itemStyle={{ color: '#e6edf3' }}
          />
          <Legend iconSize={8} wrapperStyle={{ fontSize: 10, color: '#8b9199' }} />
        </PieChart>
      </ResponsiveContainer>

      <div className={styles.chartTitle}>关系类型分布（TOP 8）</div>
      <div className={styles.relList}>
        {relData.map((d) => (
          <div key={d.name} className={styles.relItem}>
            <div className={styles.relBar} style={{ width: `${Math.round(d.value / relData[0].value * 100)}%`, background: d.color }} />
            <span className={styles.relName}>{d.name}</span>
            <span className={styles.relCount}>{d.value}</span>
          </div>
        ))}
      </div>
    </>
  )
}

function MetricsCards({ overall }) {
  const pct = (v) => `${((v || 0) * 100).toFixed(1)}%`
  return (
    <div className={styles.metricsCards}>
      <div className={`${styles.metricCard} ${styles.cardP}`}>
        <div className={styles.metricLabel}>Precision</div>
        <div className={styles.metricValue}>{pct(overall?.precision)}</div>
      </div>
      <div className={`${styles.metricCard} ${styles.cardR}`}>
        <div className={styles.metricLabel}>Recall</div>
        <div className={styles.metricValue}>{pct(overall?.recall)}</div>
      </div>
      <div className={`${styles.metricCard} ${styles.cardF1}`}>
        <div className={styles.metricLabel}>F1-Score</div>
        <div className={styles.metricValue}>{pct(overall?.f1)}</div>
      </div>
      <div className={styles.metricCard}>
        <div className={styles.metricLabel}>TP / FP / FN</div>
        <div className={styles.metricValueSm}>
          {overall?.tp ?? 0} / {overall?.fp ?? 0} / {overall?.fn ?? 0}
        </div>
      </div>
    </div>
  )
}

function TypeBarChart({ byType, height = 180 }) {
  const data = Object.entries(byType || {})
    .map(([name, m]) => ({
      name,
      P: +((m.precision || 0) * 100).toFixed(1),
      R: +((m.recall    || 0) * 100).toFixed(1),
      F1: +((m.f1       || 0) * 100).toFixed(1),
    }))
    .sort((a, b) => b.F1 - a.F1)

  if (!data.length) return <div className={styles.noData}>暂无分类数据</div>

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 40, left: 0 }} barCategoryGap="30%">
        <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
        <XAxis
          dataKey="name"
          tick={{ fill: '#8b9199', fontSize: 10 }}
          angle={-35}
          textAnchor="end"
          interval={0}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: '#8b9199', fontSize: 10 }}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip
          formatter={(v) => `${v}%`}
          contentStyle={{ background: '#1c2128', border: '1px solid #30363d', fontSize: 11 }}
          itemStyle={{ color: '#e6edf3' }}
        />
        <Bar dataKey="P"  name="Precision" fill="rgba(63,185,80,0.75)"  radius={[3,3,0,0]} />
        <Bar dataKey="R"  name="Recall"    fill="rgba(210,153,34,0.75)" radius={[3,3,0,0]} />
        <Bar dataKey="F1" name="F1"         fill="rgba(88,166,255,0.8)"  radius={[3,3,0,0]} />
        <Legend
          iconSize={8}
          wrapperStyle={{ fontSize: 10, color: '#8b9199', paddingTop: 4 }}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

// 评估 Tab
function EvalStats() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  const load = () => {
    if (fetched) return
    setLoading(true)
    evalApi.getMetrics()
      .then(setData)
      .catch(console.error)
      .finally(() => { setLoading(false); setFetched(true) })
  }

  useEffect(() => { load() }, []) // eslint-disable-line

  if (loading) return <div className={styles.loading}><Spin /></div>

  if (!data || data.status === 'not_ready') {
    return (
      <div style={{ padding: '12px 4px' }}>
        <Alert
          type="info"
          showIcon
          message="评估数据尚未生成"
          description={
            <div style={{ fontSize: 12 }}>
              请依次运行以下命令：<br />
              <code>python scripts/generate_annotation_samples.py</code><br />
              <code>python scripts/evaluate.py</code>
            </div>
          }
          style={{ background: '#1c2128', border: '1px solid #1f6feb', borderRadius: 8 }}
        />
      </div>
    )
  }

  const { ner = {}, re = {}, total_samples = 0 } = data

  return (
    <>
      <div className={styles.evalSamples}>评估样本：<strong>{total_samples}</strong> 条</div>

      <div className={styles.chartTitle}>NER 命名实体识别</div>
      <MetricsCards overall={ner.overall} />
      <div className={styles.chartTitle} style={{ marginTop: 10 }}>分实体类型 P/R/F1</div>
      <TypeBarChart byType={ner.by_type} height={200} />

      <div className={styles.chartTitle} style={{ marginTop: 14 }}>RE 关系抽取</div>
      <MetricsCards overall={re.overall} />
      <div className={styles.chartTitle} style={{ marginTop: 10 }}>分关系类型 P/R/F1</div>
      <TypeBarChart byType={re.by_rel} height={220} />
    </>
  )
}

export default function StatsPanel() {
  const tabItems = [
    {
      key:      'graph',
      label:    <span>图谱</span>,
      children: <GraphStats />,
    },
    {
      key:      'eval',
      label:    <span><ExperimentOutlined style={{ marginRight: 4 }} />评估</span>,
      children: <EvalStats />,
    },
  ]

  return (
    <div className={styles.panel}>
      <Tabs
        defaultActiveKey="graph"
        size="small"
        items={tabItems}
        tabBarStyle={{ marginBottom: 8, borderBottom: '1px solid #30363d' }}
      />
    </div>
  )
}
