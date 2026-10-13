import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const isProductionBuild = command === 'build' || mode === 'production';

  if (isProductionBuild) {
    const env = loadEnv(mode, process.cwd(), '');

    const emulatorHost = (
      process.env.VITE_FIREBASE_AUTH_EMULATOR_HOST ??
      env.VITE_FIREBASE_AUTH_EMULATOR_HOST ??
      ''
    ).trim();

    if (emulatorHost.length > 0) {
      throw new Error(
        `Production build failed: VITE_FIREBASE_AUTH_EMULATOR_HOST cannot be set in production (${emulatorHost}). Unset VITE_FIREBASE_AUTH_EMULATOR_HOST for production builds.`
      );
    }

    const apiKey = (
      process.env.VITE_FIREBASE_API_KEY ??
      env.VITE_FIREBASE_API_KEY ??
      ''
    ).trim();

    const authDomain = (
      process.env.VITE_FIREBASE_AUTH_DOMAIN ??
      env.VITE_FIREBASE_AUTH_DOMAIN ??
      ''
    ).trim();

    const projectId = (
      process.env.VITE_FIREBASE_PROJECT_ID ??
      env.VITE_FIREBASE_PROJECT_ID ??
      ''
    ).trim();

    const missing: string[] = [];
    if (!apiKey) missing.push('VITE_FIREBASE_API_KEY');
    if (!authDomain) missing.push('VITE_FIREBASE_AUTH_DOMAIN');
    if (!projectId) missing.push('VITE_FIREBASE_PROJECT_ID');

    if (missing.length > 0) {
      throw new Error(
        `Production build failed: missing required Firebase environment variable${
          missing.length > 1 ? 's' : ''
        }: ${missing.join(', ')}.`
      );
    }
  }

  return {
    plugins: [react()],
    define: isProductionBuild
      ? {
          'import.meta.env.VITE_API_BASE_URL': JSON.stringify(''),
        }
      : undefined,
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      watch: {
        usePolling: true,
        interval: 100,
      },
    },
  };
});

