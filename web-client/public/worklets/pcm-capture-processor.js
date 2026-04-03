class PCMCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Int16Array(512); // 512 samples = 1024 bytes
    this._bufferIndex = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0]; // mono channel

    for (let i = 0; i < channelData.length; i++) {
      // Float32 [-1.0, 1.0] -> Int16 [-32768, 32767]
      const s = Math.max(-1, Math.min(1, channelData[i]));
      this._buffer[this._bufferIndex++] = s < 0 ? s * 0x8000 : s * 0x7fff;

      if (this._bufferIndex >= 512) {
        // Send 1024 bytes (512 Int16 samples)
        this.port.postMessage(this._buffer.buffer.slice(0));
        this._bufferIndex = 0;
      }
    }

    return true;
  }
}

registerProcessor("pcm-capture-processor", PCMCaptureProcessor);
