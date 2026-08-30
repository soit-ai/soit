import { reactRouter } from '@react-router/dev/vite'
import autoprefixer from 'autoprefixer'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import path from 'path'

import { readFileSync } from 'fs'

const packageVersion = JSON.parse(
  readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'),
).version as string

export default defineConfig(({ command, mode }) => ({
  // Stamped at build time so a support conversation can start with the
  // version the person is actually running, rather than a dash.
  define: {
    __CONSOLE_VERSION__: JSON.stringify(packageVersion),
  },
  base: mode === 'development' ? '/' : '/',
  sourcemap: true,
  appType: 'spa',
  resolve: {
    tsconfigPaths: true,
    alias: {
      '@dagrejs/dagre': path.resolve(__dirname, 'node_modules/@dagrejs/dagre/dist/dagre.cjs.js'),
    },
  },
  server: {
    port: 5000,
    proxy: {
      '/api/v1/': {
        // target: 'https://soit.dev',
        target: 'http://127.0.0.1:9200',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  css: {
    postcss: {
      plugins: [autoprefixer],
    },
  },
  build: {
    target: 'esnext',
    polyfillDynamicImport: true,
    chunkSizeWarningLimit: 1000,
  },
  plugins: [tailwindcss(), reactRouter()],
}))
