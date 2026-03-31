<template>
  <!-- 消息容器，根据消息角色和加载状态动态调整样式 -->
  <div
    class="message-container"
    :class="[
      message.role === 'assistant' ? 'message-assistant' : 'message-user',
      { loading }
    ]"
  >
    <!-- 消息头像，根据消息角色显示不同图标 -->
    <div class="message-avatar">
      <span class="material-symbols-outlined avatar-icon">{{ message.role === 'assistant' ? 'support_agent' : 'person' }}</span>
    </div>
    <!-- 消息内容，根据加载状态显示不同内容 -->
    <div class="message-content">
      <!-- 显示模式 -->
      <div class="message-text" v-if="!loading && !isEditing">
        <!-- VLM 格式消息：包含图片和文本 -->
        <div v-if="isVLMMessage" class="vlm-message">
          <!-- 显示图片 -->
          <div class="message-images" v-if="messageImages.length > 0">
            <img 
              v-for="(imageUrl, index) in messageImages" 
              :key="index"
              :src="imageUrl" 
              class="message-image"
              @click="previewImage(imageUrl)"
            />
          </div>
          <!-- 显示文本 -->
          <div v-if="messageText">
            <!-- 显示思考过程 -->
            <div class="think-content" v-if="thinkContent">
              <div class="think-label">🧠 思考过程：</div>
              <div class="think-text" v-html="renderedThinkContent"></div>
            </div>
            <!-- 显示正式回答 -->
            <div class="answer-content" v-if="answerContent">
              <div class="markdown-body" v-html="renderedAnswerContent" ref="markdownBody" @click="handleCodeBlockClick"></div>
            </div>
          </div>
        </div>
        <!-- 传统格式消息 -->
        <div v-else>
          <!-- 显示思考过程 -->
          <div class="think-content" v-if="thinkContent">
            <div class="think-label">🧠 思考过程：</div>
            <div class="think-text" v-html="renderedThinkContent"></div>
          </div>
          <!-- 显示正式回答 -->
          <div class="answer-content" v-if="answerContent">
            <div class="markdown-body" v-html="renderedAnswerContent" ref="markdownBody" @click="handleCodeBlockClick"></div>
          </div>
        </div>
      </div>

      <!-- 编辑模式 -->
      <div class="message-edit" v-if="isEditing">
        <div class="mdui-textfield edit-textfield">
          <textarea
            class="mdui-textfield-input"
            v-model="editContent"
            rows="2"
            ref="editInputRef"
            @keydown.enter.exact.prevent="handleEditKeydown"
            @keydown.esc="cancelEdit"
          ></textarea>
        </div>
        <div class="edit-actions">
          <button class="mdui-btn mdui-ripple" @click="cancelEdit">取消</button>
          <button class="mdui-btn mdui-ripple mdui-color-primary" @click="saveEdit">保存</button>
        </div>
      </div>

      <div class="message-loading" v-if="loading">
        <span class="loading-dots"></span>
        正在思考...
      </div>

      <!-- 消息底部区域：时间和操作按钮 -->
      <div class="message-footer">
        <span class="message-time">{{ formatTime(message.timestamp) }}</span>
        <!-- 用户消息的操作按钮 -->
        <div class="message-actions" v-if="!loading && message.role === 'user' && !isEditing">
          <button class="mdui-btn mdui-btn-icon mdui-ripple" @click="startEdit" title="编辑">
            <span class="material-symbols-outlined">edit</span>
          </button>
          <button class="mdui-btn mdui-btn-icon mdui-ripple" @click="handleDelete" title="删除">
            <span class="material-symbols-outlined">delete</span>
          </button>
        </div>
        <!-- AI助手消息的操作按钮 -->
        <div class="message-actions" v-if="!loading && message.role === 'assistant'">
          <button class="mdui-btn mdui-btn-icon mdui-ripple" @click="handleRegenerate" :title="'重新生成'" :disabled="isLoading">
            <span class="material-symbols-outlined">refresh</span>
          </button>
          <button class="mdui-btn mdui-btn-icon mdui-ripple" @click="handleCopyAll" title="复制全部">
            <span class="material-symbols-outlined">content_copy</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, nextTick } from 'vue'
import { renderMarkdown } from '../utils/markdown'
import { useChatStore } from '../stores/chat'

