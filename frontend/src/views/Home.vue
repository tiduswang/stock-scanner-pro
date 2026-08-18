<template>
  <n-grid :cols="24" :x-gap="16" :y-gap="16">
    <!-- 左侧搜索与筛选 -->
    <n-gi :span="7">
      <n-space vertical size="16" style="width:100%">
        <!-- 搜索 -->
        <n-card :bordered="false" size="small" title="股票搜索（代码/拼音/名称）">
          <n-space vertical style="width:100%">
            <n-input
              v-model:value="q"
              placeholder="支持 代码 000001 / 拼音首字母 PAYH / 中文 平安银行"
              size="large"
              clearable
              @input="onSearch"
              @keyup.enter="doSearch"
            >
              <template #prefix>🔍</template>
            </n-input>
            <n-checkbox-group v-model:value="searchMarkets">
              <n-space>
                <n-checkbox value="A">A股</n-checkbox>
                <n-checkbox value="HK">港股</n-checkbox>
                <n-checkbox value="ETF">ETF</n-checkbox>
              </n-space>
            </n-checkbox-group>

            <div v-if="searchLoading" style="padding:8px 4px"><n-spin size="small" /> 搜索中...</div>
            <n-scrollbar v-else style="max-height:300px">
              <n-list bordered size="small" clickable>
                <n-list-item v-for="it in searchResult" :key="it.code + it.market" @click="goAnalyze(it)">
                  <n-space align="center" justify="space-between" style="width:100%">
                    <div>
                      <div style="font-weight:600">{{ it.name }}</div>
                      <div style="font-size:12px;color:#909399">{{ it.code }} · {{ it.first_letter }}</div>
                    </div>
                    <n-tag size="small" :type="it.market === 'A' ? 'success' : it.market === 'HK' ? 'warning' : 'info'">{{ it.market }}</n-tag>
                  </n-space>
                </n-list-item>
                <n-list-item v-if="searchResult.length === 0 && q">
                  <n-text depth="3">暂无匹配结果</n-text>
                </n-list-item>
              </n-list>
            </n-scrollbar>
          </n-space>
        </n-card>

        <!-- 参数面板 -->
        <ParamsPanel ref="paramsPanelRef" @change="onParamsChange" />

        <!-- 选股模式 -->
        <n-card :bordered="false" size="small" title="选股模式设置">
          <n-form label-placement="left" label-width="90px" size="small">
            <n-form-item label="选股市场">
              <n-checkbox-group v-model:value="scanMarkets">
                <n-space>
                  <n-checkbox value="A">A股</n-checkbox>
                  <n-checkbox value="HK">港股</n-checkbox>
                  <n-checkbox value="ETF">ETF</n-checkbox>
                </n-space>
              </n-checkbox-group>
            </n-form-item>
            <n-form-item label="板块筛选(A股)">
              <n-select v-model:value="sector" :options="sectorOptions" clearable placeholder="不选=全市场" style="width:100%" />
            </n-form-item>
            <n-form-item label="自定义代码">
              <n-input
                v-model:value="customCodes"
                type="textarea"
                placeholder="多个代码用逗号或空格分隔，如 000001,600519,510300"
                :autosize="{ minRows: 2, maxRows: 4 }"
              />
            </n-form-item>
            <n-form-item label="买卖决策">
              <n-switch v-model:value="includeBuySell" /> 含买卖点建议（慢一点）
            </n-form-item>

            <n-divider style="margin:4px 0 12px 0" />

            <n-space wrap>
              <n-button type="primary" size="large" :loading="scanning" @click="startNormalScan">
                <template #icon>🎯</template>
                开始量化选股
              </n-button>
              <n-button type="info" size="large" :loading="scanning" @click="startAIScan">
                <template #icon>🤖</template>
                AI 智能选股（Ollama）
              </n-button>
            </n-space>

            <n-space style="margin-top:10px" v-if="!ollamaOk">
              <n-alert type="warning" :show-icon="true">
                未检测到Ollama服务，启动请先安装并拉模型：<br>
                <code>ollama pull qwen2.5:7b</code> 或在.env中修改模型名
              </n-alert>
            </n-space>
          </n-form>
        </n-card>

        <!-- 进度面板 -->
        <ProgressPanel v-if="scanId" :progress="progress" />
      </n-space>
    </n-gi>

    <!-- 右侧结果列表 + AI报告 -->
    <n-gi :span="17">
      <n-tabs type="line" animated>
        <n-tab-pane name="result" tab="选股结果">
          <StockResultTable :data="results" :loading="scanning" @select="goAnalyze" @ai="doSingleAI" />
          <n-card v-if="!results.length && !scanning" :bordered="false" style="margin-top:12px;text-align:center">
            <n-text depth="3">暂无结果，请先开始选股或调整筛选条件</n-text>
          </n-card>
        </n-tab-pane>
        <n-tab-pane name="ai" tab="AI深度分析报告">
          <n-card :bordered="false" size="small">
            <template #header>
              <n-space align="center" justify="space-between">
                <div style="font-weight:600">Ollama AI 组合分析报告</div>
                <n-tag v-if="aiReport" type="success" round>已生成 {{ aiReport.length }} 字</n-tag>
                <n-tag v-else-if="scanning && lastScanIsAI" type="info" round>生成中...</n-tag>
              </n-space>
            </template>
            <n-scrollbar style="max-height:calc(100vh - 260px)">
              <div v-if="aiReport" class="ai-report" v-html="formatMD(aiReport)"></div>
              <n-empty v-else description="请先点击【AI智能选股】，完成后报告将显示于此" />
            </n-scrollbar>
          </n-card>
        </n-tab-pane>
      </n-tabs>
    </n-gi>
  </n-grid>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import ParamsPanel from '@/components/ParamsPanel.vue'
