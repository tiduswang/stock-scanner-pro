import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  create, NButton, NCard, NInput, NSelect, NSpace, NGrid, NGi, NLayout,
  NLayoutHeader, NLayoutContent, NLayoutSider, NMenu, NProgress,
  NStatistic, NRow, NCol, NTag, NDescriptions, NDescriptionsItem,
  NDivider, NList, NListItem, NModal, NSlider, NForm, NFormItem,
  NCheckbox, NRadio, NRadioGroup, NText, NBadge, NSpin, NAlert,
  NTabs, NTabPane, NDataTable, NNumberAnimation, NGradientText,
  NAvatar, NIcon, NTooltip, NTimeline, NTimelineItem, NScrollbar,
  NCollapse, NCollapseItem, NDrawer, NDrawerContent
} from 'naive-ui'
import naive from 'naive-ui'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(naive)
app.mount('#app')