// 定义组件属性
const props = defineProps({
  message: {
    type: Object,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update', 'delete', 'regenerate'])

const markdownBody = ref(null)
const isEditing = ref(false)
const editContent = ref('')
const editInputRef = ref(null)

// 从 store 中获取 loading 状态
const chatStore = useChatStore()
const isLoading = computed(() => chatStore.isLoading)

// 开始编辑
const startEdit = async () => {
  // 对于VLM格式的消息，只编辑文本部分
  editContent.value = isVLMMessage.value ? messageText.value : props.message.content
  isEditing.value = true
  // 等待 DOM 更新后聚焦输入框
  await nextTick()
  editInputRef.value?.focus && editInputRef.value.focus()
}

// 取消编辑
const cancelEdit = () => {
  isEditing.value = false
  editContent.value = ''
}

// 保存编辑
const saveEdit = () => {
  if (!editContent.value.trim()) {
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: '消息内容不能为空' })
    } else {
      alert('消息内容不能为空')
    }
    return
  }
  
  // 对于VLM格式的消息，更新文本部分
  let updatedContent
  if (isVLMMessage.value) {
    updatedContent = {
      ...props.message.content,
      text: editContent.value.trim()
    }
  } else {
    updatedContent = editContent.value.trim()
  }
  
  emit('update', {
    ...props.message,
    content: updatedContent
  })
  isEditing.value = false
}

// 删除消息
const handleDelete = async () => {
  try {
    const confirmed = window.confirm('确定要删除这条消息吗？')
    if (confirmed) emit('delete', props.message)
  } catch (e) {
    // ignore
  }
}

// 格式化时间函数
const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString()
}

// 计算属性：判断是否为VLM格式消息
const isVLMMessage = computed(() => {
  return typeof props.message.content === 'object' && props.message.content.images
})

// 计算属性：获取消息中的图片
const messageImages = computed(() => {
  if (isVLMMessage.value) {
    return props.message.content.images || []
  }
  return []
})

// 计算属性：获取消息文本
const messageText = computed(() => {
  if (isVLMMessage.value) {
    return props.message.content.text || ''
  }
  return props.message.content
})

// 计算属性：提取思考过程和正式回答
const thinkContent = computed(() => {
  const text = messageText.value
  const thinkStart = text.indexOf('<think>')
  const thinkEnd = text.indexOf('</think>')
  if (thinkStart !== -1 && thinkEnd !== -1) {
    return text.substring(thinkStart + 6, thinkEnd).trim()
  }
  return ''
})

const answerContent = computed(() => {
  const text = messageText.value
  const thinkEnd = text.indexOf('</think>')
  if (thinkEnd !== -1) {
    return text.substring(thinkEnd + 7).trim()
  }
  return text
})

// 计算属性：渲染 Markdown 内容
const renderedThinkContent = computed(() => {
  return renderMarkdown(thinkContent.value)
})

const renderedAnswerContent = computed(() => {
  return renderMarkdown(answerContent.value)
})

// 图片预览功能
const previewImage = (imageUrl) => {
  // 创建一个新的窗口来预览图片
  const newWindow = window.open('', '_blank')
  newWindow.document.write(`
    <html>
      <head><title>图片预览</title></head>
      <body style="margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#000;">
        <img src="${imageUrl}" style="max-width:100%;max-height:100%;object-fit:contain;" />
      </body>
    </html>
  `)
}

// 复制文本到剪贴板
const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: '代码已复制到剪贴板' })
    } else {
      alert('代码已复制到剪贴板')
    }
  } catch (err) {
    console.error('复制失败:', err)
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: '复制失败' })
    } else {
      alert('复制失败')
    }
  }
}

// 处理代码块点击事件
const handleCodeBlockClick = (event) => {
  const preElement = event.target.closest('pre')
  if (preElement) {
    const codeElement = preElement.querySelector('code')
    if (codeElement) {
      copyToClipboard(codeElement.textContent)
    }
  }
}

// 处理编辑时的按键事件
const handleEditKeydown = (e) => {
  if (e.shiftKey) return // 如果按住 Shift，允许换行
  saveEdit() // 直接保存并发送
}

// 处理重新生成
const handleRegenerate = () => {
  emit('regenerate', props.message)
}

