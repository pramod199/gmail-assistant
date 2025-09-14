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
from typing import Optional

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
INPUT_RATE = 16000
OUTPUT_RATE = 24000
BUFFER_DURATION = 1.5  # Send chunks every 1.5 seconds (was 0.5s)

# Server configuration
WEBSOCKET_URL = "ws://localhost:8000/api/voice/voice"


class GmailVoiceClient:
    """PyAudio client that streams audio to our Gmail voice assistant WebSocket endpoint"""
    
    def __init__(self, firebase_user_id: str):
        self.firebase_user_id = firebase_user_id
        self.websocket_url = f"{WEBSOCKET_URL}?firebase_user_id={firebase_user_id}"
        
        self.audio = pyaudio.PyAudio()
        self.audio_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.running = True
        self.is_playing_audio = False  # Audio isolation flag
        self.websocket = None
        
        print(f"🔊 Gmail Voice Client initialized")
        print(f"📡 WebSocket URL: {self.websocket_url}")
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
    
    async def connect_and_run(self):
        """Connect to WebSocket and start conversation"""
        try:
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
    
    # Get Firebase user ID from user
    print("\n📋 You need a Firebase User ID to connect.")
    print("💡 Authentication is now handled at the app level.")
    print("💡 Use your Firebase UID (e.g., 'user123' or actual Firebase UID)")
    firebase_user_id = input("🔑 Enter your Firebase User ID: ").strip()
    
    if not firebase_user_id:
        print("❌ No Firebase User ID provided. Exiting.")
        return
    
    client = GmailVoiceClient(firebase_user_id)
    
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