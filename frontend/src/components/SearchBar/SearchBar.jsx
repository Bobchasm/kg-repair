/**
 * SearchBar.jsx — 实体搜索 + 最短路径查询
 */
import React, { useState, useRef } from 'react'
import { Input, AutoComplete, Button, Space, Tooltip, Divider, message } from 'antd'
import { SearchOutlined, NodeIndexOutlined, SwapOutlined } from '@ant-design/icons'
import { searchApi, pathApi } from '../../services/api'
import { NODE_COLORS } from '../GraphCanvas/graphStyles'
import styles from './SearchBar.module.css'

export default function SearchBar({ onNodeFocus, onPathFound }) {
  // ── 搜索状态 ───────────────────────────────────────────────────
  const [searchVal, setSearchVal]   = useState('')
  const [options, setOptions]       = useState([])
  const [searching, setSearching]   = useState(false)

  // ── 路径查询状态 ───────────────────────────────────────────────
  const [pathMode, setPathMode]     = useState(false)
  const [fromNode, setFromNode]     = useState('')
  const [toNode, setToNode]         = useState('')
  const [pathLoading, setPathLoad]  = useState(false)

  // ── 搜索自动补全 ──────────────────────────────────────────────
  const handleSearch = async (val) => {
    setSearchVal(val)
    if (!val.trim() || val.length < 1) {
      setOptions([])
      return
    }
    setSearching(true)
    try {
      const data = await searchApi.search(val, 20)
      setOptions(
        (data.results || []).map((r) => ({
          value: r.name,
          label: (
            <div className={styles.option}>
              <span
                className={styles.optionTag}
                style={{
                  background: (NODE_COLORS[r.label] || '#7f8c8d') + '22',
                  color: NODE_COLORS[r.label] || '#7f8c8d',
                  borderColor: (NODE_COLORS[r.label] || '#7f8c8d') + '44',
                }}
              >
                {r.label}
              </span>
              <span className={styles.optionName}>{r.name}</span>
            </div>
          ),
          raw: r,
        }))
      )
    } catch {
      setOptions([])
    } finally {
      setSearching(false)
    }
  }

  const handleSelect = (val, option) => {
    onNodeFocus?.(val)
    setSearchVal('')
    setOptions([])
  }

  // ── 最短路径查询 ──────────────────────────────────────────────
  const handleFindPath = async () => {
    if (!fromNode.trim() || !toNode.trim()) {
      message.warning('请输入起点和终点节点名称')
      return
    }
    setPathLoad(true)
    try {
      const data = await pathApi.shortestPath(fromNode.trim(), toNode.trim())
      onPathFound?.(data.path)
      message.success(`找到路径，长度 ${data.length} 步`)
    } catch (err) {
      message.error('路径查询失败：' + err.message)
    } finally {
      setPathLoad(false)
    }
  }

  return (
    <div className={styles.bar}>
      {/* 搜索框 */}
      <AutoComplete
        value={searchVal}
        options={options}
        onSearch={handleSearch}
        onSelect={handleSelect}
        className={styles.searchInput}
        dropdownClassName={styles.dropdown}
      >
        <Input
          prefix={<SearchOutlined style={{ color: '#8b9199' }} />}
          placeholder="搜索节点..."
          allowClear
          style={{ background: '#21262d', borderColor: '#30363d', color: '#e6edf3' }}
        />
      </AutoComplete>

      <Divider type="vertical" style={{ borderColor: '#30363d', height: 24 }} />

      {/* 路径查询切换 */}
      <Tooltip title="最短路径查询">
        <Button
          icon={<NodeIndexOutlined />}
          type={pathMode ? 'primary' : 'text'}
          style={{ color: pathMode ? undefined : '#8b9199' }}
          onClick={() => setPathMode((p) => !p)}
        />
      </Tooltip>

      {pathMode && (
        <>
          <Input
            placeholder="起点节点"
            value={fromNode}
            onChange={(e) => setFromNode(e.target.value)}
            style={{ width: 120, background: '#21262d', borderColor: '#30363d', color: '#e6edf3' }}
          />
          <SwapOutlined style={{ color: '#8b9199' }} />
          <Input
            placeholder="终点节点"
            value={toNode}
            onChange={(e) => setToNode(e.target.value)}
            style={{ width: 120, background: '#21262d', borderColor: '#30363d', color: '#e6edf3' }}
          />
          <Button
            type="primary"
            size="small"
            loading={pathLoading}
            onClick={handleFindPath}
          >
            查找
          </Button>
        </>
      )}
    </div>
  )
}
