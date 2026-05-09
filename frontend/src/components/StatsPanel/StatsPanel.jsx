/**
 * StatsPanel.jsx — 图谱统计仪表盘
 * 使用 Recharts 绘制节点/关系类型分布饼图
 */
import React, { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { Statistic, Row, Col, Spin } from 'antd'
import { NodeIndexOutlined, ShareAltOutlined } from '@ant-design/icons'
import { statsApi } from '../../services/api'
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

export default function StatsPanel() {
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
    <div className={styles.panel}>
      {/* 总计 */}
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

      {/* 节点类型分布 */}
      <div className={styles.chartTitle}>节点类型分布</div>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={nodeData}
            cx="50%"
            cy="50%"
            outerRadius={70}
            dataKey="value"
            labelLine={false}
            label={renderCustomLabel}
          >
            {nodeData.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: '#1c2128', border: '1px solid #30363d', fontSize: 12 }}
            itemStyle={{ color: '#e6edf3' }}
          />
          <Legend
            iconSize={8}
            wrapperStyle={{ fontSize: 10, color: '#8b9199' }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* 关系类型分布 */}
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
    </div>
  )
}