// 复制全部内容
const handleCopyAll = async () => {
  try {
    await navigator.clipboard.writeText(answerContent.value)
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: '内容已复制到剪贴板' })
    } else {
      alert('内容已复制到剪贴板')
    }
  } catch (err) {
    console.error('复制失败:', err)
    if (window.mdui && window.mdui.snackbar) {
      window.mdui.snackbar({ message: '复制失败' })
    } else {
      alert('复制失败')
    }
  }
}
</script>

<style lang="scss" scoped>
.message-container {
  display: flex;
  margin: 0.5rem 0;
  padding: 0.3rem;
  gap: 0.8rem;
  transition: all 0.3s ease;
  
  // 用户消息样式
  &.message-user {
    flex-direction: row-reverse;
    //翻转实现用户布局在右侧
    .message-content {
      align-items: flex-end;
    }
    
    // 深色模式下用户消息的特殊样式
    [data-theme="dark"] & {
      .message-text {
        background-color: var(--primary-color);
        color: #ffffff;
        box-shadow: var(--box-shadow), 0 0 8px rgba(92, 174, 253, 0.3);
      }
    }
  }

  // 助手消息深色模式优化
&.message-assistant {
  [data-theme="dark"] & {
    .message-text {
      background-color: #2d2d2d;
      box-shadow: var(--box-shadow), 0 0 4px rgba(255, 255, 255, 0.1);
    }
    
    .think-content {
      background-color: #1e1e1e;
      border-left-color: #4a90e2;
      
      .think-label {
        color: #4a90e2;
      }
      
      .think-text {
        color: #b0b0b0;
      }
    }
    
    .answer-content {
      .answer-label {
        color: #52c41a;
      }
    }
  }
}

  .markdown-body {
    :deep() {
      // Markdown 内容样式
      h1, h2, h3, h4, h5, h6 {
        margin: 0.3rem 0;
        font-weight: 600;
        line-height: 1.25;
      }

      p {
        margin: 0.15rem 0;
      }

      code {
        font-family: var(--code-font-family);
        padding: 0.2em 0.4em;
        margin: 0;
        font-size: 85%;
        background-color: var(--code-bg);
        border-radius: 3px;
        color: var(--code-text);
      }

      pre {
        position: relative;
        padding: 2rem 1rem 1rem;
        overflow: auto;
        font-size: 85%;
        line-height: 1.45;
        background-color: var(--code-block-bg);
        border-radius: var(--border-radius);
        margin: 0.3rem 0;
        border: 1px solid var(--border-color);
        
        // 代码头部样式
        .code-header {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          padding: 0.3rem 1rem;
          background-color: var(--code-header-bg);
          border-bottom: 1px solid var(--border-color);
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-family: var(--code-font-family);
          
          .code-lang {
            font-size: 0.8rem;
            color: var(--text-color-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
        }

        &::after {
          content: "点击复制";
          position: absolute;
          top: 0.3rem;
          right: 1rem;
          padding: 0.2rem 0.5rem;
          font-size: 0.75rem;
          color: var(--text-color-secondary);
          opacity: 0;
          transition: opacity 0.3s;
          font-family: system-ui, -apple-system, sans-serif;
        }

        &:hover::after {
          opacity: 0.8;
        }

        code {
          padding: 0;
          background-color: transparent;
          color: inherit;
          display: block;
          font-family: var(--code-font-family);
        }
      }

      blockquote {
        margin: 0.15rem 0;
        padding: 0 0.75rem;
        color: var(--text-color-secondary);
        border-left: 0.25rem solid var(--border-color);
      }

      ul, ol {
        margin: 0.15rem 0;
        padding-left: 1.5rem;
      }

      table {
        border-collapse: collapse;
        width: 100%;
        margin: 0.15rem 0;

        th, td {
          padding: 0.5rem;
          border: 1px solid var(--border-color);
        }

        th {
          background-color: var(--bg-color-secondary);
        }
      }

      img {
        max-width: 100%;
        max-height: 300px;
        object-fit: contain;
        margin: 0.3rem 0;
        border-radius: var(--border-radius);
        cursor: pointer;
        
        &:hover {
          opacity: 0.9;
        }
      }

      a {
        color: var(--primary-color);
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }

      > *:last-child {
        margin-bottom: 0;
      }
    }
  }
}

.message-avatar {
  flex-shrink: 0;

  .avatar-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: var(--primary-color);
    color: var(--md-sys-color-on-primary);
    font-size: 20px;
  }

  .avatar-icon[role='assistant'], .avatar-icon.assistant {
    background: var(--success-color);
  }
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-width: 80%;
}

.message-text {
  background-color: var(--bg-color);
  padding: 0.8rem;
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);
  white-space: pre-wrap;
  transition: all 0.3s ease;
  
  // 深色模式下增强阴影效果
  [data-theme="dark"] & {
    border: 1px solid var(--border-color);
  }
}

