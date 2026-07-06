import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// All API calls go through /api and are proxied to the backend in dev,
// so SPA routes (/transactions, /accounts, ...) never collide with API paths.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL ?? 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
