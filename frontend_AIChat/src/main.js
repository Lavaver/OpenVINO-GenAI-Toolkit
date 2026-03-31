import { createApp, nextTick } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
// Element Plus removed from UI layer — keeping frontend lightweight without Element CSS
import './assets/styles/main.scss'
import router from './router'
import App from './App.vue'

// 使用深色代码主题
import 'highlight.js/styles/github-dark.css'

const app = createApp(App)
const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(router)

// 挂载应用
app.mount('#app')

// Initialize MDUI if loaded (CDN injects global `mdui`)
if (typeof window !== 'undefined' && window.mdui) {
  try {
    // Mutation will scan the DOM for mdui components
    window.mdui.mutation && window.mdui.mutation()
  } catch (e) {
    // 非阻塞日志
    // eslint-disable-next-line no-console
    console.warn('MDUI initialization error:', e)
  }
}

// Element Plus 主题适配
import { useSettingsStore } from './stores/settings'

// 在应用挂载后初始化主题系统
nextTick(() => {
  const settingsStore = useSettingsStore()
  settingsStore.initTheme()
})