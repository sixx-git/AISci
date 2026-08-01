import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 3600000,           // 60分钟（设计脚本 / Pipeline）
        proxyTimeout: 3600000,
      },
      '/storage': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 600000,
      },
      // pingfenbiao 评分表 / 影响力预测服务（需单独启动 :8765）
      '/pingfenbiao': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/pingfenbiao/, ''),
        timeout: 600000,
      },
    },
  },
})
