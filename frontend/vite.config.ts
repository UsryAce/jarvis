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
    // Accept local clients plus Cloudflare's random quick-tunnel subdomains.
    // Host validation remains enabled rather than accepting arbitrary hosts.
    allowedHosts: ['localhost', '127.0.0.1', '.trycloudflare.com'],
    // This supervised process behaves like an appliance. HMR would advertise a
    // localhost websocket to remote phones and create a permanent failed socket.
    hmr: false,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': 'ws://127.0.0.1:8000',
    },
  },
})
