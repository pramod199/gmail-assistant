"use client";

import { useState } from "react";
import type {
  Phase,
  SessionState,
  ConversationEvent,
} from "@/lib/use-voice-session";
import type { LogEntry } from "@/lib/logger";
import { StatusIndicator } from "./StatusIndicator";
import { LogPanel } from "./LogPanel";
import { ConversationPanel } from "./ConversationPanel";

interface VoiceInterfaceProps {
  phase: Phase;
  gmailAuthUrl: string | null;
  sessionState: SessionState;
  conversation: ConversationEvent[];
  micVolume: number;
  isSpeaking: boolean;
  speakerVolume: number;
  audioOut: number;
  audioIn: number;
  logs: LogEntry[];
  onConnect: () => void;
  onDisconnect: () => void;
  onStartVoice: () => void;
  onStopVoice: () => void;
  onClearLogs: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function MicButton({
  isActive,
  isSpeaking,
  micVolume,
  onClick,
}: {
  isActive: boolean;
  isSpeaking: boolean;
  micVolume: number;
  onClick: () => void;
}) {
  const ringScale = isActive ? 1 + micVolume * 0.5 : 1;
  const ringOpacity = isActive ? 0.3 + micVolume * 0.5 : 0;

  return (
    <div className="relative flex items-center justify-center">
      <div
        className="absolute w-20 h-20 rounded-full transition-transform duration-75"
        style={{
          transform: `scale(${ringScale})`,
          opacity: ringOpacity,
          background: isActive
            ? "radial-gradient(circle, rgba(239,68,68,0.4) 0%, transparent 70%)"
            : "none",
        }}
      />
      {isSpeaking && !isActive && (
        <div className="absolute w-20 h-20 rounded-full animate-ping opacity-20 bg-blue-500" />
      )}
      <button
        onClick={onClick}
        className={`relative z-10 w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-lg ${
          isActive
            ? "bg-red-600 hover:bg-red-700 shadow-red-600/40"
            : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-600/30"
        }`}
        title={isActive ? "Stop listening" : "Start listening"}
      >
        {isActive ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
          </svg>
        )}
      </button>
    </div>
  );
}

function AudioControlStrip({
  phase,
  micVolume,
  isSpeaking,
  speakerVolume,
  audioOut,
  audioIn,
  onStartVoice,
  onStopVoice,
  onConnect,
}: {
  phase: Phase;
  micVolume: number;
  isSpeaking: boolean;
  speakerVolume: number;
  audioOut: number;
  audioIn: number;
  onStartVoice: () => void;
  onStopVoice: () => void;
  onConnect: () => void;
}) {
  const isConnected = phase === "connected" || phase === "voice_active";
  const isVoiceActive = phase === "voice_active";

  if (!isConnected) {
    return (
      <div className="flex items-center justify-center py-5 border-b border-gray-800/40 bg-gray-950/50">
        <button
          onClick={onConnect}
          disabled={phase === "connecting"}
          className="px-8 py-3 text-base bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-medium transition-colors"
        >
          {phase === "connecting" ? "Connecting..." : "Connect"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center gap-6 py-4 px-4 border-b border-gray-800/40 bg-gray-950/50">
      {/* Mic input side */}
      <div className="flex items-center gap-3 flex-1 justify-end">
        <div className="text-right">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Mic Input</div>
          <div className="text-sm font-mono text-gray-400">{formatBytes(audioOut)}</div>
        </div>
        {/* Volume bar - mic */}
        <div className="w-24 flex flex-col gap-1">
          <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-75"
              style={{ width: `${isVoiceActive ? Math.max(micVolume * 100, 2) : 0}%` }}
            />
          </div>
          <div className="flex justify-between">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`w-1 h-1 rounded-full transition-colors ${
                  isVoiceActive && micVolume > i * 0.2
                    ? "bg-green-400"
                    : "bg-gray-700"
                }`}
              />
            ))}
          </div>
        </div>
        {/* Up arrow */}
        <svg
          className={`w-5 h-5 transition-colors ${
            isVoiceActive && micVolume > 0.05 ? "text-green-400" : "text-gray-700"
          }`}
          fill="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z" />
        </svg>
      </div>

      {/* Center mic button */}
      <MicButton
        isActive={isVoiceActive}
        isSpeaking={isSpeaking}
        micVolume={micVolume}
        onClick={isVoiceActive ? onStopVoice : onStartVoice}
      />

      {/* Speaker output side */}
      <div className="flex items-center gap-3 flex-1">
        {/* Down arrow */}
        <svg
          className={`w-5 h-5 transition-colors ${
            isSpeaking ? "text-blue-400" : "text-gray-700"
          }`}
          fill="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M20 12l-1.41-1.41L13 16.17V4h-2v12.17l-5.58-5.59L4 12l8 8 8-8z" />
        </svg>
        {/* Volume bar - speaker */}
        <div className="w-24 flex flex-col gap-1">
          <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-75"
              style={{ width: `${isSpeaking ? Math.max(speakerVolume * 100, 2) : 0}%` }}
            />
          </div>
          <div className="flex justify-between">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`w-1 h-1 rounded-full transition-colors ${
                  isSpeaking && speakerVolume > i * 0.2 ? "bg-blue-400" : "bg-gray-700"
                }`}
              />
            ))}
          </div>
        </div>
        <div className="text-left">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Speaker</div>
          <div className="text-sm font-mono text-gray-400">{formatBytes(audioIn)}</div>
        </div>
      </div>
    </div>
  );
}

