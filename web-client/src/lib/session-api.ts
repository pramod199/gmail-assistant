const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export interface SessionResponse {
  session_id: string;
  gmail_authorized: boolean;
  requires_gmail_auth: boolean;
  gmail_auth_url?: string;
}

export interface VoicePersonaConfig {
  persona_id?: string;
  voice_name?: string;
  custom_instructions?: string;
  persona_name?: string;
  language?: string;
  enable_transcription?: boolean;
}

export interface VoicePersonaResponse extends Required<Omit<VoicePersonaConfig, "custom_instructions">> {
  custom_instructions: string | null;
  persona_description: string;
  persona_style_prompt: string;
}

export interface PrebuiltPersonaInfo {
  id: string;
  name: string;
  default_voice: string;
  description: string;
}

export interface InstructionPresetInfo {
  id: string;
  label: string;
  instructions: string;
}

export async function createSession(
  token: string
): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE_URL}/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({}),
  });

  if (!res.ok && res.status !== 201) {
    const text = await res.text();
    throw new Error(`Create session failed (${res.status}): ${text}`);
  }

  return res.json();
}

export async function deleteSession(
  sessionId: string,
  token: string,
  firebaseUserId: string
): Promise<void> {
  await fetch(
    `${API_BASE_URL}/sessions/${sessionId}?firebase_user_id=${firebaseUserId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    }
  );
}

export async function getPrebuiltPersonas(): Promise<PrebuiltPersonaInfo[]> {
  const res = await fetch(`${API_BASE_URL}/config/voice-personas`);
  if (!res.ok) throw new Error(`Failed to fetch personas (${res.status})`);
  return res.json();
}

export async function getInstructionPresets(): Promise<InstructionPresetInfo[]> {
  const res = await fetch(`${API_BASE_URL}/config/instruction-presets`);
  if (!res.ok) throw new Error(`Failed to fetch presets (${res.status})`);
  return res.json();
}

export async function getVoicePersona(
  token: string
): Promise<VoicePersonaResponse> {
  const res = await fetch(`${API_BASE_URL}/config/user/voice-persona`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Failed to fetch voice persona (${res.status})`);
  return res.json();
}

export async function updateVoicePersona(
  token: string,
  config: VoicePersonaConfig
): Promise<VoicePersonaResponse> {
  const res = await fetch(`${API_BASE_URL}/config/user/voice-persona`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to update voice persona (${res.status}): ${text}`);
  }
  return res.json();
}
