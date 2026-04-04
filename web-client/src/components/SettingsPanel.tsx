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

export function SettingsPanel({ token, onClose, onSaved }: SettingsPanelProps) {
  const [personas, setPersonas] = useState<PrebuiltPersonaInfo[]>([]);
  const [presets, setPresets] = useState<InstructionPresetInfo[]>([]);
  const [current, setCurrent] = useState<VoicePersonaResponse | null>(null);

  const [personaId, setPersonaId] = useState("default");
  const [voiceName, setVoiceName] = useState("");
  const [presetId, setPresetId] = useState("");
  const [language, setLanguage] = useState("English");
  const [enableTranscription, setEnableTranscription] = useState(true);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

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
        setLanguage(cur.language);
        setEnableTranscription(cur.enable_transcription);

        // Detect if the stored custom_instructions matches a preset
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
  const resolvedVoice = voiceName || selectedPersona?.default_voice || "";

  async function save(next: {
    persona_id: string;
    voice_name: string;
    custom_instructions: string;
    language: string;
    enable_transcription: boolean;
  }) {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateVoicePersona(token, {
        persona_id: next.persona_id,
        voice_name: next.voice_name || undefined,
        custom_instructions: next.custom_instructions || undefined,
        language: next.language,
        enable_transcription: next.enable_transcription,
      });
      setCurrent(updated);
      setSaved(true);
      onSaved?.(updated);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 text-sm text-gray-400">Loading voice settings…</div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-5 bg-gray-900/60 border border-gray-800 rounded-xl">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-100">Voice Settings</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            Close
          </button>
        )}
      </div>

      {error && (
        <div className="px-3 py-2 text-xs rounded bg-red-950/40 border border-red-800/40 text-red-300">
          {error}
        </div>
      )}

      {/* Persona */}
      <div className="space-y-1.5">
        <label className="text-xs uppercase tracking-wider text-gray-500">
          Persona
        </label>
        <select
          value={personaId}
          onChange={(e) => {
            const v = e.target.value;
            setPersonaId(v);
            setVoiceName(""); // reset voice override when persona changes
            save({
              persona_id: v,
              voice_name: "",
              custom_instructions: presetId,
              language,
              enable_transcription: enableTranscription,
            });
          }}
          className="w-full px-3 py-2 text-sm bg-gray-950 border border-gray-800 rounded text-gray-100 focus:outline-none focus:border-blue-600"
        >
          {personas.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} — {p.description.split("—")[0].trim()}
            </option>
          ))}
        </select>
        {selectedPersona && (
          <p className="text-xs text-gray-500 pt-1">{selectedPersona.description}</p>
        )}
      </div>

      {/* Voice */}
      <div className="space-y-1.5">
        <label className="text-xs uppercase tracking-wider text-gray-500">
          Voice{" "}
          <span className="normal-case text-gray-600">
            (default: {selectedPersona?.default_voice})
          </span>
        </label>
        <select
          value={voiceName}
          onChange={(e) => {
            const v = e.target.value;
            setVoiceName(v);
            save({
              persona_id: personaId,
              voice_name: v,
              custom_instructions: presetId,
              language,
              enable_transcription: enableTranscription,
            });
          }}
          className="w-full px-3 py-2 text-sm bg-gray-950 border border-gray-800 rounded text-gray-100 focus:outline-none focus:border-blue-600"
        >
          <option value="">Use persona default ({selectedPersona?.default_voice})</option>
          {VALID_VOICES.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
        {resolvedVoice && (
          <p className="text-xs text-gray-600">Active voice: {resolvedVoice}</p>
        )}
      </div>

      {/* Instruction Preset */}
      <div className="space-y-1.5">
        <label className="text-xs uppercase tracking-wider text-gray-500">
          Instruction Preset
        </label>
        <select
          value={presetId}
          onChange={(e) => {
            const v = e.target.value;
            setPresetId(v);
            save({
              persona_id: personaId,
              voice_name: voiceName,
              custom_instructions: v,
              language,
              enable_transcription: enableTranscription,
            });
          }}
          className="w-full px-3 py-2 text-sm bg-gray-950 border border-gray-800 rounded text-gray-100 focus:outline-none focus:border-blue-600"
        >
          <option value="">None</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      {/* Language */}
      <div className="space-y-1.5">
        <label className="text-xs uppercase tracking-wider text-gray-500">Language</label>
        <input
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          onBlur={() =>
            save({
              persona_id: personaId,
              voice_name: voiceName,
              custom_instructions: presetId,
              language,
              enable_transcription: enableTranscription,
            })
          }
          maxLength={50}
          placeholder="English"
          className="w-full px-3 py-2 text-sm bg-gray-950 border border-gray-800 rounded text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-600"
        />
      </div>

      {/* Transcription toggle */}
      <label className="flex items-center gap-2 text-sm text-gray-300">
        <input
          type="checkbox"
          checked={enableTranscription}
          onChange={(e) => {
            const v = e.target.checked;
            setEnableTranscription(v);
            save({
              persona_id: personaId,
              voice_name: voiceName,
              custom_instructions: presetId,
              language,
              enable_transcription: v,
            });
          }}
          className="w-4 h-4 accent-blue-600"
        />
        Show voice transcriptions in conversation
      </label>

      {/* Status */}
      <div className="flex items-center gap-3 pt-1 text-xs">
        {saving && <span className="text-gray-500">Saving…</span>}
        {!saving && saved && <span className="text-emerald-400">Saved</span>}
        {current && (
          <span className="text-gray-600 ml-auto">
            Current: {current.persona_name} / {current.voice_name}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500">Changes apply on next Connect.</p>
    </div>
  );
}
