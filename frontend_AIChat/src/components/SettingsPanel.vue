<template>
  <!-- 自实现的右侧设置面板（MDUI 风格） -->
  <div class="settings-drawer" :class="{ 'open': visible }" @click.self="visible = false">
    <div class="settings-panel mdui-card mdui-shadow-8">
      <div class="settings-header">
        <div class="mdui-typo-title">设置</div>
        <button class="mdui-btn mdui-btn-icon" @click="visible = false"><span class="material-symbols-outlined">close</span></button>
      </div>

      <div class="settings-container">
        <div class="form-row">
          <label>主题模式</label>
          <select v-model="settings.themeMode" @change="handleThemeModeChange" class="mdui-select w-full">
            <option value="system">跟随系统</option>
            <option value="light">浅色模式</option>
            <option value="dark">深色模式</option>
          </select>
          <div class="form-item-tip">跟随系统会自动适应您的系统主题设置</div>
        </div>

        <div class="form-row">
          <label>Temperature</label>
          <div class="range-row">
            <input type="range" v-model.number="settings.temperature" min="0" max="1" step="0.1" />
            <div class="range-value">{{ settings.temperature.toFixed(1) }}</div>
          </div>
        </div>

        <div class="form-row">
          <label>最大Token</label>
          <input type="number" v-model.number="settings.maxTokens" min="1" max="4096" class="mdui-textfield-input" />
        </div>

        <div class="form-row">
          <label>流式响应</label>
          <label class="mdui-switch">
            <input type="checkbox" v-model="settings.streamResponse" />
            <i class="mdui-switch-icon"></i>
          </label>
          <div class="form-item-tip">开启后将实时显示AI回复</div>
        </div>

        <div class="form-row">
          <label>Top P</label>
          <div class="range-row">
            <input type="range" v-model.number="settings.topP" min="0" max="1" step="0.1" />
            <div class="range-value">{{ settings.topP.toFixed(1) }}</div>
          </div>
        </div>

        <div class="form-row">
          <label>Top K</label>
          <input type="number" v-model.number="settings.topK" min="1" max="100" class="mdui-textfield-input" />
        </div>

        <div class="form-row">
          <label>主色（Primary）</label>
          <div style="display:flex;gap:8px;align-items:center">
            <input type="color" v-model="settings.primaryColor" />
            <input type="text" v-model="settings.primaryColor" class="mdui-textfield-input" style="width:120px" />
            <button class="mdui-btn mdui-ripple" @click="applyPrimaryColor">应用主色</button>
          </div>
          <div class="form-item-tip">使用 MDUI 的 setColorScheme 生成整套配色方案</div>
        </div>
      </div>

      <div class="settings-footer">
        <button class="mdui-btn mdui-ripple mdui-color-primary" @click="handleSave">保存设置</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { useSettingsStore } from '../stores/settings'

// 定义组件的props
const props = defineProps({ modelValue: Boolean })

// 定义组件的emits
const emit = defineEmits(['update:modelValue'])

// 使用设置存储
const settingsStore = useSettingsStore()

// 可见性计算属性，同步抽屉的可见性状态
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 设置对象，使用reactive进行响应式处理
const settings = reactive({
  themeMode: settingsStore.themeMode,
  isDarkMode: settingsStore.isDarkMode,
  primaryColor: settingsStore.primaryColor,
  temperature: settingsStore.temperature,
  maxTokens: settingsStore.maxTokens,
  streamResponse: settingsStore.streamResponse,
  topP: settingsStore.topP,
  topK: settingsStore.topK
})

// 处理主题模式变化
const handleThemeModeChange = (value) => {
  settingsStore.setThemeMode(value)
  settings.isDarkMode = settingsStore.isDarkMode
}

// 保存设置
const handleSave = () => {
  settingsStore.updateSettings(settings)
  if (window.mdui && window.mdui.snackbar) {
    window.mdui.snackbar({ message: '设置已保存' })
  } else {
    alert('设置已保存')
  }
  visible.value = false
}

const applyPrimaryColor = async () => {
  try {
    await settingsStore.setColorScheme(settings.primaryColor)
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: '主色已应用' })
    }
  } catch (e) {
    console.error('应用主色失败', e)
    alert('应用主色失败')
  }
}
</script>

<style lang="scss" scoped>
.settings-drawer {
  position: fixed;
  right: 0;
  top: 0;
  height: 100vh;
  width: 0;
  overflow: hidden;
  transition: width 0.25s ease;
  z-index: 1300;
}
.settings-drawer.open {
  width: 420px;
}
.settings-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px;
  background: var(--md-sys-color-surface);
}
.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--divider-color);
}
.settings-container {
  padding: 12px 0;
  flex: 1;
  overflow: auto;
}
.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.form-row label {
  font-weight: 600;
}
.range-row {
  display:flex;
  align-items:center;
  gap:8px;
}
.range-value {
  min-width:36px;
  text-align:center;
}
.settings-footer {
  padding-top: 8px;
  text-align: right;
}
.form-item-tip {
  font-size: 12px;
  color: var(--text-color-secondary);
}
.w-full { width:100%; }
</style>