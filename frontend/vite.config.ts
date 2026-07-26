import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'esbuild',
  },
  server: {
    port: 4173,
    // Keep the dev client's WebSocket on the same public host used by the
    // dashboard. Without this, Vite can advertise 127.0.0.1 while Jarvis is
    // opened at localhost, which breaks live updates in the in-app browser.
    hmr: {
      host: 'localhost',
      clientPort: 4173,
    },
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': 'ws://127.0.0.1:8000',
    },
  },
})
