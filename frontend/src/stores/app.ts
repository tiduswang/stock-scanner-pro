import { defineStore } from 'pinia'
import { API } from '@/api/http'

export const useAppStore = defineStore('app', {
  state: () => ({
    weights: { technical: 0.45, fundamental: 0.35, sentiment: 0.20 },
    scoreThreshold: 70,
    markets: { A: 'A股', HK: '港股', ETF: 'ETF' },
    sectors: [] as string[],
    ollama: { base_url: 'http://127.0.0.1:11434', model: 'qwen2.5:7b', timeout: 300 },
    ollamaStatus: { ok: false, msg: '未检查', available_models: [] as string[] },
  }),
  actions: {
    async loadConfig() {
      try {
        const res = await API.config()
        const d = res.data
        this.weights = d.weights
        this.scoreThreshold = d.score_threshold
        this.markets = d.markets
        this.sectors = d.sectors || []
        this.ollama = d.ollama
      } catch (e) {
        console.warn('加载默认配置失败，使用内置值', e)
      }
    },
    async checkOllama(cfg?: any) {
      try {
        const res = await API.checkOllama(cfg || this.ollama)
        this.ollamaStatus = res.data
        return res.data
      } catch (e: any) {
        this.ollamaStatus = { ok: false, msg: e.message || '检查失败', available_models: [] }
        return this.ollamaStatus
      }
    },
  },
})
