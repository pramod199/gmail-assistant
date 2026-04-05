"use client";

import { useEffect, useState } from "react";
import {
  getPrebuiltPersonas,
  getInstructionPresets,
  getVoicePersona,
  updateVoicePersona,
  type PrebuiltPersonaInfo,
  type InstructionPresetInfo,
  type VoicePersonaResponse,
} from "@/lib/session-api";

const VALID_VOICES = [
  "Puck",
  "Charon",
  "Kore",
  "Fenrir",
  "Aoede",
  "Leda",
  "Orus",
  "Zephyr",
];

interface SettingsPanelProps {
  token: string;
  onClose?: () => void;
  onSaved?: (config: VoicePersonaResponse) => void;
}

const selectCls =
  "w-full h-11 px-3.5 pr-9 text-[15px] bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-[var(--r-md)] text-[var(--text-1)] focus-ring hover:border-[var(--border-strong)] transition-colors appearance-none cursor-pointer bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2214%22 height=%2214%22 viewBox=%220 0 20 20%22 fill=%22%237e8596%22><path d=%22M5.5 7.5L10 12l4.5-4.5H5.5z%22/></svg>')] bg-[length:14px] bg-no-repeat bg-[right_0.875rem_center]";

const labelCls = "t-label text-[var(--text-3)]";

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h3 className="t-label text-[var(--text-2)]">{title}</h3>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

