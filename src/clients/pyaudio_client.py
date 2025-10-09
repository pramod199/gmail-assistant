#!/usr/bin/env python3
"""
PyAudio Streaming Client for Gmail Voice Assistant
Connects to our WebSocket voice endpoint instead of directly to Gemini Live API
Implements audio isolation to prevent feedback loops (same as live_audio_isolated.py)
"""

import asyncio
import threading
import queue
import json
import base64
import websockets
import pyaudio
import aiohttp
import requests
import getpass
from typing import Optional

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
INPUT_RATE = 16000
OUTPUT_RATE = 24000
BUFFER_DURATION = 1.5  # Send chunks every 1.5 seconds (was 0.5s)

# Server configuration
API_BASE_URL = "http://localhost:8000/api"
WEBSOCKET_URL = "ws://localhost:8000/api/voice/voice"

# Import Firebase client configuration
try:
    from firebase_config import FIREBASE_API_KEY, FIREBASE_AUTH_URL
except ImportError:
    # Fallback if firebase_config.py not found
    import os
    FIREBASE_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "AIzaSyDWfLILJm7gcBKPIR5WvXbkff4STITePI8")
    FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"


def firebase_sign_in(email: str, password: str) -> tuple[str, str]:
    """
    Sign in with Firebase using email and password.
    Returns (id_token, user_id)
    """
    try:
        print(f"🔐 Authenticating with Firebase...")
        print(f"🔑 Using API Key: {FIREBASE_API_KEY}")

        # Firebase REST API for sign in
        url = f"{FIREBASE_AUTH_URL}?key={FIREBASE_API_KEY}"
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        response = requests.post(url, json=payload)

        if response.status_code == 200:
            data = response.json()
            id_token = data.get("idToken")
            user_id = data.get("localId")
            email = data.get("email")

            print(f"✅ Authentication successful!")
            print(f"👤 User: {email}")
            print(f"🆔 User ID: {user_id}")

            return id_token, user_id
        else:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
            print(f"❌ Authentication failed: {error_message}")

            # Handle common errors
            if "EMAIL_NOT_FOUND" in error_message:
                print("💡 The email address is not registered. Please sign up first.")
            elif "INVALID_PASSWORD" in error_message:
                print("💡 The password is incorrect.")
            elif "USER_DISABLED" in error_message:
                print("💡 This user account has been disabled.")

            return None, None

    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        return None, None


