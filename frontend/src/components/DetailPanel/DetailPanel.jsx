/**
 * DetailPanel.jsx — 节点/边属性详情面板
 * 点击节点或边后在右侧展示完整属性
 */
import React from 'react'
import { Drawer, Tag, Descriptions, Button, Typography } from 'antd'
import { NODE_COLORS } from '../GraphCanvas/graphStyles'
import styles from './DetailPanel.module.css'

const { Text, Title } = Typography

const TYPE_LABELS = {
  Vehicle:    '车辆',
  Component:  '零部件',
  Fault:      '故障',
  Symptom:    '症状',
  RepairStep: '维修步骤',
  Tool:       '工具',
  System:     '系统',
  Parameter:  '参数',
}

const PROP_LABELS = {
  name:              '名称',
  brand:             '品牌',
  model:             '型号',
  engine_type:       '发动机类型',
  displacement:      '排量',
  fuel_type:         '燃油类型',
  year:              '年份',
  component_no:      '零件编号',
  system:            '所属系统',
  specs:             '规格',
  material:          '材质',
  description:       '描述',
  fault_code:        '故障码',
  severity:          '严重程度',
  fault_type:        '故障类别',
  observable_method: '观测方式',
  step_no:           '步骤序号',
  operation:         '操作说明',
  precaution:        '注意事项',
  tool_spec:         '规格型号',
  tool_type:         '工具类型',
  usage:             '用途',
  value:             '参数值',
  unit:              '单位',
  source_doc:        '来源文档',
  confidence:        '置信度',
  source_sent:       '来源句子',
}

const SEVERITY_COLOR = { low: 'green', medium: 'orange', high: 'red' }

export default function DetailPanel({ selection, onClose, onExpand }) {
  if (!selection) return null

  const isNode = selection.type === 'node'
  const data   = selection.data || {}
  const props  = data.props || {}

  const color = NODE_COLORS[data.label] || '#7f8c8d'

  return (
    <Drawer
      title={null}
      placement="right"
      onClose={onClose}
      open={!!selection}
      width={320}
      className={styles.drawer}
      styles={{
        header: { display: 'none' },
        body:   { padding: 0, background: '#1c2128' },
        mask:   { background: 'transparent' },
      }}
    >
      {/* 顶部标题区 */}
      <div className={styles.header} style={{ borderLeft: `4px solid ${color}` }}>
        <div className={styles.headerMeta}>
          <Tag
            style={{
              background: color + '22',
              color,
              border: `1px solid ${color}44`,
              fontSize: 11,
            }}
          >
            {isNode ? (TYPE_LABELS[data.label] || data.label) : '关系'}
          </Tag>
          {isNode && (
            <Button
              size="small"
              type="link"
              onClick={() => onExpand?.(data.name)}
              style={{ color: '#4A90D9', padding: '0 4px', fontSize: 11 }}
            >
              展开子图
            </Button>
          )}
        </div>
        <Title level={5} style={{ color: '#e6edf3', margin: '6px 0 0', fontSize: 15 }}>
          {data.name || data.type || 'Unknown'}
        </Title>
      </div>

      {/* 属性列表 */}
      <div className={styles.body}>
        <Descriptions
          column={1}
          size="small"
          labelStyle={{ color: '#8b9199', fontSize: 12, padding: '4px 0' }}
          contentStyle={{ color: '#e6edf3', fontSize: 12, padding: '4px 0' }}
        >
          {isNode && Object.entries(props)
            .filter(([k, v]) => v && k !== 'name')
            .map(([k, v]) => (
              <Descriptions.Item key={k} label={PROP_LABELS[k] || k}>
                {k === 'severity' ? (
                  <Tag color={SEVERITY_COLOR[v] || 'default'}>{v}</Tag>
                ) : (
                  <Text style={{ color: '#e6edf3', fontSize: 12 }}>{String(v)}</Text>
                )}
              </Descriptions.Item>
            ))
          }
          {!isNode && (
            <>
              <Descriptions.Item label="关系类型">
                <Tag color="blue">{data.type}</Tag>
              </Descriptions.Item>
              {data.props && Object.entries(data.props)
                .filter(([k, v]) => v && !['id', 'source', 'target', 'type'].includes(k))
                .map(([k, v]) => (
                  <Descriptions.Item key={k} label={PROP_LABELS[k] || k}>
                    <Text style={{ color: '#e6edf3', fontSize: 12 }}>{String(v)}</Text>
                  </Descriptions.Item>
                ))
              }
            </>
          )}
        </Descriptions>
      </div>
    </Drawer>
  )
}
