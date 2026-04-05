"use client";

import type { Phase, SessionState } from "@/lib/use-voice-session";

interface StatusPillProps {
  phase: Phase;
  sessionState: SessionState;
  isSpeaking: boolean;
}

const phaseLabel: Record<Phase, string> = {
  idle: "Offline",
  authenticating: "Signing in",
  authenticated: "Signed in",
  connecting: "Connecting",
  connected: "Connected",
  voice_active: "Live",
};

type Tone = "neutral" | "accent" | "success" | "warn" | "live";

function toneFor(phase: Phase): Tone {
  switch (phase) {
    case "voice_active":
      return "live";
    case "connected":
      return "success";
    case "connecting":
    case "authenticating":
      return "warn";
    case "authenticated":
      return "accent";
    default:
      return "neutral";
  }
}

const toneBg: Record<Tone, string> = {
  neutral: "bg-[var(--surface-2)] border-[var(--border-subtle)]",
  accent: "bg-[var(--accent-soft)] border-[color:var(--accent)]/40",
  success: "bg-[var(--success-soft)] border-[color:var(--success)]/40",
  warn: "bg-[var(--warn-soft)] border-[color:var(--warn)]/40",
  live: "bg-[var(--live-soft)] border-[color:var(--live)]/50",
};

const toneDot: Record<Tone, string> = {
  neutral: "bg-[var(--text-4)]",
  accent: "bg-[var(--accent)]",
  success: "bg-[var(--success)]",
  warn: "bg-[var(--warn)]",
  live: "bg-[var(--live)]",
};

const toneGlow: Record<Tone, string> = {
  neutral: "none",
  accent: "0 0 14px rgba(99,102,241,0.35)",
  success: "0 0 14px rgba(16,185,129,0.4)",
  warn: "0 0 14px rgba(245,158,11,0.4)",
  live: "0 0 16px rgba(239,68,68,0.5)",
};

export function StatusPill({
  phase,
  sessionState,
  isSpeaking,
}: StatusPillProps) {
  const tone = toneFor(phase);
  const pulse =
    phase === "voice_active" ||
    phase === "connecting" ||
    phase === "authenticating";
  const label = phaseLabel[phase];

  // Sub-state for voice_active
  let substate: string | null = null;
  if (phase === "voice_active") {
    substate = isSpeaking ? "Speaking" : "Listening";
  } else if (phase === "connected") {
    substate = "Press mic";
  }

  const counter =
    sessionState.totalMessages !== undefined
      ? `${(sessionState.currentIndex ?? 0) + 1}/${sessionState.totalMessages}${sessionState.hasMore ? "+" : ""}`
      : null;

  return (
    <div
      className={`inline-flex items-center gap-2 sm:gap-2.5 h-8 sm:h-9 px-2.5 sm:px-3.5 rounded-[var(--r-full)] border ${toneBg[tone]} text-[13px] sm:text-[14px] transition-all min-w-0 max-w-full`}
      role="status"
      aria-live="polite"
      style={{ boxShadow: toneGlow[tone] }}
    >
      <span className="relative flex items-center justify-center shrink-0">
        {pulse && (
          <span
            className={`absolute w-3 h-3 rounded-full ${toneDot[tone]} opacity-40 animate-ping`}
          />
        )}
        <span className={`w-2 h-2 rounded-full ${toneDot[tone]}`} />
      </span>
      <span className="font-medium text-[var(--text-1)] truncate">{label}</span>
      {substate && (
        <>
          <span className="text-[var(--text-4)]">·</span>
          <span className="text-[var(--text-2)] truncate">{substate}</span>
        </>
      )}
      {counter && (
        <>
          <span className="text-[var(--text-4)] hidden sm:inline">·</span>
          <span className="t-mono text-[12px] sm:text-[13px] text-[var(--text-3)] hidden sm:inline">
            {counter}
          </span>
        </>
      )}
    </div>
  );
}
