<template>
  <n-card :bordered="false" size="small" title="分析参数（可调节）">
    <n-form label-placement="left" label-width="120px" size="small">

      <n-divider>权重调节（三面总和=100%）</n-divider>
      <n-form-item label="技术面权重">
        <n-space align="center">
          <n-slider v-model:value="w_tech" :min="0" :max="1" :step="0.05" style="width:100%" />
          <n-statistic :value="Math.round(w_tech * 100)" suffix="%" style="width:60px" />
        </n-space>
      </n-form-item>
      <n-form-item label="基本面权重">
        <n-space align="center">
          <n-slider v-model:value="w_fund" :min="0" :max="1" :step="0.05" style="width:100%" />
          <n-statistic :value="Math.round(w_fund * 100)" suffix="%" style="width:60px" />
        </n-space>
      </n-form-item>
      <n-form-item label="情绪面权重">
        <n-space align="center">
          <n-slider v-model:value="w_sent" :min="0" :max="1" :step="0.05" style="width:100%" />
          <n-statistic :value="Math.round(w_sent * 100)" suffix="%" style="width:60px" />
        </n-space>
      </n-form-item>
      <n-form-item label="总和校验">
        <n-tag :type="totalIs100 ? 'success' : 'warning'">
          当前总和 {{ Math.round(totalPct) }}% {{ totalIs100 ? '✓' : '(推荐=100%)' }}
        </n-tag>
      </n-form-item>

      <n-divider>选股阈值</n-divider>
      <n-form-item label="筛选分数≥">
        <n-slider v-model:value="scoreThreshold" :min="50" :max="90" :step="5" :marks="marks" style="width:100%" />
      </n-form-item>
      <n-form-item label="输出Top N">
        <n-select v-model:value="topN" :options="topNOptions" style="width:100%" />
      </n-form-item>
      <n-form-item label="并发线程数">
        <n-radio-group v-model:value="workers">
          <n-radio :value="1">1</n-radio>
          <n-radio :value="3">3</n-radio>
          <n-radio :value="5">5</n-radio>
          <n-radio :value="8">8</n-radio>
        </n-radio-group>
      </n-form-item>

      <n-divider>技术面参数</n-divider>
      <n-form-item label="RSI超买阈值">
        <n-slider v-model:value="techParams.rsi_overbought" :min="60" :max="90" :step="1" style="width:100%" />
      </n-form-item>
      <n-form-item label="RSI超卖阈值">
        <n-slider v-model:value="techParams.rsi_oversold" :min="10" :max="40" :step="1" style="width:100%" />
      </n-form-item>
    </n-form>
  </n-card>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()
const w_tech = ref(app.weights.technical)
const w_fund = ref(app.weights.fundamental)
const w_sent = ref(app.weights.sentiment)
const scoreThreshold = ref(app.scoreThreshold)
const topN = ref(50)
const topNOptions = [10, 20, 30, 50, 100, 200].map(v => ({ label: v + ' 只', value: v }))
const workers = ref(3)

const techParams = reactive({
  rsi_overbought: 70,
  rsi_oversold: 30,
})

const marks = { 50: '50', 60: '60', 70: '70', 80: '80', 90: '90' }

const totalPct = computed(() => (w_tech.value + w_fund.value + w_sent.value) * 100)
const totalIs100 = computed(() => Math.abs(totalPct.value - 100) < 0.001)

function autoBalance() {
  const s = w_tech.value + w_fund.value + w_sent.value
  if (s > 0) {
    w_tech.value = +(w_tech.value / s).toFixed(2)
    w_fund.value = +(w_fund.value / s).toFixed(2)
    w_sent.value = +(1 - w_tech.value - w_fund.value).toFixed(2)
  }
}

const emit = defineEmits(['change'])
watch([w_tech, w_fund, w_sent, scoreThreshold, topN, workers, techParams], () => {
  emit('change', buildPayload())
}, { deep: true, immediate: true })

function buildPayload() {
  return {
    weights: { technical: w_tech.value, fundamental: w_fund.value, sentiment: w_sent.value },
    scoreThreshold: scoreThreshold.value,
    topN: topN.value,
    max_workers: workers.value,
    analysisParams: {
      technical: {
        rsi_overbought: techParams.rsi_overbought,
        rsi_oversold: techParams.rsi_oversold,
      },
    },
  }
}

defineExpose({ buildPayload, autoBalance })
</script>
