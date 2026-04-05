"use client";

import type { VoicePersonaResponse } from "@/lib/session-api";
import { Chip } from "./ui/Chip";

interface ConfigChipRowProps {
  persona: VoicePersonaResponse;
  presetLabel?: string | null;
  onEdit?: () => void;
}

const personaIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M10 8a3 3 0 100-6 3 3 0 000 6zM5 18a5 5 0 1110 0H5z" />
  </svg>
);

const voiceIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M10 3a1 1 0 011 1v12a1 1 0 11-2 0V4a1 1 0 011-1zm-4 3a1 1 0 011 1v6a1 1 0 11-2 0V7a1 1 0 011-1zm8 0a1 1 0 011 1v6a1 1 0 11-2 0V7a1 1 0 011-1zM3 8a1 1 0 011 1v2a1 1 0 11-2 0V9a1 1 0 011-1zm14 0a1 1 0 011 1v2a1 1 0 11-2 0V9a1 1 0 011-1z" />
  </svg>
);

const presetIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 5a1 1 0 011-1h8a1 1 0 110 2H4a1 1 0 01-1-1z" />
  </svg>
);

const transcriptionIcon = (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M2 4a2 2 0 012-2h12a2 2 0 012 2v8a2 2 0 01-2 2H7l-4 4V4z" />
  </svg>
);

export function ConfigChipRow({
  persona,
  presetLabel,
  onEdit,
}: ConfigChipRowProps) {
  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--surface-1)]/40 shrink-0">
      <div className="max-w-5xl mx-auto px-3 sm:px-4 py-2 sm:py-2.5 flex items-center gap-2 overflow-x-auto scroll-thin">
        <Chip
          tone="accent"
          icon={personaIcon}
          label="Persona"
          value={persona.persona_name}
          title={persona.persona_description}
          onClick={onEdit}
        />
        <Chip
          tone="cyan"
          icon={voiceIcon}
          label="Voice"
          value={persona.voice_name}
        />
        {presetLabel && (
          <Chip
            tone="purple"
            icon={presetIcon}
            label="Preset"
            value={presetLabel}
            truncate
            title={persona.custom_instructions ?? undefined}
          />
        )}
        <Chip
          tone={persona.enable_transcription ? "success" : "neutral"}
          icon={transcriptionIcon}
          label="Transcript"
          value={persona.enable_transcription ? "On" : "Off"}
          dot
        />
      </div>
    </div>
  );
}
