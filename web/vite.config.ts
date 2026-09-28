import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // 로컬 API 포트는 API_PORT 로 바꿀 수 있습니다(기본 8000)
    proxy: { '/api': `http://127.0.0.1:${process.env.API_PORT ?? 8000}` },
  },
  build: { chunkSizeWarningLimit: 1600 },
})
