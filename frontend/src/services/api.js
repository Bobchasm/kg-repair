/**
 * 后端接口封装
 */
import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 统一错误提示
http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    console.error('[API Error]', msg)
    return Promise.reject(new Error(msg))
  }
)

export const graphApi = {
  /** 获取概览图（首屏展示） */
  getOverview: (limit = 200) => http.get('/graph/overview', { params: { limit } }),

  /** 以节点为中心展开子图 */
  getSubgraph: (nodeName, hops = 2, maxNodes = 100) =>
    http.get(`/graph/subgraph/${encodeURIComponent(nodeName)}`, {
      params: { hops, max_nodes: maxNodes },
    }),

  /** 分页节点列表 */
  getNodes: (label, skip = 0, limit = 100) =>
    http.get('/graph/nodes', { params: { label, skip, limit } }),
}

export const searchApi = {
  search: (q, limit = 30) => http.get('/search/', { params: { q, limit } }),
}

export const pathApi = {
  shortestPath: (fromNode, toNode) =>
    http.get('/path/shortest', { params: { from_node: fromNode, to_node: toNode } }),
}

export const statsApi = {
  getStats: () => http.get('/stats/'),
}

export const evalApi = {
  getMetrics: () => http.get('/eval/metrics'),
}
