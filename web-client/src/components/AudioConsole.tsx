"use client";

import { useEffect, useRef, useState } from "react";
import type { Phase } from "@/lib/use-voice-session";

interface AudioConsoleProps {
  phase: Phase;
  micVolume: number;
  isSpeaking: boolean;
  speakerVolume: number;
  audioOut: number;
  audioIn: number;
  onStartVoice: () => void;
  onStopVoice: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * Fake frequency visualizer — bars that react to the volume signal with
 * staggered random multipliers so it feels alive.
 */
function FreqBars({
  volume,
  active,
  color,
  count = 14,
  align = "left",
}: {
  volume: number;
  active: boolean;
  color: string;
  count?: number;
  align?: "left" | "right";
}) {
  // Stable per-bar phase offsets.
  const phasesRef = useRef<number[]>([]);
  if (phasesRef.current.length !== count) {
    phasesRef.current = Array.from({ length: count }, () => Math.random() * Math.PI * 2);
  }
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    let raf = 0;
    const loop = () => {
      setTick((t) => t + 1);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [active]);

  const bars = phasesRef.current.map((phase, i) => {
    const t = tick * 0.08 + phase;
    const shimmer = active ? 0.5 + 0.5 * Math.abs(Math.sin(t + i * 0.4)) : 0;
    // Bell curve: center bars taller
    const mid = (count - 1) / 2;
    const bell = 1 - Math.abs(i - mid) / mid * 0.55;
    const h = active
      ? Math.min(1, volume * 2.2 * shimmer * bell + 0.06)
      : 0.06;
    return h;
  });

  return (
    <div
      className={`flex items-end gap-[2px] sm:gap-[3px] h-8 sm:h-10 ${align === "right" ? "flex-row-reverse" : ""}`}
    >
      {bars.map((h, i) => (
        <div
          key={i}
          className="w-[3px] rounded-full transition-[height] duration-75"
          style={{
            height: `${Math.max(h * 100, 6)}%`,
            background: active
              ? `linear-gradient(to top, ${color}, ${color}cc)`
              : "var(--surface-3)",
            boxShadow: active ? `0 0 6px ${color}55` : "none",
          }}
        />
      ))}
    </div>
  );
}

function MicOrb({
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
  void micVolume;
  void isSpeaking;

  return (
    <button
      onClick={onClick}
      aria-label={isActive ? "Stop listening" : "Start listening"}
      aria-pressed={isActive}
      className={`shrink-0 w-16 h-16 rounded-full flex items-center justify-center transition-transform focus-ring hover:scale-[1.04] active:scale-95 ${
        isActive ? "bg-red-600 hover:bg-red-500" : "bg-green-600 hover:bg-green-500"
      }`}
    >
      {isActive ? (
        <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-white">
          <rect x="6" y="6" width="12" height="12" rx="2.5" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="currentColor" className="w-7 h-7 text-white">
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
      )}
    </button>
  );
}

function ChannelColumn({
  label,
  active,
  volume,
  bytes,
  align,
  gradient,
  color,
  icon,
  barCount,
}: {
  label: string;
  active: boolean;
  volume: number;
  bytes: number;
  align: "left" | "right";
  gradient: string;
  color: string;
  icon: React.ReactNode;
  barCount: number;
}) {
  const pct = active ? Math.max(Math.round(volume * 100), 0) : 0;
  const isRight = align === "right";

  return (
    <div
      className={`flex-1 min-w-0 flex flex-col gap-2 sm:gap-2.5 ${
        isRight ? "items-end text-right" : "items-start text-left"
      }`}
    >
      {/* Label + icon + % */}
      <div
        className={`flex items-center gap-1.5 sm:gap-2.5 ${isRight ? "flex-row-reverse" : ""}`}
      >
        <div
          className={`w-6 h-6 sm:w-7 sm:h-7 rounded-[var(--r-sm)] flex items-center justify-center shrink-0 transition-all`}
          style={{
            background: active ? gradient : "var(--surface-2)",
            boxShadow: active ? `0 0 14px ${color}55` : "none",
          }}
        >
          <span className={`${active ? "text-white" : "text-[var(--text-3)]"}`}>
            {icon}
          </span>
        </div>
        <span className="t-label text-[var(--text-2)] hidden sm:inline">{label}</span>
        <span
          className="t-mono text-[15px] sm:text-[17px] font-semibold tabular-nums sm:ml-1"
          style={{ color: active ? color : "var(--text-4)" }}
        >
          {pct}%
        </span>
      </div>

      {/* Frequency bars visualizer */}
      <FreqBars volume={volume} active={active} color={color} align={align} count={barCount} />

      {/* Thick gradient volume bar */}
      <div className="w-full max-w-[240px] h-2 sm:h-2.5 bg-[var(--surface-2)] rounded-full overflow-hidden relative">
        <div
          className={`h-full rounded-full transition-all duration-75 ${isRight ? "ml-auto" : ""}`}
          style={{
            width: `${Math.max(pct, active ? 3 : 0)}%`,
            background: gradient,
            boxShadow: active ? `0 0 12px ${color}99` : "none",
          }}
        />
        {/* Peak markers */}
        <div className="absolute inset-0 flex justify-between px-1 pointer-events-none">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="w-px h-full bg-[var(--canvas)] opacity-40"
              style={{ marginLeft: i === 0 ? "25%" : 0 }}
            />
          ))}
        </div>
      </div>

