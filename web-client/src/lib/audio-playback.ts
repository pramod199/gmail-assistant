import { logger } from "./logger";

export class AudioPlayback {
  private audioContext: AudioContext;
  private analyser: AnalyserNode;
  private nextStartTime = 0;
  private activeSources: AudioBufferSourceNode[] = [];
  private volumeInterval: ReturnType<typeof setInterval> | null = null;
  onSpeakingChange: ((speaking: boolean) => void) | null = null;
  onVolumeChange: ((volume: number) => void) | null = null;

  constructor() {
    this.audioContext = new AudioContext({ sampleRate: 24000 });
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.connect(this.audioContext.destination);
    logger.info(
      `Playback AudioContext sample rate: ${this.audioContext.sampleRate}Hz`
    );
  }

  async resume() {
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
    // Start polling volume
    if (!this.volumeInterval) {
      const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      this.volumeInterval = setInterval(() => {
        this.analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        this.onVolumeChange?.(sum / dataArray.length / 255);
      }, 50);
    }
  }

  private updateSpeaking() {
    this.onSpeakingChange?.(this.activeSources.length > 0);
  }

  enqueue(pcmData: ArrayBuffer) {
    const int16 = new Int16Array(pcmData);
    const float32 = new Float32Array(int16.length);

    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    const audioBuffer = this.audioContext.createBuffer(
      1,
      float32.length,
      24000
    );
    audioBuffer.getChannelData(0).set(float32);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    // Route through analyser so we can read output levels
    source.connect(this.analyser);

    const now = this.audioContext.currentTime;
    if (this.nextStartTime < now) {
      this.nextStartTime = now;
    }

    source.start(this.nextStartTime);
    this.nextStartTime += audioBuffer.duration;

    this.activeSources.push(source);
    this.updateSpeaking();

    source.onended = () => {
      const idx = this.activeSources.indexOf(source);
      if (idx !== -1) this.activeSources.splice(idx, 1);
      this.updateSpeaking();
    };
  }

  flush() {
    logger.info("Flushing audio playback queue");
    for (const source of this.activeSources) {
      try {
        source.stop();
      } catch {
        // already stopped
      }
    }
    this.activeSources = [];
    this.nextStartTime = 0;
    this.updateSpeaking();
  }

  close() {
    if (this.volumeInterval) {
      clearInterval(this.volumeInterval);
      this.volumeInterval = null;
    }
    this.flush();
    this.audioContext.close();
  }
}
