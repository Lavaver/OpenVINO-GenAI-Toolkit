<template>
  <!-- 聊天输入容器（岛式浮动卡片） -->
  <div class="chat-input-container">
    <div class="island-card mdui-card mdui-shadow-8">
      <div class="island-inner">
        <div class="mdui-textfield chat-textfield">
          <textarea
            class="mdui-textfield-input"
            v-model="messageText"
            :placeholder="placeholder"
            @keydown.enter.exact.prevent="handleSend"
            @keydown.enter.shift.exact="newline"
            @input="adjustHeight"
            ref="textareaRef"
            rows="2"
          ></textarea>
        </div>

        <div class="button-group">
          <button class="mdui-btn mdui-btn-icon mdui-ripple" @click="handleClear" title="清空对话">
            <span class="material-symbols-outlined">delete</span>
          </button>

          <button :class="['mdui-btn', 'mdui-ripple', 'mdui-color-primary']" @click="handleSend" :disabled="loading">
            <span class="material-symbols-outlined" style="margin-right:8px">send</span>
            发送
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'

// 定义组件的属性
const props = defineProps({
  loading: {
    type: Boolean,
    default: false
  }
})

// 定义组件的事件
const emit = defineEmits(['send', 'clear'])

// 使用聊天存储和设置存储
const chatStore = useChatStore()
const settingsStore = useSettingsStore()
// 消息文本的响应式引用
const messageText = ref('')

// 输入框的占位符
const placeholder = `输入消息，按Enter发送\nShift + Enter 换行`

// 计算属性，用于获取聊天存储中的Token计数
const tokenCount = computed(() => chatStore.tokenCount)

// 计算属性：判断当前模型是否支持图片
const isVLMModel = computed(() => false)

// 修改发送处理函数
const handleSend = async () => {
  if (!messageText.value.trim() || props.loading) return

  try {
    const messageContent = messageText.value
    emit('send', messageContent)
    messageText.value = ''
  } catch (error) {
    console.error('发送失败:', error)
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: error.message || '发送失败，请重试' })
    } else {
      alert(error.message || '发送失败，请重试')
    }
  }
}

// 处理换行的函数
const newline = (e) => {
  messageText.value += '\n'
}

// 处理清空对话的函数
const handleClear = async () => {
  try {
    // 优先使用 MDUI 对话框（如存在），否则回退到浏览器confirm
    let confirmed = false
    if (window.mdui && window.mdui.dialog) {
      confirmed = window.confirm('确定要清空所有对话记录吗？')
    } else {
      confirmed = window.confirm('确定要清空所有对话记录吗？')
    }
    if (confirmed) emit('clear')
  } catch (e) {
    // ignore
  }
}

const textareaRef = ref(null)

// 调整输入框高度的方法
const adjustHeight = () => {
  const textarea = textareaRef.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = `${textarea.scrollHeight}px`
  }
}

</script>

<style lang="scss" scoped>
/* 聊天输入容器（浮动岛式） */
.chat-input-container {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  width: min(960px, calc(100% - 48px));
  z-index: 1200;
}

.island-card {
  border-radius: var(--mdui-shape-corner-extra-large);
  padding: 10px 14px;
  background: var(--bg-color);
  box-shadow: var(--box-shadow);
}

.island-inner {
  display: flex;
  gap: 12px;
  align-items: center;
}

.chat-textfield {
  flex: 1;
}

.chat-textfield .mdui-textfield-input {
  border-radius: var(--mdui-shape-corner-medium);
  padding: 10px 12px;
  min-height: 44px;
  max-height: 240px;
  resize: none;
  box-shadow: none;
}

.button-group {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mdui-color-primary {
  background-color: var(--md-sys-color-primary) !important;
  color: var(--md-sys-color-on-primary) !important;
}

/* 简单 loading 样式 */
.loading-dots {
  display: inline-block;
  width: 36px;
  text-align: left;
}

.loading-dots::after {
  content: '...';
  animation: blink 1s steps(3,end) infinite;
}

@keyframes blink {
  0%, 20% { opacity: 0 }
  40% { opacity: 1 }
}

</style>