// 思考过程样式
.think-content {
  margin-bottom: 1rem;
  padding: 0.8rem;
  background-color: var(--bg-color-secondary);
  border-radius: var(--border-radius);
  border-left: 4px solid var(--info-color);
  
  .think-label {
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--info-color);
    font-size: 0.9rem;
  }
  
  .think-text {
    font-style: italic;
    color: var(--text-color-secondary);
    line-height: 1.5;
    
    // 继承 markdown-body 样式
    :deep() {
      h1, h2, h3, h4, h5, h6 {
        margin: 0.3rem 0;
        font-weight: 600;
        line-height: 1.25;
      }

      p {
        margin: 0.15rem 0;
      }

      code {
        font-family: var(--code-font-family);
        padding: 0.2em 0.4em;
        margin: 0;
        font-size: 85%;
        background-color: var(--code-bg);
        border-radius: 3px;
        color: var(--code-text);
      }

      pre {
        position: relative;
        padding: 2rem 1rem 1rem;
        overflow: auto;
        font-size: 85%;
        line-height: 1.45;
        background-color: var(--code-block-bg);
        border-radius: var(--border-radius);
        margin: 0.3rem 0;
        border: 1px solid var(--border-color);
        
        // 代码头部样式
        .code-header {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          padding: 0.3rem 1rem;
          background-color: var(--code-header-bg);
          border-bottom: 1px solid var(--border-color);
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-family: var(--code-font-family);
          
          .code-lang {
            font-size: 0.8rem;
            color: var(--text-color-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }
        }

        code {
          padding: 0;
          background-color: transparent;
          color: inherit;
          display: block;
          font-family: var(--code-font-family);
        }
      }

      blockquote {
        margin: 0.15rem 0;
        padding: 0 0.75rem;
        color: var(--text-color-secondary);
        border-left: 0.25rem solid var(--border-color);
      }

      ul, ol {
        margin: 0.15rem 0;
        padding-left: 1.5rem;
      }

      table {
        border-collapse: collapse;
        width: 100%;
        margin: 0.15rem 0;

        th, td {
          padding: 0.5rem;
          border: 1px solid var(--border-color);
        }

        th {
          background-color: var(--bg-color-secondary);
        }
      }

      a {
        color: var(--primary-color);
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }
    }
  }
}

// 正式回答样式
.answer-content {
  .answer-label {
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--success-color);
    font-size: 0.9rem;
  }
}

// VLM 消息样式
.vlm-message {
  .message-images {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
    
    .message-image {
      max-width: 200px;
      max-height: 200px;
      object-fit: cover;
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: transform 0.2s ease;
      
      &:hover {
        transform: scale(1.05);
      }
    }
  }
}

.message-loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-color-secondary);
}

.message-meta {
  font-size: 0.8rem;
  color: var(--text-color-secondary);
}

.message-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0.5rem;
  font-size: 0.8rem;
  color: var(--text-color-secondary);
}

.message-time {
  margin-right: 0.5rem;
}

.message-actions {
  display: flex;
  gap: 0.25rem;
  opacity: 0.6;
  transition: opacity 0.2s ease;

  &:hover { opacity: 1; }

  .mdui-btn {
    padding: 6px;
    height: 36px;
    min-width: 36px;
    transition: all 0.12s ease;
    border-radius: 8px;

    span.material-symbols-outlined { font-size: 16px; }

    &:hover {
      color: var(--md-sys-color-on-primary);
      background-color: var(--hover-bg-color);
      transform: translateY(-2px);
    }
  }
}

.message-edit {
  background-color: var(--bg-color);
  padding: 0.75rem;
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);

  .el-input {
    margin-bottom: 0.5rem;
    
    :deep(.el-textarea__inner) {
      background-color: var(--bg-color-secondary);
      border-color: var(--border-color);
      resize: none; // 禁用手动调整大小
      
      &:focus {
        border-color: var(--primary-color);
      }
    }
  }

  .edit-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
  }
}
</style>