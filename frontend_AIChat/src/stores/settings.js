// 引入 Pinia 的 defineStore 方法，用于定义一个新的 store
import { defineStore } from 'pinia'

// 定义一个名为 'settings' 的 store
export const useSettingsStore = defineStore('settings', {
    // 定义 store 的状态
    state: () => ({
        // 主题模式：'light', 'dark', 'system'
        themeMode: 'system',
        // 是否启用深色模式，默认为 false
        isDarkMode: false,
        // 主色（十六进制），可用于 setColorScheme
        primaryColor: '#0061a4',
        // 温度参数，控制生成文本的随机性，默认值为 0.7
        temperature: 0.7,
        // 最大 token 数量，默认值为 32768
        maxTokens: 32768,
        // 是否启用流式响应，默认为 true
        streamResponse: true,
        // Top P 参数
        topP: 0.9,
    }),

    // 定义 store 的动作
    actions: {
        // 检测系统主题
        detectSystemTheme() {
            if (typeof window !== 'undefined') {
                const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches
                return isDarkMode
            }
            return false
        },

        // 应用主题
        applyTheme(isDark) {
            this.isDarkMode = isDark
            // 保持老的 data-theme 用于兼容现有样式选择器
            document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')

            // 同时为 MDUI 添加主题类，mdui 支持 mdui-theme-auto/light/dark
            document.documentElement.classList.remove('mdui-theme-auto', 'mdui-theme-light', 'mdui-theme-dark')
            if (this.themeMode === 'system') {
                document.documentElement.classList.add('mdui-theme-auto')
            } else if (isDark) {
                document.documentElement.classList.add('mdui-theme-dark')
            } else {
                document.documentElement.classList.add('mdui-theme-light')
            }
        },

        // 设置主题模式
        setThemeMode(mode) {
            this.themeMode = mode
            if (mode === 'system') {
                const isDark = this.detectSystemTheme()
                this.applyTheme(isDark)
            } else {
                const isDark = mode === 'dark'
                this.applyTheme(isDark)
            }
        },

        // 切换深色模式（保留原有方法以兼容现有代码）
        toggleDarkMode() {
            if (this.themeMode === 'system') {
                // 如果当前是系统模式，切换到手动模式
                this.setThemeMode(this.isDarkMode ? 'light' : 'dark')
            } else {
                // 在手动模式间切换
                this.setThemeMode(this.isDarkMode ? 'light' : 'dark')
            }
        },

        // 初始化主题
        initTheme() {
            // 应用当前主题
            if (this.themeMode === 'system') {
                const isDark = this.detectSystemTheme()
                this.applyTheme(isDark)
            } else {
                const isDark = this.themeMode === 'dark'
                this.applyTheme(isDark)
            }

            // 监听系统主题变化（仅在浏览器环境中）
            if (typeof window !== 'undefined') {
                const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
                const handleChange = (e) => {
                    if (this.themeMode === 'system') {
                        this.applyTheme(e.matches)
                    }
                }
                
                // 使用新的 addEventListener 方法
                if (mediaQuery.addEventListener) {
                    mediaQuery.addEventListener('change', handleChange)
                } else {
                    // 兼容旧版浏览器
                    mediaQuery.addListener(handleChange)
                }
            }

            // 在初始化时尝试应用已保存的主色
            if (typeof window !== 'undefined') {
                // 在浏览器环境下调用 setColorScheme，以便 mdui 的 CSS 变量被生成
                this.setColorScheme(this.primaryColor).catch(() => {})
            }
        },

        // 使用 mdui 的 setColorScheme 动态生成配色方案
        async setColorScheme(hex) {
            if (!hex) return
            // 允许传入 #rrggbb 或不带 # 的十六进制
            let color = hex
            if (color && color[0] !== '#') color = `#${color}`
            try {
                // 优先使用全局 mdui（CDN 加载时）
                if (typeof window !== 'undefined' && window.mdui && window.mdui.functions && typeof window.mdui.functions.setColorScheme === 'function') {
                    window.mdui.functions.setColorScheme(color)
                } else {
                    // 动态模块导入 mdui 的 setColorScheme 函数（通过 unpkg CDN）
                    const mod = await import('https://unpkg.com/mdui@2/functions/setColorScheme.js')
                    const fn = mod.setColorScheme || mod.default || mod
                    if (typeof fn === 'function') fn(color)
                }
                this.primaryColor = color
            } catch (e) {
                // 非阻塞日志
                // eslint-disable-next-line no-console
                console.warn('setColorScheme failed:', e)
            }
        },

        // 更新设置
        updateSettings(settings) {
            // 使用 Object.assign 方法将传入的设置对象合并到当前 store 的状态中
            Object.assign(this.$state, settings)
        },
    },

    // 配置持久化选项
    persist: {
        // 启用持久化功能
        enabled: true,
        // 持久化策略数组
        strategies: [
            {
                // 存储键名
                key: 'ai-chat-settings',
                // 存储方式，这里使用的是 localStorage
                storage: localStorage,
            },
        ],
    },
})