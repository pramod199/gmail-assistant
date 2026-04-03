"use client";

import type { Phase, SessionState } from "@/lib/use-voice-session";
import type { LogEntry } from "@/lib/logger";
import { StatusIndicator } from "./StatusIndicator";
import { LogPanel } from "./LogPanel";

interface VoiceInterfaceProps {
  phase: Phase;
  gmailAuthUrl: string | null;
  sessionState: SessionState;
  logs: LogEntry[];
  onConnect: () => void;
  onDisconnect: () => void;
  onStartVoice: () => void;
  onStopVoice: () => void;
  onClearLogs: () => void;
}

export function VoiceInterface({
  phase,
  gmailAuthUrl,
  sessionState,
  logs,
  onConnect,
  onDisconnect,
  onStartVoice,
  onStopVoice,
  onClearLogs,
}: VoiceInterfaceProps) {
  const isConnected = phase === "connected" || phase === "voice_active";
  const isVoiceActive = phase === "voice_active";

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h1 className="text-lg font-semibold">Gmail Voice Assistant</h1>
        <StatusIndicator phase={phase} sessionState={sessionState} />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-4 p-6">
        {!isConnected && (
          <button
            onClick={onConnect}
            disabled={phase === "connecting"}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
          >
            {phase === "connecting" ? "Connecting..." : "Connect"}
          </button>
        )}

        {isConnected && (
          <>
            {/* Mic button */}
            <button
              onClick={isVoiceActive ? onStopVoice : onStartVoice}
              className={`w-20 h-20 rounded-full flex items-center justify-center text-3xl transition-all ${
                isVoiceActive
                  ? "bg-red-600 hover:bg-red-700 shadow-lg shadow-red-600/30 animate-pulse"
                  : "bg-green-600 hover:bg-green-700 shadow-lg shadow-green-600/20"
              }`}
              title={isVoiceActive ? "Stop listening" : "Start listening"}
            >
              {isVoiceActive ? (
                // Stop icon
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="w-8 h-8"
                >
                  <rect x="6" y="6" width="12" height="12" rx="1" />
                </svg>
              ) : (
                // Mic icon
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="w-8 h-8"
                >
                  <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                  <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                </svg>
              )}
            </button>

            <button
              onClick={onDisconnect}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
            >
              Disconnect
            </button>
          </>
        )}
      </div>

      {/* Gmail Auth Link */}
      {gmailAuthUrl && (
        <div className="mx-4 mb-2 p-3 bg-yellow-900/30 border border-yellow-700 rounded-lg text-sm">
          <span className="text-yellow-300">Gmail authorization required: </span>
          <a
            href={gmailAuthUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 underline hover:text-blue-300"
          >
            Authorize Gmail Access
          </a>
          <span className="text-yellow-300">
            {" "}
            — then click Connect again.
          </span>
        </div>
      )}

      {/* Log Panel */}
      <div className="flex-1 mx-4 mb-4 bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
        <LogPanel logs={logs} onClear={onClearLogs} />
      </div>
    </div>
  );
}
