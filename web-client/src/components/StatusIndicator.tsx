"use client";

import type { Phase, SessionState } from "@/lib/use-voice-session";

const phaseLabels: Record<Phase, string> = {
  idle: "Offline",
  authenticating: "Signing in...",
  authenticated: "Signed in",
  connecting: "Connecting...",
  connected: "Connected",
  voice_active: "Live",
};

const phaseDot: Record<Phase, string> = {
  idle: "bg-gray-500",
  authenticating: "bg-yellow-500 animate-pulse",
  authenticated: "bg-blue-500",
  connecting: "bg-yellow-500 animate-pulse",
  connected: "bg-green-500",
  voice_active: "bg-red-500 animate-pulse",
};

export function StatusIndicator({
  phase,
  sessionState,
}: {
  phase: Phase;
  sessionState: SessionState;
}) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-400">
      <div className="flex items-center gap-1.5">
        <div className={`w-1.5 h-1.5 rounded-full ${phaseDot[phase]}`} />
        <span>{phaseLabels[phase]}</span>
      </div>
      {sessionState.totalMessages !== undefined && (
        <span className="text-gray-600">
          {(sessionState.currentIndex ?? 0) + 1}/{sessionState.totalMessages}
          {sessionState.hasMore ? "+" : ""}
        </span>
      )}
    </div>
  );
}
