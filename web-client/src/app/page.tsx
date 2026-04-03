"use client";

import { useVoiceSession } from "@/lib/use-voice-session";
import { LoginForm } from "@/components/LoginForm";
import { VoiceInterface } from "@/components/VoiceInterface";

export default function Home() {
  const {
    phase,
    authError,
    gmailAuthUrl,
    sessionState,
    logs,
    login,
    connect,
    startVoice,
    stopVoice,
    disconnect,
    clearLogs,
  } = useVoiceSession();

  if (phase === "idle" || phase === "authenticating") {
    return (
      <LoginForm
        onLogin={login}
        error={authError}
        loading={phase === "authenticating"}
      />
    );
  }

  return (
    <VoiceInterface
      phase={phase}
      gmailAuthUrl={gmailAuthUrl}
      sessionState={sessionState}
      logs={logs}
      onConnect={connect}
      onDisconnect={disconnect}
      onStartVoice={startVoice}
      onStopVoice={stopVoice}
      onClearLogs={clearLogs}
    />
  );
}
