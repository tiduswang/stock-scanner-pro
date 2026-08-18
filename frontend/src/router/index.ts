import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页 - 选股扫描' },
  },
  {
    path: '/analyze/:code',
    name: 'analyze',
    component: () => import('@/views/AnalyzeDetail.vue'),
    meta: { title: '个股深度分析' },
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
