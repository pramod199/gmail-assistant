import { logger } from "./logger";

const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_BASE_URL || "ws://localhost:8000/api/voice";

export type JsonMessageHandler = (msg: Record<string, unknown>) => void;
export type AudioDataHandler = (data: ArrayBuffer) => void;
export type CloseHandler = () => void;

export class WebSocketManager {
  private ws: WebSocket | null = null;
  onJsonMessage: JsonMessageHandler = () => {};
  onAudioData: AudioDataHandler = () => {};
  onClose: CloseHandler = () => {};

  connect(sessionId: string, firebaseUserId: string, onOpen?: () => void) {
    const url = `${WS_BASE_URL}/voice?session_id=${sessionId}&firebase_user_id=${firebaseUserId}`;
    logger.info(`WebSocket connecting to ${url}`);

    this.ws = new WebSocket(url);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      logger.info("WebSocket connected");
      onOpen?.();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof ArrayBuffer) {
        this.onAudioData(event.data);
      } else {
        try {
          const msg = JSON.parse(event.data as string);
          this.onJsonMessage(msg);
        } catch (e) {
          logger.error(`Failed to parse WebSocket message: ${e}`);
        }
      }
    };

    this.ws.onerror = (event) => {
      logger.error(`WebSocket error: ${event}`);
    };

    this.ws.onclose = (event) => {
      logger.warn(
        `WebSocket closed: code=${event.code} reason=${event.reason}`
      );
      this.ws = null;
      this.onClose();
    };
  }

  sendJson(msg: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  sendAudio(chunk: ArrayBuffer) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      if (this.ws.bufferedAmount > 65536) return; // backpressure
      this.ws.send(chunk);
    }
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
