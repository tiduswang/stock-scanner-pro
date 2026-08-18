<template>
  <n-space vertical size="16" style="width:100%">
    <n-card :bordered="false" size="small">
      <n-space justify="space-between" align="center">
        <n-space align="center" size="20">
          <n-avatar size="large" round style="background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);color:#fff;font-weight:800">
            {{ (name || code).slice(0,1) }}
          </n-avatar>
          <div>
            <n-space align="center">
              <n-gradient-text type="danger" style="font-size:24px;font-weight:800">{{ name || '加载中...' }}</n-gradient-text>
              <n-tag round>{{ code }}</n-tag>
              <n-tag round type="success" v-if="market==='A'">A股</n-tag>
              <n-tag round type="warning" v-else-if="market==='HK'">港股</n-tag>
              <n-tag round type="info" v-else>ETF</n-tag>
            </n-space>
            <n-space style="margin-top:6px">
              <n-statistic label="现价" :value="snapshot.price || 0" :precision="3" />
              <n-statistic label="涨跌幅" :value="snapshot.change_pct || 0" :precision="2" suffix="%"
                :value-style="{ color: (snapshot.change_pct || 0) >= 0 ? '#e74c3c' : '#27ae60', fontWeight: 700 }" />
              <n-statistic label="总市值(亿)" :value="Math.round((snapshot.market_cap || 0)/1e8)" />
              <n-statistic label="换手%" :value="snapshot.turnover_rate || 0" :precision="2" suffix="%" />
              <n-statistic label="市盈率TTM" :value="snapshot.pe || 0" :precision="2" />
              <n-statistic label="市净率" :value="snapshot.pb || 0" :precision="2" />
            </n-space>
          </div>
        </n-space>
        <n-space>
          <n-button @click="$router.back()">← 返回</n-button>
          <n-button type="primary" :loading="aiLoading" @click="doAIDeep">🤖 AI深度解读</n-button>
        </n-space>
      </n-space>
    </n-card>

    <n-grid :cols="24" :x-gap="16" :y-gap="16">
      <n-gi :span="8">
        <n-card :bordered="false" size="small" title="综合评分">
          <n-space vertical size="12" align="center" style="width:100%">
            <v-chart :option="radarOption" style="height:260px;width:100%" autoresize />
            <n-tag :style="{background: ratingColor + '22', color: ratingColor, border: '1px solid ' + ratingColor}" round size="large" style="font-weight:800;padding:4px 14px">
              评级 {{ score.rating || '-' }} · {{ score.rating_desc || '' }}
            </n-tag>
            <div style="font-size:13px;color:#606266">
              技术面权重 {{ (app.weights.technical*100).toFixed(0) }}% / 
              基本面 {{ (app.weights.fundamental*100).toFixed(0) }}% / 
              情绪面 {{ (app.weights.sentiment*100).toFixed(0) }}%
            </div>
          </n-space>
        </n-card>
      </n-gi>

      <n-gi :span="16">
        <n-card :bordered="false" size="small" title="买卖决策（T+1）">
          <n-descriptions :column="3" bordered size="small" label-placement="left">
            <n-descriptions-item label="操作建议">
              <span :class="'pill pill-' + (buySell.action || 'watch')" style="font-weight:700;font-size:14px;padding:4px 12px">{{ buySell.action_cn || '-' }}</span>
            </n-descriptions-item>
            <n-descriptions-item label="建议仓位">{{ buySell.position_suggestion || '根据风险偏好自行决策' }}</n-descriptions-item>
            <n-descriptions-item label="建议持有期">{{ buySell.time_horizon || '-' }}</n-descriptions-item>
            <n-descriptions-item label="买入点">
              <span v-if="buySell.buy_point">{{ buySell.buy_point.description }}</span>
              <span v-else style="color:#909399">暂不建议买入</span>
            </n-descriptions-item>
            <n-descriptions-item label="止损价">
              <n-tag type="error" v-if="buySell.stop_loss">{{ buySell.stop_loss }}</n-tag>
              <span v-else style="color:#909399">-</span>
            </n-descriptions-item>
            <n-descriptions-item label="止盈目标">
              <span v-if="buySell.take_profit">{{ buySell.take_profit.description }}</span>
              <span v-else style="color:#909399">-</span>
            </n-descriptions-item>
          </n-descriptions>

          <n-divider>推荐理由 / 风险</n-divider>
          <n-grid :cols="2" :x-gap="12">
            <n-gi>
              <n-alert type="success" title="✅ 买入逻辑"><ul style="margin:0;padding-left:18px"><li v-for="(x,i) in buySell.reasons_buy||[]" :key="i">{{ x }}</li></ul></n-alert>
            </n-gi>
            <n-gi>
              <n-alert type="error" title="⚠️ 风险/卖出逻辑"><ul style="margin:0;padding-left:18px"><li v-for="(x,i) in (buySell.reasons_sell||[]).concat(buySell.risk_warnings||[])" :key="i">{{ x }}</li></ul></n-alert>
            </n-gi>
          </n-grid>

          <n-alert type="info" style="margin-top:10px" title="T+1 交易提醒">
            <ul style="margin:6px 0;padding-left:18px"><li v-for="(t,i) in buySell.t1_tips||[]" :key="i">{{ t }}</li></ul>
          </n-alert>
        </n-card>
      </n-gi>

      <n-gi :span="14">
        <n-card :bordered="false" size="small" title="K线（近半年）">
          <v-chart v-if="kline.length" :option="klineOption" style="height:360px" autoresize />
          <n-empty v-else description="暂无K线数据" />
        </n-card>
      </n-gi>

      <n-gi :span="10">
        <n-card :bordered="false" size="small" title="技术面指标">
          <n-descriptions :column="2" bordered size="small">
            <n-descriptions-item label="MA5">{{ tech.indicators?.ma?.ma5 ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="MA20">{{ tech.indicators?.ma?.ma20 ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="MA60">{{ tech.indicators?.ma?.ma60 ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="MA250">{{ tech.indicators?.ma?.ma250 ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="DIF/MACD">{{ tech.indicators?.macd?.dif ?? '-' }} / {{ tech.indicators?.macd?.macd ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="RSI(14)">{{ tech.indicators?.rsi ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="布林上轨">{{ tech.indicators?.boll?.up ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="布林下轨">{{ tech.indicators?.boll?.low ?? '-' }}</n-descriptions-item>
            <n-descriptions-item label="趋势">{{ tech.indicators?.trend === 'bull' ? '多头 ↑' : tech.indicators?.trend === 'bear' ? '空头 ↓' : '震荡 -' }}</n-descriptions-item>
            <n-descriptions-item label="量比(vs MA20)">{{ (tech.indicators?.volume?.vol_ratio ?? '-') }}</n-descriptions-item>
          </n-descriptions>
        </n-card>
      </n-gi>

      <n-gi :span="24">
        <n-card :bordered="false" size="small" title="🤖 AI 深度解读报告">
          <template #header-extra>
            <n-space>
              <n-button :loading="aiLoading" type="primary" @click="doAIDeep">{{ aiReport ? '重新生成' : '生成报告' }}</n-button>
              <n-text depth="3" style="font-size:12px">基于本地 Ollama 模型: {{ app.ollama.model }}</n-text>
            </n-space>
          </template>
          <n-spin v-if="aiLoading" style="display:block;padding:40px;text-align:center">AI 生成中，请耐心等待...</n-spin>
          <div v-else-if="aiReport" class="ai-report" v-html="formatMD(aiReport)"></div>
          <n-empty v-else description="点击右上角【生成报告】让 Ollama 给出专业解读" />
        </n-card>
      </n-gi>
    </n-grid>
  </n-space>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CandlestickChart, LineChart, BarChart, RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, RadarComponent, VisualMapComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { API } from '@/api/http'
import { useAppStore } from '@/stores/app'

use([CanvasRenderer, CandlestickChart, LineChart, BarChart, RadarChart, GridComponent, TooltipComponent, DataZoomComponent, LegendComponent, RadarComponent, VisualMapComponent])

const route = useRoute()
const msg = useMessage()
const app = useAppStore()
const code = computed(() => String(route.params.code || ''))
const market = computed<any>(() => (route.query.market as string) || 'A')
const name = ref((route.query.name as string) || '')

const score = reactive<any>({ scores: {}, rating: '-' })
const snapshot = reactive<any>({ price: 0 })
const buySell = reactive<any>({ t1_tips: [] })
const tech = reactive<any>({ indicators: {} })
const kline = ref<any[]>([])
const aiReport = ref('')
const aiLoading = ref(false)
const loading = ref(false)

const ratingColor = computed(() => ({ S: '#e74c3c', A: '#e67e22', B: '#f1c40f', C: '#3498db', D: '#95a5a6', E: '#7f8c8d' }[score.rating] || '#ccc'))

async function loadAnalyze() {
  loading.value = true
  try {
    const res = await API.analyzeStock({ code: code.value, market: market.value, include_kline: true, kline_days: 180 })
    const d = res.data || {}
    Object.assign(score, d.score || {})
    Object.assign(snapshot, d.score?.snapshot || {})
    Object.assign(buySell, d.buy_sell || {})
    Object.assign(tech, d.score?.technical || {})
    kline.value = d.kline || []
    if (!name.value && d.score?.name) name.value = d.score.name
    // 如果路由传了 autoAI=1，自动跑AI分析
    if (route.query.autoAI === '1') doAIDeep()
  } catch (e: any) { msg.error('加载分析失败: ' + e.message) }
  finally { loading.value = false }
}

async function doAIDeep() {
  aiLoading.value = true
  aiReport.value = ''
  try {
    const res = await API.aiDeep({ code: code.value, market: market.value, score_res: score })
    aiReport.value = res.data.ai_report || ''
    msg.success('AI报告生成完成')
  } catch (e: any) { msg.error('AI分析失败: ' + e.message) }
  finally { aiLoading.value = false }
}

function formatMD(s: string): string {
  let html = (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/^### (.+)$/gm, '<h4 style="margin:16px 0 8px;color:#303133;border-left:3px solid #3498db;padding-left:8px">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 style="margin:20px 0 10px;color:#303133;border-left:4px solid #667eea;padding-left:10px">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 style="margin:24px 0 12px;color:#303133">$1</h2>')
  html = html.replace(/**(.+?)**/g, '<strong style="color:#e67e22">$1</strong>')
  html = html.replace(/^- (.+)$/gm, '<li style="margin-left:18px">$1</li>')
  html = html.replace(/^d+. (.+)$/gm, '<li style="margin-left:18px">$1</li>')
  html = html.replace(/

/g, '</p><p style="margin:6px 0">')
  html = html.replace(/
/g, '<br/>')
  return '<p style="margin:6px 0">' + html + '</p>'
}

// ===== ECharts: 雷达图 =====
const radarOption = computed(() => ({
  tooltip: {},
  radar: {
    indicator: [
      { name: '技术面', max: 100 },
      { name: '基本面', max: 100 },
      { name: '情绪面', max: 100 },
      { name: '综合分', max: 100 },
    ],
    center: ['50%', '58%'],
    radius: '68%',
    splitNumber: 4,
  },
  series: [{
    type: 'radar',
    data: [{
      value: [ score.scores?.technical || 0, score.scores?.fundamental || 0, score.scores?.sentiment || 0, score.scores?.comprehensive_adjusted || 0 ],
      name: '得分',
      areaStyle: { color: 'rgba(102,126,234,0.3)' },
      lineStyle: { color: '#667eea' },
      itemStyle: { color: '#764ba2' },
    }],
  }],
}))

// ===== ECharts: K线 + MA =====
const klineOption = computed(() => {
  const k = kline.value || []
  const dates = k.map(r => r.date)
  const kdata = k.map(r => [r.open, r.close, r.low, r.high])
  const vols = k.map(r => r.volume)
  const colors = k.map(r => r.close >= r.open ? '#e74c3c' : '#27ae60')
  const ma = (p: number) => {
    const arr: any[] = []
    for (let i = 0; i < k.length; i++) {
      if (i + 1 < p) { arr.push(null); continue }
      let s = 0; let c = 0
      for (let j = i - p + 1; j <= i; j++) { s += k[j].close; c++ }
      arr.push(c ? +(s/c).toFixed(3) : null)
    }
    return arr
  }
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', 'MA5', 'MA20', 'MA60'], top: 4 },
    grid: [{ left: '6%', right: '3%', top: 40, height: '55%' }, { left: '6%', right: '3%', top: '72%', height: '18%' }],
    xAxis: [{ type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } }, { type: 'category', data: dates, gridIndex: 1 }],
    yAxis: [{ scale: true, gridIndex: 0 }, { gridIndex: 1, axisLabel: { show: false } }],
    dataZoom: [{ type: 'inside', xAxisIndex: [0,1], start: 60, end: 100 }, { type: 'slider', xAxisIndex: [0,1], bottom: 0, start: 60, end: 100 }],
    series: [
      { name: 'K线', type: 'candlestick', data: kdata, itemStyle: { color: '#e74c3c', color0: '#27ae60', borderColor: '#e74c3c', borderColor0: '#27ae60' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA5', type: 'line', data: ma(5), smooth: false, symbol: 'none', lineStyle: { width: 1, color: '#f1c40f' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA20', type: 'line', data: ma(20), smooth: false, symbol: 'none', lineStyle: { width: 1, color: '#3498db' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: 'MA60', type: 'line', data: ma(60), smooth: false, symbol: 'none', lineStyle: { width: 1, color: '#9b59b6' }, xAxisIndex: 0, yAxisIndex: 0 },
      { name: '成交量', type: 'bar', data: vols, xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: (p: any) => colors[p.dataIndex] || '#ccc' } },
    ],
  }
})

onMounted(loadAnalyze)
</script>

<style scoped>
.ai-report { font-size: 14px; line-height: 1.8; color: #303133; padding: 8px; }
</style>
