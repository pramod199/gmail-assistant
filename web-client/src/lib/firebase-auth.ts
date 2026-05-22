const FIREBASE_API_KEY = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;

if (!FIREBASE_API_KEY) {
  throw new Error(
    "NEXT_PUBLIC_FIREBASE_API_KEY is not set. Add it to web-client/.env.local."
  );
}

const FIREBASE_AUTH_URL =
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword";

export interface FirebaseAuthResult {
  idToken: string;
  localId: string;
  email: string;
}

export async function firebaseSignIn(
  email: string,
  password: string
): Promise<FirebaseAuthResult> {
  const url = `${FIREBASE_AUTH_URL}?key=${FIREBASE_API_KEY}`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, returnSecureToken: true }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(
      err.error?.message || `Firebase auth failed: ${res.status}`
    );
  }

  const data = await res.json();
  return {
    idToken: data.idToken,
    localId: data.localId,
    email: data.email,
  };
}