class GmailVoiceClient:
    """PyAudio client that streams audio to our Gmail voice assistant WebSocket endpoint"""
    
    def __init__(self, firebase_user_id: str, firebase_token: Optional[str] = None):
        self.firebase_user_id = firebase_user_id
        self.firebase_token = firebase_token
        self.session_id: Optional[str] = None
        self.websocket_url: Optional[str] = None

        self.audio = pyaudio.PyAudio()
        self.audio_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.running = True
        self.is_playing_audio = False  # Audio isolation flag
        self.websocket = None

        print(f"🔊 Gmail Voice Client initialized")
        print(f"👤 User ID: {firebase_user_id}")
        print(f"⏱️  Buffer duration: {BUFFER_DURATION}s (improved for better VAD)")
    
    def start_recording(self):
        """Start recording audio from microphone with isolation"""
        def record_audio():
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            print("🎤 Recording started...")
            
            while self.running:
                try:
                    # AUDIO ISOLATION: Only record if not playing audio
                    if not self.is_playing_audio:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        self.audio_queue.put(data)
                    else:
                        # Read and discard to keep stream active (prevents feedback)
                        stream.read(CHUNK, exception_on_overflow=False)
                except:
                    break
                    
            stream.stop_stream()
            stream.close()
            print("🎤 Recording stopped")
        
        threading.Thread(target=record_audio, daemon=True).start()
    
    def start_playback(self):
        """Start playing audio responses with isolation"""
        def play_audio():
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=OUTPUT_RATE,
                output=True,
                frames_per_buffer=CHUNK
            )
            
            print("🔊 Playback started...")
            
            while self.running:
                try:
                    audio_data = self.response_queue.get(timeout=0.1)
                    # AUDIO ISOLATION: Block recording while playing
                    self.is_playing_audio = True
                    stream.write(audio_data)
                    self.is_playing_audio = False  # Resume recording
                except queue.Empty:
                    continue
                except:
                    break
            
            stream.stop_stream()
            stream.close()
            print("🔊 Playback stopped")
        
        threading.Thread(target=play_audio, daemon=True).start()
    
    async def audio_sender(self):
        """Send audio chunks to WebSocket every 1.5 seconds"""
        audio_buffer = b""
        chunk_size = int(INPUT_RATE * BUFFER_DURATION * 2)  # 1.5s of 16kHz 16-bit audio
        
        print(f"📤 Audio sender started (sending every {BUFFER_DURATION}s)...")
        
        while self.running and self.websocket:
            while not self.audio_queue.empty():
                data = self.audio_queue.get_nowait()
                audio_buffer += data
                
                if len(audio_buffer) >= chunk_size:
                    # Encode audio data as base64
                    encoded_audio = base64.b64encode(audio_buffer).decode('utf-8')
                    
                    # Send audio chunk message
                    message = {
                        "type": "audio_chunk",
                        "data": encoded_audio,
                        "audio_format": {
                            "sample_rate": INPUT_RATE,
                            "channels": CHANNELS,
                            "mime_type": f"audio/pcm;rate={INPUT_RATE}"
                        }
                    }
                    
                    await self.websocket.send(json.dumps(message))
                    print(f"📤 Sent audio chunk: {len(audio_buffer)} bytes ({BUFFER_DURATION}s)")
                    audio_buffer = b""
            
            await asyncio.sleep(0.05)
        
        print("📤 Audio sender stopped")
    
    async def message_receiver(self):
        """Receive and process messages from WebSocket"""
        print("📥 Message receiver started...")
        
        while self.running and self.websocket:
            try:
                raw_message = await self.websocket.recv()
                message = json.loads(raw_message)
                message_type = message.get("type")
                
                if message_type == "connected":
                    print(f"✅ Connected: {message.get('message')}")
                    print(f"👤 User ID: {message.get('user_id')}")
                    
                    # Start voice session
                    await self.websocket.send(json.dumps({"type": "start_voice_session"}))
                    print("🎙️ Voice session started")
                
                elif message_type == "voice_session_started":
                    print(f"🎙️ {message.get('message')}")
                
                elif message_type == "audio_response":
                    # Decode and queue audio response
                    audio_data = base64.b64decode(message.get("data", ""))
                    if audio_data:
                        self.response_queue.put(audio_data)
                        print(f"📥 Received audio response: {len(audio_data)} bytes")
                
                elif message_type == "text_response":
                    print(f"💬 Assistant: {message.get('text')}")
                
                elif message_type == "function_executed":
                    function_name = message.get("function_name")
                    print(f"⚡ Executed: {function_name}")
                
                elif message_type == "session_state":
                    current = message.get("current_index", 0)
                    total = message.get("total_messages", 0)
                    has_more = message.get("has_more", False)
                    print(f"📊 Session: {current + 1}/{total}" + (" (+more)" if has_more else ""))
                
                elif message_type == "error":
                    print(f"❌ Error response: {json.dumps(message, indent=2)}")
                
                else:
                    print(f"❓ Unknown message type: {message_type}")
                
            except websockets.exceptions.ConnectionClosed:
                print("🔌 WebSocket connection closed")
                break
            except Exception as e:
                print(f"📥 Message receiver error: {e}")
                break
        
        print("📥 Message receiver stopped")
    
    async def create_session(self) -> bool:
        """Create a voice session via REST API"""
        try:
            print(f"🔄 Creating voice session...")

            headers = {"Content-Type": "application/json"}
            if self.firebase_token:
                headers["Authorization"] = f"Bearer {self.firebase_token}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_BASE_URL}/sessions",
                    json={},  # Empty body as CreateSessionRequest has no required fields
                    headers=headers
                ) as response:
                    if response.status == 201:  # Created
                        data = await response.json()
                        self.session_id = data.get("session_id")
                        gmail_authorized = data.get("gmail_authorized", False)
                        requires_gmail_auth = data.get("requires_gmail_auth", False)
                        gmail_auth_url = data.get("gmail_auth_url")

                        print(f"✅ Session created: {self.session_id}")

                        # Check if Gmail authorization is required
                        if requires_gmail_auth:
                            print("\n" + "=" * 60)
                            print("⚠️  GMAIL AUTHORIZATION REQUIRED")
                            print("=" * 60)
                            print("📧 You need to authorize Gmail access to use this assistant.")
                            print(f"\n🔗 Please open this URL in your browser:")
                            print(f"\n{gmail_auth_url}\n")
                            print("After authorizing, press Enter to continue...")
                            input()

                            # Verify authorization was completed
                            if not await self._verify_gmail_auth():
                                print("❌ Gmail authorization not completed. Cannot proceed.")
                                return False

                            print("✅ Gmail authorization verified!")

                        # Build WebSocket URL with session_id and user_id
                        self.websocket_url = f"{WEBSOCKET_URL}?session_id={self.session_id}&firebase_user_id={self.firebase_user_id}"
                        print(f"📡 WebSocket URL: {self.websocket_url}")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to create session: {response.status} - {error_text}")
                        return False

        except Exception as e:
            print(f"❌ Session creation error: {e}")
            return False

    async def _verify_gmail_auth(self) -> bool:
        """Verify that Gmail authorization was completed"""
        try:
            headers = {}
            if self.firebase_token:
                headers["Authorization"] = f"Bearer {self.firebase_token}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{API_BASE_URL}/auth/gmail/status",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("is_authorized", False)
                    return False

        except Exception as e:
            print(f"⚠️  Error verifying Gmail auth: {e}")
            return False

    async def delete_session(self):
        """Delete the voice session via REST API"""
        if not self.session_id:
            return

        try:
            print(f"🗑️  Deleting session {self.session_id}...")

            headers = {}
            if self.firebase_token:
                headers["Authorization"] = f"Bearer {self.firebase_token}"

            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{API_BASE_URL}/sessions/{self.session_id}",
                    params={"firebase_user_id": self.firebase_user_id},
                    headers=headers
                ) as response:
                    if response.status == 200:
                        print(f"✅ Session deleted")
                    else:
                        print(f"⚠️  Failed to delete session: {response.status}")

        except Exception as e:
            print(f"⚠️  Session deletion error: {e}")

    async def connect_and_run(self):
        """Connect to WebSocket and start conversation"""
        try:
            # First, create a session via REST API
            if not await self.create_session():
                print("❌ Cannot proceed without a session")
                return

            print(f"🔌 Connecting to {self.websocket_url}...")

            async with websockets.connect(self.websocket_url) as websocket:
                self.websocket = websocket
                print("🔌 WebSocket connected!")

                # Start audio recording and playback
                self.start_recording()
                self.start_playback()

                # Run audio sender and message receiver concurrently
                await asyncio.gather(
                    self.audio_sender(),
                    self.message_receiver()
                )

        except Exception as e:
            print(f"❌ Connection error: {e}")
        finally:
            # Clean up session
            await self.delete_session()
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up...")
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())
        self.audio.terminate()
        print("🧹 Cleanup complete")


