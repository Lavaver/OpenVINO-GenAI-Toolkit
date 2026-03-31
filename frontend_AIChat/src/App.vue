<template>
  <div class="app-root">
    <!-- 顶部 AppBar，使用 MDUI 样式做视觉统一 -->
    <header class="mdui-appbar mdui-appbar-fixed">
      <div class="mdui-toolbar mdui-container">
        <a class="mdui-typo-title">OpenVINO™ GenAI</a>
      </div>
    </header>

    <div class="app-container mdui-container">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useSettingsStore } from './stores/settings'

const settingsStore = useSettingsStore()

// 监听主题变化
watch(() => [settingsStore.isDarkMode, settingsStore.themeMode], () => {
  if (settingsStore.themeMode === 'system') {
    const isDark = settingsStore.detectSystemTheme()
    settingsStore.applyTheme(isDark)
  } else {
    const isDark = settingsStore.themeMode === 'dark'
    settingsStore.applyTheme(isDark)
  }
}, { immediate: true })

// 在组件挂载时初始化主题
onMounted(() => {
  settingsStore.initTheme()
})
</script>
<style lang="scss">
.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}


</style>

