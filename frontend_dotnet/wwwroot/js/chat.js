// Simple client-side chat UI (native Razor + Bootstrap styling)
// This file provides a minimal chat UI without backend integration.
// Replace the simulateReply function with a fetch() call to your AI backend when ready.

function appendMessage(text, cls) {
  const container = document.getElementById('messages')
  const wrapper = document.createElement('div')
  wrapper.className = 'd-flex'
  const msg = document.createElement('div')
  msg.className = `message ${cls}`
  // support HTML for simple formatting
  msg.innerText = text
  wrapper.appendChild(msg)
  container.appendChild(wrapper)
  container.scrollTop = container.scrollHeight
}

// Parse Server-sent events style chunks from the backend
function processSseChunk(chunk, onData) {
  // chunk may contain one or more "data: ..." events separated by \n\n
  const parts = chunk.split('\n\n')
  parts.forEach(part => {
    const line = part.trim()
    if (!line) return
    if (line.startsWith('data:')) {
      const payload = line.slice(5).trim()
      onData(payload)
    }
  })
}

async function streamChat(promptText, onToken, onDone) {
  // Try calling Python backend at localhost:8000 (default). Fallback to simulation on error.
  const apiUrl = (window.AI_API_BASE || 'http://localhost:8000') + '/v1/chat/completions'
  const body = {
    model: 'local-model',
    messages: [{ role: 'user', content: promptText }],
    max_tokens: 2048,
    temperature: 0.7,
    top_p: 0.9,
    stream: true
  }

  try {
    const resp = await fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    if (!resp.ok) {
      throw new Error('聊天接口返回错误: ' + resp.status)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let done = false
    let buffer = ''
    while (!done) {
      const { value, done: streamDone } = await reader.read()
      if (value) {
        buffer += decoder.decode(value, { stream: true })
        // Process any complete SSE events in buffer
        const events = buffer.split('\n\n')
        // keep last partial
        buffer = events.pop() || ''
        for (const ev of events) {
          const trimmed = ev.trim()
          if (!trimmed) continue
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (payload === '[DONE]') {
            done = true
            break
          }
          // payload may be JSON or simple text
          try {
            const parsed = JSON.parse(payload)
            // streaming chunk in OpenAI-style: choices[0].delta.content
            if (parsed.choices && parsed.choices.length > 0) {
              const delta = parsed.choices[0].delta || {}
              if (delta.content) {
                onToken(delta.content)
              }
            } else if (typeof parsed === 'string') {
              onToken(parsed)
            }
          } catch (e) {
            // not JSON, pass raw payload
            onToken(payload)
          }
        }
      }
      if (streamDone) break
    }
    onDone()
  } catch (e) {
    console.warn('Stream chat failed, falling back to simulation:', e)
    // fallback: simple simulated reply
    await new Promise(r => setTimeout(r, 600))
    onToken('（模拟回复）' + promptText)
    onDone()
  }
}

async function pushHistory(item) {
  const api = (window.AI_API_BASE || 'http://localhost:8000') + '/v1/history'
  try {
    await fetch(api, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(item)
    })
  } catch (e) {
    // ignore history errors
    console.debug('history push failed', e)
  }
}

async function loadHistory() {
  const api = (window.AI_API_BASE || 'http://localhost:8000') + '/v1/history'
  try {
    const r = await fetch(api)
    if (!r.ok) return
    const j = await r.json()
    if (j && Array.isArray(j.history)) {
      j.history.forEach(h => {
        if (h && h.role && h.content) appendMessage(h.content, h.role === 'user' ? 'user' : 'bot')
      })
    }
  } catch (e) {
    console.debug('load history failed', e)
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form')
  const input = document.getElementById('chat-input')
  const sendBtn = document.getElementById('send-btn')

  // load history if available
  loadHistory()

  async function send() {
    const text = input.value && input.value.trim()
    if (!text) return
    appendMessage(text, 'user')
    // push to remote history (best-effort)
    pushHistory({ role: 'user', content: text })
    input.value = ''
    sendBtn.disabled = true
    // add placeholder bot message
    appendMessage('...', 'bot')
    const placeholder = document.querySelector('#messages .message.bot:last-child')
    let accumulated = ''
    await streamChat(text, (token) => {
      accumulated += token
      if (placeholder) placeholder.textContent = accumulated
    }, () => {
      // streaming done: push assistant content to history
      pushHistory({ role: 'assistant', content: accumulated })
      sendBtn.disabled = false
      input.focus()
    })
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
