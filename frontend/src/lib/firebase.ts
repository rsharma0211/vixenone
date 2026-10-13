import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, connectAuthEmulator, GoogleAuthProvider } from 'firebase/auth';

const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
const emulatorHost = import.meta.env.PROD
  ? ''
  : (import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST || '');
const isEmulator = Boolean(emulatorHost && emulatorHost.trim().length > 0);

// The fake api key fallback is allowed only when the emulator host is set (local dev).
const apiKey =
  import.meta.env.VITE_FIREBASE_API_KEY ||
  (!import.meta.env.PROD && isEmulator ? 'fake-api-key' : '');
const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN;

const firebaseConfig = {
  apiKey,
  authDomain: authDomain || (projectId ? `${projectId}.firebaseapp.com` : undefined),
  projectId,
};

const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

let initialized = false;
export function initFirebaseAuth() {
  if (initialized) return;
  initialized = true;

  if (isEmulator && emulatorHost.trim().length > 0) {
    const emulatorUrl = emulatorHost.startsWith('http')
      ? emulatorHost
      : `http://${emulatorHost}`;
    connectAuthEmulator(auth, emulatorUrl, { disableWarnings: true });
    console.info(`[Firebase Auth] Connected to auth emulator at ${emulatorUrl}`);
  } else {
    console.info(`[Firebase Auth] Connected to real Firebase project ${projectId || 'unspecified'}`);
  }
}
