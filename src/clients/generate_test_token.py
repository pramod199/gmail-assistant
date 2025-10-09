#!/usr/bin/env python3
"""
Generate a test Firebase custom token for development testing
"""
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.auth.firebase_async import create_custom_token_async
import asyncio


async def main():
    """Generate a custom token for testing"""
    print("=" * 60)
    print("FIREBASE CUSTOM TOKEN GENERATOR")
    print("=" * 60)

    user_id = input("\n🔑 Enter Firebase User ID (e.g., 'testuser123'): ").strip()

    if not user_id:
        print("❌ User ID is required")
        return

    try:
        print(f"\n🔄 Generating custom token for user: {user_id}...")
        token = await create_custom_token_async(user_id)

        print("\n✅ Token generated successfully!")
        print("-" * 60)
        print("📋 Copy this token:")
        print(token)
        print("-" * 60)
        print("\n💡 Use this token with the PyAudio client")

    except Exception as e:
        print(f"\n❌ Error generating token: {e}")
        print("⚠️  Make sure Firebase is properly configured")


if __name__ == "__main__":
    asyncio.run(main())
