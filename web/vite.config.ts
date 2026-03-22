import { reactRouter } from '@react-router/dev/vite'
import autoprefixer from 'autoprefixer'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import tsconfigPaths from 'vite-tsconfig-paths'
import path from 'path'

export default defineConfig(({ command, mode }) => ({
  base: mode === 'development' ? '/' : '/',
  sourcemap: true,
  appType: 'spa',
  resolve: {
    alias: {
      '@/': path.resolve(__dirname, 'app/'),
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
  },
  plugins: [tailwindcss(), reactRouter(), tsconfigPaths()],
}))
