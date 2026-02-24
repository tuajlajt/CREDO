import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Forward API requests to the FastAPI backend
    proxy: {
      '/ehr':       { target: 'http://localhost:8000', changeOrigin: true },
      '/health':    { target: 'http://localhost:8000', changeOrigin: true },
      '/transcribe':{ target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    // Production build lands in the FastAPI static folder
    outDir: 'src/ui/static/dist',
  },
});
