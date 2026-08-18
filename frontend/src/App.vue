<template>
  <n-layout style="min-height:100vh">
    <n-layout-header bordered style="height:64px;padding:0 24px;display:flex;align-items:center;justify-content:space-between">
      <n-space align="center">
        <n-avatar round size="large" style="background: linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;font-weight:800">AI</n-avatar>
        <div>
          <div style="font-size:18px;font-weight:700;letter-spacing:0.5px">智能选股系统 Pro</div>
          <div style="font-size:12px;color:#909399">量化T+1策略 · 技术/基本/情绪三面分析 · Ollama本地AI深度解读</div>
        </div>
      </n-space>
      <n-space>
        <n-tag :type="ollamaOk ? 'success' : 'warning" round>
          <template #icon><n-icon>{{ ollamaOk ? '✓' : '!' }}</n-icon></template>
          Ollama: {{ ollamaOk ? ollamaModel + ' 已连接' : '未连接' }}
        </n-tag>
        <n-tag type="info" round>T+1 模式</n-tag>
      </n-space>
    </n-layout-header>

    <n-layout has-sider>
      <n-layout-content content-style="padding:16px 24px 32px">
        <router-view />
      </n-layout-content>
    </n-layout>
  </n-layout>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
const app = useAppStore()
onMounted(() => { app.loadConfig().then(() => app.checkOllama()) })
const ollamaOk = computed(() => !!app.ollamaStatus.ok)
const ollamaModel = computed(() => app.ollama.model || '')
</script>
