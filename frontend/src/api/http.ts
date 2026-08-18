import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 60_000,
})

export const API = {
  // common
  health: () => http.get('/common/health'),
  config: () => http.get('/common/config'),
  checkOllama: (cfg: any) => http.post('/common/ollama/check', cfg || {}),

  // search
  searchStock: (q: string, markets?: string, limit = 30) =>
    http.get('/search/stock', { params: { q, markets, limit } }),
  hotSuggest: (markets?: string, limit = 10) =>
    http.get('/search/hot', { params: { markets, limit } }),

  // analyze
  analyzeStock: (data: any) => http.post('/analyze/stock', data),
  aiDeep: (data: any) => http.post('/analyze/stock/ai', data),

  // scan
  startScan: (data: any) => http.post('/scan/start', data),
  startAIScan: (data: any) => http.post('/scan/ai/start', data),
  getProgress: (id: string) => http.get(`/scan/progress/${id}`),
}

export function createSSEStream(url: string) {
  return new EventSource(url)
}

export default http
