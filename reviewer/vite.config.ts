import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { repoRootStaticPlugin } from './devStaticServer.js';

export default defineConfig({
  base: './',
  plugins: [repoRootStaticPlugin(), react()],
  test: {
    environment: 'jsdom',
    passWithNoTests: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
