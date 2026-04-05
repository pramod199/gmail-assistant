"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  Phase,
  SessionState,
  ConversationEvent,
} from "@/lib/use-voice-session";
import type { LogEntry } from "@/lib/logger";
import {
  getVoicePersona,
  getInstructionPresets,
  type VoicePersonaResponse,
  type InstructionPresetInfo,
} from "@/lib/session-api";
import { StatusPill } from "./StatusPill";
import { LogPanel } from "./LogPanel";
import { ConversationPanel } from "./ConversationPanel";
import { SettingsPanel } from "./SettingsPanel";
import { SubtitleOverlay } from "./SubtitleOverlay";
import { AudioConsole } from "./AudioConsole";
import { ConfigChipRow } from "./ConfigChipRow";
import { Button } from "./ui/Button";

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
  subtitle: string;
  userSubtitle: string;
  logs: LogEntry[];
  onConnect: () => void;
  onDisconnect: () => void;
  onStartVoice: () => void;
  onStopVoice: () => void;
  onClearLogs: () => void;
  token: string;
}

function BrandMark() {
  return (
    <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
      <div
        className="relative w-8 h-8 sm:w-9 sm:h-9 rounded-[var(--r-md)] flex items-center justify-center shrink-0 shadow-[var(--elev-1)]"
        style={{
          background: "var(--grad-primary)",
          boxShadow: "var(--glow-accent)",
        }}
      >
        <div
          className="absolute inset-[2px] rounded-[8px] pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 30% 20%, rgba(255,255,255,0.4) 0%, transparent 55%)",
          }}
        />
        <svg
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-4 h-4 sm:w-5 sm:h-5 text-white relative z-10"
        >
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
      </div>
      <div className="flex flex-col leading-tight min-w-0">
        <span className="text-[15px] sm:text-[17px] font-semibold tracking-tight text-grad-primary truncate">
          Gmail Assistant
        </span>
        <span className="t-micro text-[var(--text-4)] hidden sm:inline">Voice</span>
      </div>
    </div>
  );
}

const settingsIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path
      fillRule="evenodd"
      d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
      clipRule="evenodd"
    />
  </svg>
);

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
  subtitle,
  userSubtitle,
  logs,
  onConnect,
  onDisconnect,
  onStartVoice,
  onStopVoice,
  onClearLogs,
  token,
}: VoiceInterfaceProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [persona, setPersona] = useState<VoicePersonaResponse | null>(null);
  const [presets, setPresets] = useState<InstructionPresetInfo[]>([]);

  const isConnected = phase === "connected" || phase === "voice_active";
  const isSetup = phase === "authenticated" || phase === "connecting";

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    getVoicePersona(token)
      .then((p) => !cancelled && setPersona(p))
      .catch(() => {});
    getInstructionPresets()
      .then((pr) => !cancelled && setPresets(pr))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token]);

  const presetLabel = useMemo(() => {
    if (!persona?.custom_instructions) return null;
    const match = presets.find(
      (p) => p.instructions === persona.custom_instructions
    );
    return match?.label ?? "Custom";
  }, [persona, presets]);

  return (
    <div className="flex flex-col h-screen app-bg text-[var(--text-1)]">
      {/* Header */}
      <header className="relative flex items-center gap-2 sm:gap-3 px-3 sm:px-5 h-14 sm:h-16 border-b border-[var(--border-subtle)] bg-[var(--surface-1)]/50 backdrop-blur-sm shrink-0">
        {/* Gradient accent line at bottom */}
        <div
          className="absolute inset-x-0 bottom-0 h-px pointer-events-none"
          style={{ background: "var(--grad-header-underline)" }}
        />
        <BrandMark />
        <div className="flex-1 min-w-0 flex justify-center sm:justify-end">
          <StatusPill
            phase={phase}
            sessionState={sessionState}
            isSpeaking={isSpeaking}
          />
        </div>
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          {isConnected && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSettingsOpen(true)}
              aria-label="Settings"
              className="h-9 w-9 sm:h-10 sm:w-10"
            >
              {settingsIcon}
            </Button>
          )}
          {isConnected && (
            <>
              <Button
                variant="secondary"
                size="icon"
                onClick={onDisconnect}
                aria-label="Disconnect"
                className="sm:hidden h-9 w-9"
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path d="M10 2a1 1 0 011 1v7a1 1 0 11-2 0V3a1 1 0 011-1z" />
                  <path d="M5.05 5.05a1 1 0 010 1.414 5 5 0 107.071 0 1 1 0 111.414-1.414 7 7 0 11-9.9 0 1 1 0 011.415 0z" />
                </svg>
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={onDisconnect}
                className="hidden sm:inline-flex"
              >
                Disconnect
              </Button>
            </>
          )}
        </div>
      </header>

      {/* Gmail Auth Banner */}
      {gmailAuthUrl && (
        <div className="mx-3 sm:mx-4 mt-3 px-3 py-2.5 rounded-[var(--r-md)] bg-[var(--warn-soft)] border border-[color:var(--warn)]/30 flex items-center gap-2.5 shrink-0">
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-4 h-4 text-[var(--warn)] shrink-0"
          >
            <path
              fillRule="evenodd"
              d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM10 13a1 1 0 110 2 1 1 0 010-2zm-1-4a1 1 0 112 0v2a1 1 0 11-2 0V9z"
              clipRule="evenodd"
            />
          </svg>
          <span className="t-body text-[var(--text-1)] flex-1">
            Gmail authorization required.
          </span>
          <a
            href={gmailAuthUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="t-body font-medium text-[var(--warn)] hover:underline focus-ring rounded"
          >
            Authorize →
          </a>
        </div>
      )}

      {/* Setup screen vs active session */}
      {isSetup ? (
        <div className="flex-1 overflow-y-auto scroll-thin">
          <div className="max-w-5xl mx-auto p-4 sm:p-6 lg:p-8">
            <div className="text-center space-y-2.5 sm:space-y-3 mb-6 sm:mb-8">
              <div
                className="inline-flex items-center gap-2 px-3 py-1 rounded-[var(--r-full)] border border-[color:var(--accent)]/30 bg-[var(--accent-soft)] t-micro text-[var(--accent-hover)]"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
                Ready to connect
              </div>
              <h2 className="text-[26px] sm:text-[32px] lg:text-[38px] leading-tight font-semibold tracking-tight text-grad-primary px-2">
                Configure your voice assistant
              </h2>
              <p className="t-body sm:t-body-lg text-[var(--text-3)] px-2">
                Pick a persona and voice, then connect to start talking.
              </p>
            </div>

            <div className="grid lg:grid-cols-[1fr_360px] gap-4 sm:gap-5 items-start">
              {token && (
                <SettingsPanel token={token} onSaved={setPersona} />
              )}

              {/* Preview card */}
              <aside
                className="relative p-5 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-[var(--r-lg)] shadow-[var(--elev-1)] space-y-4 overflow-hidden"
              >
                <div
                  className="absolute inset-x-0 top-0 h-px pointer-events-none"
                  style={{ background: "var(--grad-primary)" }}
                />
                <div
                  className="absolute -top-20 -right-20 w-40 h-40 rounded-full pointer-events-none"
                  style={{
                    background:
                      "radial-gradient(circle, rgba(168,85,247,0.15) 0%, transparent 70%)",
                  }}
                />
                <h3 className="t-label text-grad-primary relative">Preview</h3>
                {persona ? (
                  <>
                    <div className="space-y-1">
                      <div className="t-micro text-[var(--text-3)]">
                        Persona
                      </div>
                      <div className="t-body-lg text-[var(--text-1)]">
                        {persona.persona_name}
                      </div>
                      {persona.persona_description && (
                        <div className="t-body text-[var(--text-3)]">
                          {persona.persona_description}
                        </div>
                      )}
                    </div>
                    <div className="h-px bg-[var(--border-subtle)]" />
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <div className="t-micro text-[var(--text-3)] mb-1">
                          Voice
                        </div>
                        <div className="t-body text-[var(--text-1)]">
                          {persona.voice_name}
                        </div>
                      </div>
                      <div>
                        <div className="t-micro text-[var(--text-3)] mb-1">
                          Transcript
                        </div>
                        <div className="t-body text-[var(--text-1)]">
                          {persona.enable_transcription ? "On" : "Off"}
                        </div>
                      </div>
                    </div>
                    {presetLabel && (
                      <div>
                        <div className="t-micro text-[var(--text-3)] mb-1">
                          Preset
                        </div>
                        <div className="t-body text-[var(--text-1)]">
                          {presetLabel}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="t-body text-[var(--text-3)]">Loading…</div>
                )}
              </aside>
            </div>

            <div className="flex justify-center pt-6 sm:pt-8">
              <button
                onClick={onConnect}
                disabled={phase === "connecting"}
                className="relative h-12 sm:h-14 w-full sm:w-auto sm:min-w-[240px] px-8 rounded-[var(--r-md)] font-semibold text-[16px] sm:text-[17px] text-white focus-ring transition-transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100 btn-grad shadow-[var(--glow-accent)] overflow-hidden"
              >
                <div
                  className="absolute inset-0 pointer-events-none"
                  style={{
                    background:
                      "radial-gradient(circle at 30% 0%, rgba(255,255,255,0.22) 0%, transparent 50%)",
                  }}
                />
                <span className="relative flex items-center justify-center gap-2">
                  {phase === "connecting" ? (
                    <>
                      <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 animate-spin">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeDasharray="50 50" opacity="0.3" />
                        <path d="M12 2a10 10 0 0110 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                      </svg>
                      Connecting…
                    </>
                  ) : (
                    <>
                      Connect
                      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                        <path fillRule="evenodd" d="M10.3 5.3a1 1 0 011.4 0l4 4a1 1 0 010 1.4l-4 4a1 1 0 01-1.4-1.4L12.58 11H4a1 1 0 110-2h8.58L10.3 6.7a1 1 0 010-1.4z" clipRule="evenodd" />
                      </svg>
                    </>
                  )}
                </span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {persona && <ConfigChipRow persona={persona} presetLabel={presetLabel} onEdit={() => setSettingsOpen(true)} />}

          <AudioConsole
            phase={phase}
            micVolume={micVolume}
            isSpeaking={isSpeaking}
            speakerVolume={speakerVolume}
            audioOut={audioOut}
            audioIn={audioIn}
            onStartVoice={onStartVoice}
            onStopVoice={onStopVoice}
          />

          {/* Main content */}
          <div className="flex-1 flex flex-col lg:flex-row min-h-0">
            <div className="relative flex-1 flex flex-col min-h-0 lg:min-w-0">
              <ConversationPanel events={conversation} />
              <SubtitleOverlay
                subtitle={subtitle}
                userSubtitle={userSubtitle}
                accent={isSpeaking}
              />
            </div>

            {/* Logs sidebar — desktop only */}
            <div className="hidden lg:flex lg:w-[360px] lg:border-l border-[var(--border-subtle)] flex-col shrink-0">
              <LogPanel logs={logs} onClear={onClearLogs} />
            </div>
          </div>
        </>
      )}

      {/* Settings modal (mid-session) — bottom-sheet on mobile, centered on desktop */}
      {settingsOpen && token && (
        <div
          className="fixed inset-0 z-30 flex items-end sm:items-center justify-center sm:p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setSettingsOpen(false)}
        >
          <div
            className="w-full sm:max-w-md max-h-[88vh] sm:max-h-[90vh] overflow-y-auto scroll-thin"
            onClick={(e) => e.stopPropagation()}
          >
            <SettingsPanel
              token={token}
              onClose={() => setSettingsOpen(false)}
              onSaved={setPersona}
            />
          </div>
        </div>
      )}
    </div>
  );
}
