#!/usr/bin/env python3
"""
Simple Firebase Token Generator - Create your own test token
"""

import requests
import json
import firebase_admin
from firebase_admin import credentials, auth

# Configuration
FIREBASE_API_KEY = "REDACTED_FIREBASE_API_KEY"
PROJECT_ID = "REDACTED_FIREBASE_PROJECT_ID"

def create_firebase_user_token(email: str, password: str) -> str:
    """Method 1: Create Firebase user and get ID token"""
    print(f"🔥 Creating Firebase user: {email}")
    
    # Create user via Firebase Auth REST API
    signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
    
    data = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(signup_url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            id_token = result.get("idToken")
            print("✅ User created and token generated!")
            return id_token
        else:
            # User might already exist, try signing in
            print("👤 User exists, signing in...")
            return signin_firebase_user(email, password)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def signin_firebase_user(email: str, password: str) -> str:
    """Sign in existing Firebase user"""
    signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    
    data = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(signin_url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            id_token = result.get("idToken")
            print("✅ Sign in successful!")
            return id_token
        else:
            print(f"❌ Sign in failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def create_custom_token_method() -> str:
    """Method 2: Use Firebase Admin SDK to create custom token, then exchange"""
    print("🔧 Creating custom token with Admin SDK...")
    
    try:
        # Initialize Firebase Admin
        if not firebase_admin._apps:
            cred = credentials.Certificate('firebase-service-account.json')
            firebase_admin.initialize_app(cred)
        
        # Create custom token
        test_uid = f"test-user-{int(__import__('time').time())}"  # Unique ID
        custom_token = auth.create_custom_token(test_uid, {
            'email': 'test@example.com',
            'role': 'tester'
        })
        
        print("✅ Custom token created, exchanging for ID token...")
        
        # Exchange for ID token
        exchange_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}"
        
        data = {
            "token": custom_token.decode(),
            "returnSecureToken": True
        }
        
        response = requests.post(exchange_url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            id_token = result.get("idToken")
            print("✅ Custom token exchanged successfully!")
            return id_token
        else:
            print(f"❌ Exchange failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def save_token(token: str, filename: str = "my_test_token.txt"):
    """Save token to file and display usage"""
    with open(filename, "w") as f:
        f.write(token)
    
    print(f"\n💾 Token saved to: {filename}")
    print(f"\n📋 Copy this for Postman 'firebase_token' variable:")
    print(f"{token}")
    
    print(f"\n🧪 Test with curl:")
    print(f'curl -H "Authorization: Bearer {token}" http://localhost:8000/api/auth/gmail/status')
    
    return filename

def main():
    print("🔑 Firebase Test Token Generator")
    print("=" * 50)
    print("Choose your method:")
    print("1. Create Firebase user (Email/Password)")
    print("2. Use Admin SDK custom token")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    token = None
    
    if choice == "1":
        print("\n📧 Create Firebase User Method")
        email = input("Enter email (default: test@example.com): ").strip() or "test@example.com"
        password = input("Enter password (default: testpass123): ").strip() or "testpass123"
        
        token = create_firebase_user_token(email, password)
        
    elif choice == "2":
        print("\n🔧 Admin SDK Custom Token Method")
        token = create_custom_token_method()
        
    else:
        print("❌ Invalid choice")
        return
    
    if token:
        save_token(token)
        print(f"\n✅ SUCCESS! You now have a working Firebase token.")
        
        # Test token verification
        print(f"\n🔍 Testing token verification...")
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate('firebase-service-account.json')
                firebase_admin.initialize_app(cred)
            
            decoded = auth.verify_id_token(token)
            print(f"✅ Token verified! User: {decoded.get('uid', decoded.get('user_id'))}")
            
        except Exception as e:
            print(f"⚠️  Token verification issue: {e}")
            print("   Token might still work with API")
    else:
        print("❌ Failed to generate token")

if __name__ == "__main__":
    main()