import ProgressPanel from '@/components/ProgressPanel.vue'
import StockResultTable from '@/components/StockResultTable.vue'
import { API, createSSEStream } from '@/api/http'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const msg = useMessage()
const app = useAppStore()

// 搜索
const q = ref('')
const searchMarkets = ref(['A', 'HK', 'ETF'])
const searchResult = ref<any[]>([])
const searchLoading = ref(false)
let _searchTimer: any = null
function onSearch() {
  clearTimeout(_searchTimer)
  if (!q.value || q.value.length < 1) { searchResult.value = []; return }
  _searchTimer = setTimeout(doSearch, 250)
}
async function doSearch() {
  if (!q.value) return
  searchLoading.value = true
  try {
    const res = await API.searchStock(q.value, searchMarkets.value.join(','), 30)
    searchResult.value = res.data.items || []
  } catch (e: any) { msg.error('搜索失败: ' + e.message) }
  finally { searchLoading.value = false }
}

function goAnalyze(it: any) {
  router.push({ name: 'analyze', params: { code: it.code }, query: { market: it.market || 'A', name: it.name || '' } })
}

// 参数
const paramsPanelRef = ref<any>()
const params = reactive<any>({ weights: { technical: 0.45, fundamental: 0.35, sentiment: 0.2 }, scoreThreshold: 70, topN: 50, max_workers: 3, analysisParams: {} })
function onParamsChange(p: any) { Object.assign(params, p) }

// 选股配置
const scanMarkets = ref(['A'])
const sector = ref<string | null>(null)
const customCodes = ref('')
const includeBuySell = ref(true)
const sectorOptions = computed(() => [{ label: '所有板块（慢）', value: '所有板块' }, ...(app.sectors.map(s => ({ label: s, value: s })))])

// 扫描状态
const scanning = ref(false)
const scanId = ref<string>('')
const progress = ref<any>({ stage_log: [], progress_pct: 0 })
const results = ref<any[]>([])
const aiReport = ref('')
const lastScanIsAI = ref(false)
const ollamaOk = computed(() => !!app.ollamaStatus.ok)

let _sse: EventSource | null = null
function closeSSE() { if (_sse) { _sse.close(); _sse = null } }

function buildScanBody() {
  const stock_codes = customCodes.value ? customCodes.value.split(/[,s]+/).filter(Boolean) : undefined
  return {
    markets: scanMarkets.value.length ? scanMarkets.value : ['A'],
    stock_codes,
    sector: sector.value || undefined,
    score_threshold: params.scoreThreshold,
    top_n: params.topN,
    weights: params.weights,
    analysis_params: params.analysisParams,
    max_workers: params.max_workers,
    include_buy_sell: includeBuySell.value,
  }
}

async function startNormalScan() {
  startScan(false)
}
async function startAIScan() {
  if (!ollamaOk.value) {
    const c = await app.checkOllama()
    if (!c.ok) { msg.warning('Ollama未连接，请先启动Ollama服务并拉取模型。仍将先执行量化选股。') }
  }
  startScan(true)
}

async function startScan(isAI: boolean) {
  if (scanning.value) return
  closeSSE()
  scanning.value = true
  lastScanIsAI.value = isAI
  results.value = []
  aiReport.value = ''
  try {
    const body = buildScanBody()
    const res = isAI ? await API.startAIScan({ ...body, ai_mode: 'after_filter' }) : await API.startScan(body)
    scanId.value = res.data.scan_id
    msg.success(isAI ? '已启动 AI 智能选股（量化+AI深度分析）' : '已启动量化选股')
    // 连接SSE
    _sse = createSSEStream('/api/scan/progress/' + encodeURIComponent(scanId.value))
    _sse.addEventListener('progress', (ev: any) => {
      const d = JSON.parse(ev.data || '{}')
      progress.value = d
      if (d.results) results.value = d.results
      if (d.ai_report) aiReport.value = d.ai_report
    })
    _sse.addEventListener('final', (ev: any) => {
      const d = JSON.parse(ev.data || '{}')
      progress.value = d
      results.value = d.results || []
      aiReport.value = d.ai_report || ''
      scanning.value = false
      msg.success('扫描完成，命中 ' + results.value.length + ' 只')
      closeSSE()
    })
    _sse.onerror = () => {
      scanning.value = false
      msg.warning('SSE流断开，可轮询进度查看')
      // 兜底：轮询一次
      setTimeout(() => API.getProgress(scanId.value).then(r => { progress.value = r.data; results.value = r.data.results || []; aiReport.value = r.data.ai_report || '' }), 500)
      closeSSE()
    }
  } catch (e: any) {
    scanning.value = false
    msg.error('启动扫描失败: ' + e.message)
  }
}

function doSingleAI(row: any) {
  router.push({ name: 'analyze', params: { code: row.code }, query: { market: row.market || 'A', name: row.name || '', autoAI: '1' } })
}

function formatMD(s: string): string {
  // 极简markdown转HTML：标题/列表/加粗/换行
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

onMounted(() => { API.hotSuggest('A',5).then(r => searchResult.value = r.data.items) })
</script>

<style scoped>
.ai-report { font-size: 14px; line-height: 1.8; color: #303133; padding: 8px 4px; }
.ai-report h2, .ai-report h3, .ai-report h4 { font-weight: 700; }
</style>
