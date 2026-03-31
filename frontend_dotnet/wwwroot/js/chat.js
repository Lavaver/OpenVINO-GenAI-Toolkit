// Simple client-side chat UI (native Razor + Bootstrap styling)
// This file provides a minimal chat UI without backend integration.
// Replace the simulateReply function with a fetch() call to your AI backend when ready.

function appendMessage(text, cls) {
  const container = document.getElementById('messages')
  const wrapper = document.createElement('div')
  wrapper.className = 'd-flex'
  const msg = document.createElement('div')
  msg.className = `message ${cls}`
  msg.textContent = text
  wrapper.appendChild(msg)
  container.appendChild(wrapper)
  container.scrollTop = container.scrollHeight
}

function simulateReply(inputText) {
  // 模拟延迟并返回示例回复；替换为真实后端调用
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve('（模拟回复）我收到了：' + inputText)
    }, 900)
  })
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form')
  const input = document.getElementById('chat-input')
  const sendBtn = document.getElementById('send-btn')

  async function send() {
    const text = input.value && input.value.trim()
    if (!text) return
    appendMessage(text, 'user')
    input.value = ''
    sendBtn.disabled = true
    appendMessage('正在输入...', 'bot')
    const placeholder = document.querySelector('#messages .message.bot:last-child')
    try {
      const reply = await simulateReply(text)
      if (placeholder) placeholder.textContent = reply
    } catch (e) {
      if (placeholder) placeholder.textContent = '回复失败'
    } finally {
      sendBtn.disabled = false
      input.focus()
    }
  }

  sendBtn.addEventListener('click', (e) => {
    e.preventDefault()
    send()
  })

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  })
})
