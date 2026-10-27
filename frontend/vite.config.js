import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development, /api is proxied to Django so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  build: { chunkSizeWarningLimit: 6000 }, // plotly.js is ~4.5 MB minified
});
