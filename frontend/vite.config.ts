import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// Where the dev server forwards API calls: the backend started with
// `poetry run uvicorn app.main:app --reload`. Same origin for the browser, so no CORS.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  // vue-i18n feature flags: Composition API only, no devtools hooks in production builds.
  define: {
    __VUE_I18N_LEGACY_API__: 'false',
    __VUE_I18N_FULL_INSTALL__: 'true',
    __INTLIFY_PROD_DEVTOOLS__: 'false',
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': apiTarget,
      '/health': apiTarget,
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.spec.ts'],
    restoreMocks: true,
  },
})