export function SettingsPanel({ token, onClose, onSaved }: SettingsPanelProps) {
  const [personas, setPersonas] = useState<PrebuiltPersonaInfo[]>([]);
  const [presets, setPresets] = useState<InstructionPresetInfo[]>([]);
  const [current, setCurrent] = useState<VoicePersonaResponse | null>(null);

  const [personaId, setPersonaId] = useState("default");
  const [voiceName, setVoiceName] = useState("");
  const [presetId, setPresetId] = useState("");
  const [enableTranscription, setEnableTranscription] = useState(true);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedField, setSavedField] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [p, pr, cur] = await Promise.all([
          getPrebuiltPersonas(),
          getInstructionPresets(),
          getVoicePersona(token),
        ]);
        setPersonas(p);
        setPresets(pr);
        setCurrent(cur);

        setPersonaId(cur.persona_id);
        setVoiceName(cur.voice_name);
        setEnableTranscription(cur.enable_transcription);

        const matched = pr.find((x) => x.instructions === cur.custom_instructions);
        setPresetId(matched ? matched.id : "");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const selectedPersona = personas.find((p) => p.id === personaId);
  const selectedPreset = presets.find((p) => p.id === presetId);
  const resolvedVoice = voiceName || selectedPersona?.default_voice || "";

  async function save(
    fieldLabel: string,
    next: {
      persona_id: string;
      voice_name: string;
      custom_instructions: string;
      enable_transcription: boolean;
    }
  ) {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateVoicePersona(token, {
        persona_id: next.persona_id,
        voice_name: next.voice_name || undefined,
        custom_instructions: next.custom_instructions || undefined,
        enable_transcription: next.enable_transcription,
      });
      setCurrent(updated);
      setSavedField(fieldLabel);
      onSaved?.(updated);
      setTimeout(() => setSavedField(null), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 t-body text-[var(--text-3)]">
        Loading voice settings…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-5 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-[var(--r-lg)] shadow-[var(--elev-1)]">
      <div className="flex items-center justify-between">
        <h2 className="t-title text-[var(--text-1)]">Voice Settings</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="h-8 w-8 flex items-center justify-center text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] rounded-[var(--r-md)] transition-colors focus-ring"
            aria-label="Close"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M4.3 4.3a1 1 0 011.4 0L10 8.6l4.3-4.3a1 1 0 111.4 1.4L11.4 10l4.3 4.3a1 1 0 01-1.4 1.4L10 11.4l-4.3 4.3a1 1 0 01-1.4-1.4L8.6 10 4.3 5.7a1 1 0 010-1.4z" />
            </svg>
          </button>
        )}
      </div>

      {error && (
        <div className="px-3 py-2 t-body rounded-[var(--r-md)] bg-[var(--live-soft)] border border-[color:var(--live)]/30 text-[var(--text-1)]">
          {error}
        </div>
      )}

      <Section title="Persona & Voice">
        <div className="space-y-1.5">
          <label className={labelCls}>Persona</label>
          <select
            value={personaId}
            onChange={(e) => {
              const v = e.target.value;
              setPersonaId(v);
              setVoiceName("");
              save("Persona", {
                persona_id: v,
                voice_name: "",
                custom_instructions: selectedPreset?.instructions ?? "",
                enable_transcription: enableTranscription,
              });
            }}
            className={selectCls}
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.description.split("—")[0].trim()}
              </option>
            ))}
          </select>
          {selectedPersona && (
            <p className="t-body text-[var(--text-3)] pt-1">
              {selectedPersona.description}
            </p>
          )}
          {savedField === "Persona" && (
            <p className="t-micro text-[var(--success)]">Saved</p>
          )}
        </div>

        <div className="space-y-1.5">
          <label className={labelCls}>
            Voice
            <span className="ml-1.5 text-[var(--text-4)] normal-case tracking-normal">
              (default: {selectedPersona?.default_voice})
            </span>
          </label>
          <select
            value={voiceName}
            onChange={(e) => {
              const v = e.target.value;
              setVoiceName(v);
              save("Voice", {
                persona_id: personaId,
                voice_name: v,
                custom_instructions: selectedPreset?.instructions ?? "",
                enable_transcription: enableTranscription,
              });
            }}
            className={selectCls}
          >
            <option value="">
              Use persona default ({selectedPersona?.default_voice})
            </option>
            {VALID_VOICES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          {resolvedVoice && (
            <p className="t-micro text-[var(--text-4)]">
              Active voice: {resolvedVoice}
            </p>
          )}
          {savedField === "Voice" && (
            <p className="t-micro text-[var(--success)]">Saved</p>
          )}
        </div>
      </Section>

      <div className="h-px bg-[var(--border-subtle)]" />

      <Section title="Behavior">
        <div className="space-y-1.5">
          <label className={labelCls}>Instruction Preset</label>
          <select
            value={presetId}
            onChange={(e) => {
              const v = e.target.value;
              setPresetId(v);
              const preset = presets.find((p) => p.id === v);
              save("Preset", {
                persona_id: personaId,
                voice_name: voiceName,
                custom_instructions: preset?.instructions ?? "",
                enable_transcription: enableTranscription,
              });
            }}
            className={selectCls}
          >
            <option value="">None</option>
            {presets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          {savedField === "Preset" && (
            <p className="t-micro text-[var(--success)]">Saved</p>
          )}
        </div>

        <label className="flex items-center gap-2.5 t-body text-[var(--text-2)] cursor-pointer select-none group">
          <input
            type="checkbox"
            checked={enableTranscription}
            onChange={(e) => {
              const v = e.target.checked;
              setEnableTranscription(v);
              save("Transcription", {
                persona_id: personaId,
                voice_name: voiceName,
                custom_instructions: selectedPreset?.instructions ?? "",
                enable_transcription: v,
              });
            }}
            className="w-4 h-4 accent-[var(--accent)] focus-ring rounded"
          />
          <span className="group-hover:text-[var(--text-1)] transition-colors">
            Show voice transcriptions in conversation
          </span>
          {savedField === "Transcription" && (
            <span className="t-micro text-[var(--success)] ml-auto">Saved</span>
          )}
        </label>
      </Section>

      <div className="flex items-center justify-between pt-1 t-micro">
        <span className="text-[var(--text-4)]">
          {saving ? "Saving…" : current ? `Current: ${current.persona_name} / ${current.voice_name}` : ""}
        </span>
        <span className="text-[var(--text-4)]">
          Changes apply on next Connect
        </span>
      </div>
    </div>
  );
}