      {/* Bytes — hidden on small screens */}
      <div
        className={`hidden sm:flex items-center gap-1.5 t-mono text-[13px] text-[var(--text-4)] tabular-nums ${
          isRight ? "flex-row-reverse" : ""
        }`}
      >
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5 opacity-60">
          <path d="M2 3h12v2H2V3zm0 4h12v2H2V7zm0 4h8v2H2v-2z" />
        </svg>
        <span>{formatBytes(bytes)}</span>
      </div>
    </div>
  );
}

const micIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M10 12a2.5 2.5 0 002.5-2.5v-5a2.5 2.5 0 00-5 0v5A2.5 2.5 0 0010 12z" />
    <path d="M14 9.5a4 4 0 11-8 0H4.5a5.5 5.5 0 005 5.48V17h1V14.98a5.5 5.5 0 005-5.48H14z" />
  </svg>
);
const speakerIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M7 5L3 8H1v4h2l4 3V5zm3.5 1.5a1 1 0 011.42 0 5 5 0 010 7.07 1 1 0 01-1.42-1.41 3 3 0 000-4.24 1 1 0 010-1.42zm2.83-2.83a1 1 0 011.41 0 9 9 0 010 12.73 1 1 0 01-1.41-1.41 7 7 0 000-9.9 1 1 0 010-1.42z" />
  </svg>
);

export function AudioConsole({
  phase,
  micVolume,
  isSpeaking,
  speakerVolume,
  audioOut,
  audioIn,
  onStartVoice,
  onStopVoice,
}: AudioConsoleProps) {
  const isVoiceActive = phase === "voice_active";

  return (
    <div className="border-y border-[var(--border-subtle)] bg-gradient-to-b from-[var(--surface-1)]/80 to-[var(--canvas)]/40 shrink-0 relative overflow-hidden">
      {/* Ambient corner glows */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[200px] pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at center top, rgba(99,102,241,0.15) 0%, transparent 70%)",
        }}
      />
      <div className="relative max-w-5xl mx-auto px-3 sm:px-8 py-3.5 sm:py-5 flex items-center justify-between gap-3 sm:gap-8">
        <ChannelColumn
          label="Mic Input"
          active={isVoiceActive}
          volume={micVolume}
          bytes={audioOut}
          align="right"
          gradient="var(--grad-success)"
          color="var(--success)"
          icon={micIcon}
          barCount={10}
        />

        <MicOrb
          isActive={isVoiceActive}
          isSpeaking={isSpeaking}
          micVolume={micVolume}
          onClick={isVoiceActive ? onStopVoice : onStartVoice}
        />

        <ChannelColumn
          label="Speaker"
          active={isSpeaking}
          volume={speakerVolume}
          bytes={audioIn}
          align="left"
          gradient="var(--grad-cool)"
          color="var(--accent-2)"
          icon={speakerIcon}
          barCount={10}
        />
      </div>
    </div>
  );
}
