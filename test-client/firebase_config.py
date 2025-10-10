"""
Firebase Client Configuration

To get your Firebase Web API Key:
1. Go to Firebase Console: https://console.firebase.google.com/
2. Select your project
3. Go to Project Settings (gear icon)
4. Under "General" tab, scroll to "Your apps"
5. Find "Web API Key" - copy this value

Set the FIREBASE_API_KEY below or use environment variable.
"""

import os

# Firebase Web API Key (from Firebase Console)
FIREBASE_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "AIzaSyDWfLILJm7gcBKPIR5WvXbkff4STITePI8")

# Firebase REST API endpoints
FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
FIREBASE_SIGNUP_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
