import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The service `auto-reel serve` binds by default (api/settings.py).
const SERVICE = 'http://127.0.0.1:8080'

// The client addresses the API by path alone, never by absolute URL: in dev this
// proxy forwards it, and in production the service serves the built assets from
// the same origin. Same origin either way, so the service needs no CORS.
// `ws: true` covers /api/v1/ws/jobs on the same prefix.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: SERVICE, changeOrigin: true, ws: true },
      '/healthz': { target: SERVICE, changeOrigin: true },
    },
  },
})