export function VoiceInterface({
  phase,
  gmailAuthUrl,
  sessionState,
  conversation,
  micVolume,
  isSpeaking,
  speakerVolume,
  audioOut,
  audioIn,
  logs,
  onConnect,
  onDisconnect,
  onStartVoice,
  onStopVoice,
  onClearLogs,
}: VoiceInterfaceProps) {
  const [logsOpen, setLogsOpen] = useState(false);
  const isConnected = phase === "connected" || phase === "voice_active";
  const isVoiceActive = phase === "voice_active";

  // State label text
  let stateText = "";
  if (isVoiceActive && isSpeaking) stateText = "Assistant speaking...";
  else if (isVoiceActive) stateText = "Listening...";
  else if (phase === "connected") stateText = "Press mic to start";

  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-gray-950 via-gray-950 to-gray-900 text-white">
      {/* Header — compact */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800/60 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          <h1 className="text-base font-semibold tracking-tight">
            Gmail Voice Assistant
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {stateText && (
            <span className={`text-sm ${
              isSpeaking ? "text-blue-400 animate-pulse" :
              isVoiceActive ? "text-red-400" : "text-gray-500"
            }`}>
              {stateText}
            </span>
          )}
          <StatusIndicator phase={phase} sessionState={sessionState} />
          {isConnected && (
            <button
              onClick={onDisconnect}
              className="px-3 py-1 text-xs text-gray-500 hover:text-gray-300 border border-gray-800 hover:border-gray-700 rounded transition-colors"
            >
              Disconnect
            </button>
          )}
        </div>
      </div>

      {/* Gmail Auth Banner */}
      {gmailAuthUrl && (
        <div className="mx-4 mt-2 p-3 bg-yellow-900/30 border border-yellow-700/50 rounded-lg text-sm shrink-0">
          <span className="text-yellow-300">Gmail auth required: </span>
          <a
            href={gmailAuthUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 underline hover:text-blue-300"
          >
            Authorize
          </a>
          <span className="text-yellow-300"> — then reconnect.</span>
        </div>
      )}

      {/* Audio control strip — prominent center position */}
      <AudioControlStrip
        phase={phase}
        micVolume={micVolume}
        isSpeaking={isSpeaking}
        speakerVolume={speakerVolume}
        audioOut={audioOut}
        audioIn={audioIn}
        onStartVoice={onStartVoice}
        onStopVoice={onStopVoice}
        onConnect={onConnect}
      />

      {/* Main content — responsive split */}
      <div className="flex-1 flex flex-col lg:flex-row min-h-0">
        {/* Conversation — takes most space */}
        <div className="flex-1 flex flex-col min-h-0 lg:min-w-0">
          <ConversationPanel events={conversation} />
        </div>

        {/* Logs sidebar on desktop, collapsible on mobile */}
        <div className="lg:w-[420px] lg:border-l border-t lg:border-t-0 border-gray-800/60 flex flex-col shrink-0">
          <button
            onClick={() => setLogsOpen(!logsOpen)}
            className="lg:hidden w-full flex items-center justify-between px-3 py-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            <span>Logs ({logs.length})</span>
            <svg
              className={`w-3 h-3 transition-transform ${logsOpen ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <div className={`${logsOpen ? "h-48" : "hidden"} lg:flex lg:flex-col lg:flex-1 lg:min-h-0`}>
            <LogPanel logs={logs} onClear={onClearLogs} />
          </div>
        </div>
      </div>
    </div>
  );
}
