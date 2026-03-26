import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // API URL을 직접 정의 (.env 파일 의존 제거)
  // 배포 시 해당 URL을 변경하세요
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify('http://localhost:8001'),
  },
})