async def main():
    """Main function to run the Gmail voice client"""
    print("=" * 60)
    print("🎙️  GMAIL VOICE ASSISTANT CLIENT")
    print("=" * 60)

    # Firebase authentication
    print("\n🔐 Firebase Authentication")
    print("=" * 60)
    email = input("📧 Email: ").strip()

    if not email:
        print("❌ Email is required. Exiting.")
        return

    password = getpass.getpass("🔒 Password: ")

    if not password:
        print("❌ Password is required. Exiting.")
        return

    # Authenticate with Firebase
    firebase_token, firebase_user_id = firebase_sign_in(email, password)

    if not firebase_token or not firebase_user_id:
        print("❌ Authentication failed. Cannot proceed.")
        return

    client = GmailVoiceClient(firebase_user_id, firebase_token)
    
    try:
        print("\n🚀 Starting Gmail Voice Assistant...")
        print("💬 Say things like:")
        print("   - 'Read my unread emails'")
        print("   - 'Next message'") 
        print("   - 'Summarize this message'")
        print("   - 'Mark as read'")
        print("   - 'Draft a reply saying thanks'")
        print("\n⏹️  Press Ctrl+C to quit")
        print("-" * 60)
        
        await client.connect_and_run()
        
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down...")
    finally:
        client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
