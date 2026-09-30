import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The service `auto-reel serve` binds by default (api/settings.py).
const DEFAULT_SERVICE = 'http://127.0.0.1:8080'

// The CSS support floor (web/README.md, "Design system"): esbuild must neither
// lower native nesting nor rewrite light-dark() for older engines.
const CSS_TARGET = ['chrome123', 'edge123', 'firefox120', 'safari17.5']

// The client addresses the API by path alone, never by absolute URL: in dev this
// proxy forwards it, and in production the service serves the built assets from
// the same origin. Same origin either way, so the service needs no CORS.
// `ws: true` covers /api/v1/ws/jobs on the same prefix.
export default defineConfig(({ mode }) => {
  // AUTO_REEL_API points the dev proxy at a service on another address. The
  // empty prefix makes loadEnv merge the process environment as well, without
  // this file naming `process` (@types/node is not installed).
  const service = loadEnv(mode, '.', '').AUTO_REEL_API || DEFAULT_SERVICE
  return {
    plugins: [react()],
    build: { cssTarget: CSS_TARGET },
    server: {
      proxy: {
        '/api': { target: service, changeOrigin: true, ws: true },
        '/healthz': { target: service, changeOrigin: true },
      },
    },
  }
})
