import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, connectAuthEmulator, GoogleAuthProvider } from 'firebase/auth';

const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID;
const apiKey = import.meta.env.VITE_FIREBASE_API_KEY || 'fake-api-key';
const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN;
const emulatorHost = import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST;

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

  if (emulatorHost && emulatorHost.trim().length > 0) {
    const emulatorUrl = emulatorHost.startsWith('http')
      ? emulatorHost
      : `http://${emulatorHost}`;
    connectAuthEmulator(auth, emulatorUrl, { disableWarnings: true });
    console.info(`[Firebase Auth] Connected to auth emulator at ${emulatorUrl}`);
  } else {
    console.info(`[Firebase Auth] Connected to real Firebase project ${projectId || 'unspecified'}`);
  }
}
