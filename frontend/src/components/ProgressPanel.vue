<template>
  <n-card :bordered="false" size="small" class="progress-panel">
    <template #header>
      <n-space justify="space-between" align="center">
        <div style="font-weight:600">扫描进度</div>
        <n-tag v-if="progress.status === 'running'" type="info" round>运行中</n-tag>
        <n-tag v-else-if="progress.status === 'done'" type="success" round>完成</n-tag>
        <n-tag v-else-if="progress.status === 'error'" type="error" round>异常</n-tag>
        <n-tag v-else round>准备</n-tag>
      </n-space>
    </template>

    <n-space vertical size="small">
      <n-grid :cols="3" :x-gap="12">
        <n-gi><n-statistic label="总数" :value="progress.total || 0" /></n-gi>
        <n-gi><n-statistic label="已处理" :value="progress.processed || 0" /></n-gi>
        <n-gi><n-statistic label="通过筛选" :value="progress.passed_filter || 0" /></n-gi>
      </n-grid>

      <div>
        <n-space align="center" justify="space-between" style="margin-bottom:4px">
          <n-text depth="3" style="font-size:12px">{{ progress.current_stage || '等待启动' }}</n-text>
          <n-text depth="2" style="font-size:12px">
            耗时 {{ progress.elapsed_text || '0秒' }} · {{ progress.eta_text || '' }}
          </n-text>
        </n-space>
        <n-progress type="line" :percentage="progress.progress_pct || 0" :indicator-placement="inside" />
        <n-text depth="3" style="font-size:12px">
          当前: {{ progress.current_code || '-' }} {{ progress.processed }}/{{ progress.total }}
          · 速度 {{ (progress.speed_per_sec || 0).toFixed(2) }} 只/秒
          · 失败 {{ progress.failed || 0 }}
        </n-text>
      </div>

      <n-divider style="margin:6px 0">阶段日志</n-divider>
      <div class="log-box">
        <n-scrollbar style="max-height: 220px">
          <n-timeline size="small">
            <n-timeline-item
              v-for="(lg, i) in (progress.stage_log || []).slice(-50)"
              :key="i"
              :type="logType(lg.msg)"
              :title="lg.time"
            >
              <n-text style="font-size:12px">{{ lg.msg }}</n-text>
            </n-timeline-item>
          </n-timeline>
        </n-scrollbar>
      </div>
    </n-space>
  </n-card>
</template>

<script setup lang="ts">
const props = defineProps<{ progress: any }>()
function logType(msg: string) {
  if (!msg) return 'default'
  if (msg.includes('异常') || msg.includes('错误') || msg.includes('失败')) return 'error'
  if (msg.includes('完成') || msg.includes('通过')) return 'success'
  if (msg.includes('AI')) return 'info'
  if (msg.includes('开始')) return 'warning'
  return 'default'
}
</script>

<style scoped>
.log-box { border: 1px solid #f0f0f0; border-radius: 6px; padding: 8px; background: #fafbfc; }
</style>
