import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged,
  type User,
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: 'AIzaSyAYEwnNG1MGDI6LktDNQS-wZnjs8IAr39o',
  authDomain: 'tron-cloud.firebaseapp.com',
  projectId: 'tron-cloud',
  storageBucket: 'tron-cloud.firebasestorage.app',
  messagingSenderId: '710372411235',
  appId: '1:710372411235:web:d1417bf9a58a9319a7f556',
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

const googleProvider = new GoogleAuthProvider();

// Allowlisted emails — only these can access the dashboard
const ALLOWED_EMAILS = [
  'greg@ggernetzke.com',
  'dean.barrett.86@gmail.com',
  'd.barrett@ghostprotocol.us',
];

export function isEmailAllowed(email: string | null): boolean {
  if (!email) return false;
  return ALLOWED_EMAILS.includes(email.toLowerCase());
}

export async function loginWithEmail(email: string, password: string) {
  return signInWithEmailAndPassword(auth, email, password);
}

export async function loginWithGoogle() {
  return signInWithPopup(auth, googleProvider);
}

export async function logout() {
  return signOut(auth);
}

export function onAuthChange(callback: (user: User | null) => void) {
  return onAuthStateChanged(auth, callback);
}

export type { User };
