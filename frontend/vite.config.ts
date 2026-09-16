import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// The browser uses /api. Only the development server knows the backend host.
// Never read NANSEN_API_KEY here or expose it through a VITE_ variable.
const proxy = {
  '/api': {
    target: process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 4173, strictPort: true, proxy },
})
