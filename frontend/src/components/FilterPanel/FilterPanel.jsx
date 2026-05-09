/**
 * FilterPanel.jsx — 实体类型/关系类型过滤面板
 */
import React from 'react'
import { Checkbox, Divider } from 'antd'
import { NODE_COLORS, REL_LABELS } from '../GraphCanvas/graphStyles'
import styles from './FilterPanel.module.css'

const NODE_TYPES = [
  { key: 'Vehicle',    label: '车辆' },
  { key: 'Component',  label: '零部件' },
  { key: 'Fault',      label: '故障' },
  { key: 'Symptom',    label: '症状' },
  { key: 'RepairStep', label: '维修步骤' },
  { key: 'Tool',       label: '工具' },
  { key: 'System',     label: '系统' },
  { key: 'Parameter',  label: '参数' },
]

const REL_TYPES = Object.entries(REL_LABELS).map(([key, label]) => ({ key, label }))

export default function FilterPanel({ visibleNodes, visibleRels, onChange }) {
  const toggleNode = (key) => {
    const next = visibleNodes.includes(key)
      ? visibleNodes.filter((k) => k !== key)
      : [...visibleNodes, key]
    onChange?.({ visibleNodes: next, visibleRels })
  }

  const toggleRel = (key) => {
    const next = visibleRels.includes(key)
      ? visibleRels.filter((k) => k !== key)
      : [...visibleRels, key]
    onChange?.({ visibleNodes, visibleRels: next })
  }

  const allNodesChecked = visibleNodes.length === NODE_TYPES.length
  const allRelsChecked  = visibleRels.length === REL_TYPES.length

  return (
    <div className={styles.panel}>
      <div className={styles.section}>
        <div className={styles.sectionTitle}>
          <span>节点类型</span>
          <Checkbox
            checked={allNodesChecked}
            indeterminate={visibleNodes.length > 0 && !allNodesChecked}
            onChange={(e) => onChange?.({
              visibleNodes: e.target.checked ? NODE_TYPES.map((t) => t.key) : [],
              visibleRels,
            })}
          >
            全选
          </Checkbox>
        </div>
        {NODE_TYPES.map((t) => (
          <div key={t.key} className={styles.item} onClick={() => toggleNode(t.key)}>
            <span
              className={styles.dot}
              style={{ background: NODE_COLORS[t.key] }}
            />
            <span className={styles.label}>{t.label}</span>
            <Checkbox
              checked={visibleNodes.includes(t.key)}
              onChange={() => toggleNode(t.key)}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        ))}
      </div>

      <Divider style={{ borderColor: '#30363d', margin: '8px 0' }} />

      <div className={styles.section}>
        <div className={styles.sectionTitle}>
          <span>关系类型</span>
          <Checkbox
            checked={allRelsChecked}
            indeterminate={visibleRels.length > 0 && !allRelsChecked}
            onChange={(e) => onChange?.({
              visibleNodes,
              visibleRels: e.target.checked ? REL_TYPES.map((t) => t.key) : [],
            })}
          >
            全选
          </Checkbox>
        </div>
        {REL_TYPES.map((t) => (
          <div key={t.key} className={styles.item} onClick={() => toggleRel(t.key)}>
            <span className={styles.label} style={{ color: '#8b9199' }}>{t.label}</span>
            <Checkbox
              checked={visibleRels.includes(t.key)}
              onChange={() => toggleRel(t.key)}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
