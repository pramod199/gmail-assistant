import { logger } from "./logger";

export class AudioCapture {
  private audioContext: AudioContext | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private stream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private volumeInterval: ReturnType<typeof setInterval> | null = null;

  async start(
    onChunk: (data: ArrayBuffer) => void,
    onVolume?: (volume: number) => void
  ): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
        sampleRate: 16000,
      },
    });

    this.audioContext = new AudioContext({ sampleRate: 16000 });
    logger.info(
      `Mic AudioContext sample rate: ${this.audioContext.sampleRate}Hz`
    );

    await this.audioContext.audioWorklet.addModule(
      "/worklets/pcm-capture-processor.js"
    );

    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(
      this.audioContext,
      "pcm-capture-processor"
    );

    this.workletNode.port.onmessage = (e: MessageEvent) => {
      onChunk(e.data as ArrayBuffer);
    };

    this.sourceNode.connect(this.workletNode);
    this.workletNode.connect(this.audioContext.destination);

    // Set up volume analyser
    if (onVolume) {
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      this.sourceNode.connect(this.analyser);

      const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
      this.volumeInterval = setInterval(() => {
        if (!this.analyser) return;
        this.analyser.getByteFrequencyData(dataArray);
        // Average of frequency bins, normalized to 0-1
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        onVolume(sum / dataArray.length / 255);
      }, 50);
    }

    logger.info("Mic capture started");
  }

  stop() {
    if (this.volumeInterval) {
      clearInterval(this.volumeInterval);
      this.volumeInterval = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    logger.info("Mic capture stopped");
  }
}
