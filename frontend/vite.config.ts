import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    // Both loopbacks. Left to itself Vite binds only [::1] on Windows, so
    // http://localhost:5173 works and http://127.0.0.1:5173 refuses the
    // connection - which reads as "the app is down" when it is running fine.
    host: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
