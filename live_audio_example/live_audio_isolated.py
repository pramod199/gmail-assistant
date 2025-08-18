# Real-time audio chat with Gemini Live using PyAudio
# Install requirements: pip install pyaudio google-genai

import asyncio
import threading
import queue
import pyaudio
from google import genai
from google.genai import types

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
INPUT_RATE = 16000
OUTPUT_RATE = 24000
BUFFER_DURATION = 0.5

class RealTimeAudioChat:
    def __init__(self):
        self.client = genai.Client()
        self.model = "gemini-2.5-flash-live-preview"
        
        self.config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": "You are a helpful assistant and answer in a friendly tone.",
        }
        
        self.audio = pyaudio.PyAudio()
        self.audio_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.running = True
        self.is_playing_audio = False
        
    def start_recording(self):
        def record_audio():
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            while self.running:
                try:
                    # Only record if not playing audio
                    if not self.is_playing_audio:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        self.audio_queue.put(data)
                    else:
                        # Read and discard to keep stream active
                        stream.read(CHUNK, exception_on_overflow=False)
                except:
                    break
                    
            stream.stop_stream()
            stream.close()
        
        threading.Thread(target=record_audio, daemon=True).start()
    
    def start_playback(self):
        def play_audio():
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=OUTPUT_RATE,
                output=True,
                frames_per_buffer=CHUNK
            )
            
            while self.running:
                try:
                    audio_data = self.response_queue.get(timeout=0.1)
                    self.is_playing_audio = True
                    stream.write(audio_data)
                    self.is_playing_audio = False
                except queue.Empty:
                    continue
                except:
                    break
            
            stream.stop_stream()
            stream.close()
        
        threading.Thread(target=play_audio, daemon=True).start()
    
    async def audio_sender(self, session):
        audio_buffer = b""
        chunk_size = int(INPUT_RATE * BUFFER_DURATION * 2)
        
        while self.running:
            while not self.audio_queue.empty():
                data = self.audio_queue.get_nowait()
                audio_buffer += data
                
                if len(audio_buffer) >= chunk_size:
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=audio_buffer, 
                            mime_type="audio/pcm;rate=16000"
                        )
                    )
                    print(f"📤 Sent audio chunk: {len(audio_buffer)} bytes")
                    audio_buffer = b""
            
            await asyncio.sleep(0.05)
    
    async def response_receiver(self, session):
        while self.running:
            try:
                async for response in session.receive():
                    if not self.running:
                        break
                    if response.data is not None:
                        print(f"📥 Received audio response: {len(response.data)} bytes")
                        self.response_queue.put(response.data)
            except:
                break
    
    async def run_conversation(self):
        print("Starting conversation... Press Ctrl+C to quit")
        
        async with self.client.aio.live.connect(
            model=self.model, 
            config=self.config
        ) as session:
            
            self.start_recording()
            self.start_playback()
            
            # Run both tasks concurrently
            await asyncio.gather(
                self.audio_sender(session),
                self.response_receiver(session)
            )
    
    def cleanup(self):
        self.running = False
        self.audio.terminate()

async def main():
    chat = RealTimeAudioChat()
    try:
        await chat.run_conversation()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        chat.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
