import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The dev server forwards /api to the backend, as nginx does in Docker, so the
// browser only ever talks to one origin and no CORS setup is needed.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8100'

export default defineConfig({
  plugins: [react()],
  server: { port: 5180, strictPort: true, proxy: { '/api': apiTarget } },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
})
