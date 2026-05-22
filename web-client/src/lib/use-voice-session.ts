"use client";

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  useSyncExternalStore,
} from "react";
import { firebaseSignIn } from "./firebase-auth";
import { createSession, deleteSession } from "./session-api";
import { WebSocketManager } from "./websocket-manager";
import { AudioCapture } from "./audio-capture";
import { AudioPlayback } from "./audio-playback";
import { logger, type LogEntry } from "./logger";

export type Phase =
  | "idle"
  | "authenticating"
  | "authenticated"
  | "connecting"
  | "connected"
  | "voice_active";

export interface SessionState {
  currentIndex?: number;
  totalMessages?: number;
  hasMore?: boolean;
}

export type ConversationEvent =
  | { type: "assistant"; text: string }
  | { type: "user_transcription"; text: string }
  | {
      type: "function";
      name: string;
      args: Record<string, unknown>;
      result?: Record<string, unknown>;
    }
  | { type: "error"; message: string };

export function useVoiceSession() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [authError, setAuthError] = useState<string | null>(null);
  const [gmailAuthUrl, setGmailAuthUrl] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>({});
  const [conversation, setConversation] = useState<ConversationEvent[]>([]);
  const [micVolume, setMicVolume] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakerVolume, setSpeakerVolume] = useState(0);
  const [audioOut, setAudioOut] = useState(0); // bytes sent to server
  const [audioIn, setAudioIn] = useState(0); // bytes received from server
  const [subtitle, setSubtitle] = useState(""); // live transcription of model speech
  const [userSubtitle, setUserSubtitle] = useState(""); // live transcription of user speech

  const tokenRef = useRef<string>("");
  const userIdRef = useRef<string>("");
  const sessionIdRef = useRef<string>("");
  const wsRef = useRef<WebSocketManager | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const playbackRef = useRef<AudioPlayback | null>(null);
  const autoConnectDone = useRef(false);

  const logs = useSyncExternalStore(
    logger.subscribe,
    logger.getSnapshot,
    logger.getServerSnapshot
  );

  const addConversationEvent = useCallback((event: ConversationEvent) => {
    setConversation((prev) => [...prev, event]);
  }, []);

  // Merge streaming transcription chunks into the last matching event
  // instead of creating a new event per chunk.
  const appendTranscription = useCallback(
    (type: "assistant" | "user_transcription", chunk: string) => {
      setConversation((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.type === type) {
          const updated: ConversationEvent = { type, text: last.text + chunk };
          return [...prev.slice(0, -1), updated];
        }
        return [...prev, { type, text: chunk }];
      });
    },
    []
  );

  const handleJsonMessage = useCallback(
    (msg: Record<string, unknown>) => {
      const type = msg.type as string;

      switch (type) {
        case "connected":
          logger.info(
            `Connected: ${msg.message} (user=${msg.user_id}, session=${msg.session_id})`
          );
          break;

        case "voice_session_started":
          logger.info("Voice session started - ready to receive audio");
          break;

        case "voice_session_ended":
          logger.info("Voice session ended");
          break;

        case "voice_session_recovered":
          logger.warn("Voice session recovered after error");
          break;

        case "text_response":
          logger.info(`Assistant: ${msg.text}`);
          addConversationEvent({
            type: "assistant",
            text: msg.text as string,
          });
          break;

        case "function_executed":
          logger.info(
            `Function: ${msg.function_name}(${JSON.stringify(msg.args || {})})`
          );
          addConversationEvent({
            type: "function",
            name: msg.function_name as string,
            args: (msg.args as Record<string, unknown>) || {},
            result: (msg.result as Record<string, unknown>) || undefined,
          });
          break;

        case "input_transcription":
          if (msg.text) {
            const chunk = msg.text as string;
            setUserSubtitle((prev) => prev + chunk);
            appendTranscription("user_transcription", chunk);
          }
          break;

        case "output_transcription":
          if (msg.text) {
            const chunk = msg.text as string;
            setSubtitle((prev) => prev + chunk);
            appendTranscription("assistant", chunk);
          }
          break;

        case "generation_complete":
          logger.info("Generation complete");
          // Clear live subtitles; finalized text remains in conversation log
          setSubtitle("");
          setUserSubtitle("");
          break;

        case "stop_audio":
          logger.warn("Interruption detected - flushing audio");
          playbackRef.current?.flush();
          setSubtitle("");
          break;

        case "session_state":
          setSessionState({
            currentIndex: msg.current_index as number,
            totalMessages: msg.total_messages as number,
            hasMore: msg.has_more as boolean,
          });
          break;

        case "session_recreated":
          sessionIdRef.current = msg.new_session_id as string;
          logger.warn(
            `Session recreated: ${msg.old_session_id} -> ${msg.new_session_id}`
          );
          break;

        case "error":
          logger.error(`Server error: ${msg.message}`);
          addConversationEvent({
            type: "error",
            message: msg.message as string,
          });
          if (msg.auth_url) {
            setGmailAuthUrl(msg.auth_url as string);
          }
          break;

        default:
          logger.info(`Unknown message type: ${type} - ${JSON.stringify(msg)}`);
      }
    },
    [addConversationEvent, appendTranscription]
  );

  const login = useCallback(async (email: string, password: string) => {
    setAuthError(null);
    setPhase("authenticating");
    try {
      logger.info(`Signing in as ${email}...`);
      const result = await firebaseSignIn(email, password);
      tokenRef.current = result.idToken;
      userIdRef.current = result.localId;
      logger.info(`Authenticated as ${result.email} (${result.localId})`);
      setPhase("authenticated");
      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      logger.error(`Auth failed: ${msg}`);
      setAuthError(msg);
      setPhase("idle");
      return false;
    }
  }, []);

  const connect = useCallback(async () => {
    setPhase("connecting");
    setGmailAuthUrl(null);

    try {
      logger.info("Creating session...");
      const session = await createSession(tokenRef.current);
      sessionIdRef.current = session.session_id;
      logger.info(`Session created: ${session.session_id}`);

      if (session.requires_gmail_auth && session.gmail_auth_url) {
        setGmailAuthUrl(session.gmail_auth_url);
        logger.warn(
          "Gmail authorization required. Please authorize and reconnect."
        );
        setPhase("authenticated");
        return false;
      }

      // Set up audio playback with speaking state callback
      const playback = new AudioPlayback();
      playback.onSpeakingChange = setIsSpeaking;
      playback.onVolumeChange = setSpeakerVolume;
      playbackRef.current = playback;

      // Set up WebSocket
      const ws = new WebSocketManager();
      ws.onJsonMessage = handleJsonMessage;
      ws.onAudioData = (data) => {
        playbackRef.current?.enqueue(data);
        setAudioIn((prev) => prev + data.byteLength);
      };
      ws.onClose = () => {
        logger.warn("Connection lost");
        captureRef.current?.stop();
        captureRef.current = null;
        setPhase("authenticated");
      };
      // Connect and wait for WS to open before starting voice
      await new Promise<void>((resolve, reject) => {
        const origOnOpen = () => resolve();
        const origOnClose = ws.onClose;
        ws.onClose = () => {
          reject(new Error("WebSocket closed before opening"));
          origOnClose();
        };
        ws.connect(sessionIdRef.current, userIdRef.current, origOnOpen);
        wsRef.current = ws;
      });

      setPhase("connected");
      logger.info("Connected. Auto-activating mic...");

      // Auto-activate mic after connection
      try {
        await playbackRef.current?.resume();
        wsRef.current?.sendJson({ type: "start_voice_session" });
        logger.info("Sent start_voice_session");

        const capture = new AudioCapture();
        await capture.start(
          (chunk) => {
            wsRef.current?.sendAudio(chunk);
            setAudioOut((prev) => prev + chunk.byteLength);
          },
          (volume) => {
            setMicVolume(volume);
          }
        );
        captureRef.current = capture;
        setPhase("voice_active");
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        logger.error(`Auto-start mic failed: ${msg}`);
      }
      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      logger.error(`Connect failed: ${msg}`);
      setPhase("authenticated");
      return false;
    }
  }, [handleJsonMessage]);

  const startVoice = useCallback(async () => {
    if (!wsRef.current?.connected) return;

    try {
      // Resume playback context (requires user gesture)
      await playbackRef.current?.resume();

      // Send start command
      wsRef.current.sendJson({ type: "start_voice_session" });
      logger.info("Sent start_voice_session");

      // Start mic capture with volume callback
      const capture = new AudioCapture();
      await capture.start(
        (chunk) => {
          wsRef.current?.sendAudio(chunk);
          setAudioOut((prev) => prev + chunk.byteLength);
        },
        (volume) => {
          setMicVolume(volume);
        }
      );
      captureRef.current = capture;

      setPhase("voice_active");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      logger.error(`Start voice failed: ${msg}`);
    }
  }, []);

  const stopVoice = useCallback(() => {
    captureRef.current?.stop();
    captureRef.current = null;

    wsRef.current?.sendJson({ type: "end_voice_session" });
    logger.info("Sent end_voice_session");

    playbackRef.current?.flush();
    setMicVolume(0);
    setPhase("connected");
  }, []);

  const disconnect = useCallback(() => {
    captureRef.current?.stop();
    captureRef.current = null;

    wsRef.current?.sendJson({ type: "end_voice_session" });
    wsRef.current?.disconnect();
    wsRef.current = null;

    playbackRef.current?.close();
    playbackRef.current = null;

    if (sessionIdRef.current) {
      deleteSession(
        sessionIdRef.current,
        tokenRef.current,
        userIdRef.current
      ).catch(() => {});
      logger.info(`Session ${sessionIdRef.current} deleted`);
      sessionIdRef.current = "";
    }

    setGmailAuthUrl(null);
    setSessionState({});
    setMicVolume(0);
    setIsSpeaking(false);
    setSpeakerVolume(0);
    setAudioOut(0);
    setAudioIn(0);
    setSubtitle("");
    setUserSubtitle("");
    setPhase("authenticated");
  }, []);

  const clearLogs = useCallback(() => {
    logger.clear();
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnectDone.current) return;
    autoConnectDone.current = true;

    (async () => {
      const loggedIn = await login("test@example.com", "testpass123");
      if (!loggedIn) return;

      // Small delay to let state settle
      await new Promise((r) => setTimeout(r, 100));
    })();
  }, [login]);

  const getToken = useCallback(() => tokenRef.current, []);

  return {
    phase,
    authError,
    gmailAuthUrl,
    sessionState,
    conversation,
    micVolume,
    isSpeaking,
    speakerVolume,
    audioOut,
    audioIn,
    subtitle,
    userSubtitle,
    logs,
    login,
    connect,
    startVoice,
    stopVoice,
    disconnect,
    clearLogs,
    getToken,
  };
}
