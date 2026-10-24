import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API runs on :8000 (python -m macrodash serve); /api is proxied.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': process.env.MACRO_API_URL || 'http://127.0.0.1:8000' },
  },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 600 },
});
