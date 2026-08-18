<template>
  <n-data-table
    :columns="columns"
    :data="rows"
    :loading="loading"
    :pagination="{ pageSize: 10 }"
    size="small"
    :row-class-name="rowClass"
    @row-click="onRowClick"
    striped
  />
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { NTag, NButton, NSpace, NAvatar, NGradientText } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

const props = defineProps<{
  data: any[]
  loading?: boolean
}>()
const emit = defineEmits<{ (e: 'select', row: any): void; (e: 'ai', row: any): void }>()

const rows = computed(() => props.data || [])
function rowClass(r: any) { return 'clickable' }
function onRowClick(r: any) { emit('select', r) }

const ratingColor = (r: string) => ({ S: '#e74c3c', A: '#e67e22', B: '#f1c40f', C: '#3498db', D: '#95a5a6', E: '#7f8c8d' }[r] || '#ccc')
const scoreClass = (r: string) => 'score-' + r.toLowerCase()

function actionCell(_: any, row: any) {
  return h(NSpace, {}, () => [
    h(NButton, { size: 'tiny', type: 'primary', onClick: (e: Event) => { e.stopPropagation(); emit('select', row) } }, () => '详情'),
    h(NButton, { size: 'tiny', type: 'info', onClick: (e: Event) => { e.stopPropagation(); emit('ai', row) } }, () => 'AI分析'),
  ])
}

const columns: DataTableColumns<any> = [
  { title: '排名', key: 'idx', width: 56, render: (_, __, i) => i + 1 },
  {
    title: '代码 / 名称', key: 'name', width: 180,
    render: (_, r) => h(NSpace, { vertical: true, size: 2 }, () => [
      h('div', { style: 'font-weight:600' }, r.name || '-'),
      h('div', { style: 'font-size:12px;color:#909399' }, [
        r.code, ' · ', h(NTag, { size: 'tiny', type: r.market === 'A' ? 'success' : r.market === 'HK' ? 'warning' : 'info' }, () => r.market_name || r.market)
      ]),
    ]),
  },
  {
    title: '综合评分', key: 'score', width: 110,
    render: (_, r) => h(NSpace, { vertical: true, size: 0, align: 'center' }, () => [
      h(NGradientText, { type: 'danger', size: 22, style: 'font-weight:800' }, () => r.score?.toFixed(1)),
      h(NTag, { size: 'tiny', round, style: 'border:none;background:' + ratingColor(r.rating) + '22;color:' + ratingColor(r.rating) }, () => '评级 ' + (r.rating || '-')),
    ]),
  },
  {
    title: '三面得分', key: 'scores', width: 220,
    render: (_, r) => {
      const s = r.scores || {}
      return h(NSpace, { vertical: true, size: 2 }, () => [
        miniBar('技术', s.technical, '#3498db'),
        miniBar('基本', s.fundamental, '#27ae60'),
        miniBar('情绪', s.sentiment, '#e67e22'),
      ])
      function miniBar(label: string, v: number, c: string) {
        const pct = Math.max(0, Math.min(100, v || 0))
        return h('div', { style: 'display:flex;align-items:center;gap:6px;font-size:12px' }, [
          h('span', { style: 'width:28px;color:#606266' }, label),
          h('div', { style: 'flex:1;height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden' }, [
            h('div', { style: 'width:' + pct + '%;height:100%;background:' + c + ';transition:width .3s' })
          ]),
          h('span', { style: 'width:32px;text-align:right;color:#303133' }, (v || 0).toFixed(0)),
        ])
      }
    },
  },
  {
    title: '涨跌 / 现价', key: 'chg', width: 140,
    render: (_, r) => {
      const s = r.snapshot || {}
      const chg = s.change_pct
      const color = chg > 0 ? '#e74c3c' : chg < 0 ? '#27ae60' : '#909399'
      return h(NSpace, { vertical: true, size: 0 }, () => [
        h('div', { style: 'font-weight:600;color:' + color }, s.price?.toFixed(3) || '-'),
        h('div', { style: 'font-size:12px;color:' + color }, (chg >= 0 ? '+' : '') + (chg?.toFixed(2) || '0') + '%'),
      ])
    },
  },
  {
    title: '建议', key: 'action', width: 110,
    render: (_, r) => {
      const a = (r.buy_sell || {}).action || ''
      const map: any = { buy: ['买入', 'pill-buy'], sell: ['卖出/回避', 'pill-sell'], hold: ['持有', 'pill-hold'], watch: ['观望', 'pill-watch'] }
      const [t, c] = map[a] || ['-', 'pill-watch']
      return h('span', { class: 'pill ' + c }, t)
    },
  },
  { title: '操作', key: 'act', width: 150, render: actionCell },
]
</script>

<style scoped>
div.clickable { cursor: pointer; }
</style>
