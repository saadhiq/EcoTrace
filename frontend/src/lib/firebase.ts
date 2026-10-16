import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

// Web config is public (not a secret) but comes from build-time env vars,
// filled in by scripts/deploy-frontend.sh or frontend/.env.local.
const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
};

function firebaseApp(): FirebaseApp {
  return getApps().length ? getApp() : initializeApp(config);
}

/** Lazily initialised so nothing runs during static prerendering. */
export function firebaseAuth(): Auth {
  return getAuth(firebaseApp());
}
