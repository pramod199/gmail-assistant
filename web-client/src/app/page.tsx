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
    conversation,
    micVolume,
    isSpeaking,
    speakerVolume,
    audioOut,
    audioIn,
    subtitle,
    userSubtitle,
    logs,
    login,
    connect,
    startVoice,
    stopVoice,
    disconnect,
    clearLogs,
    getToken,
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
      conversation={conversation}
      micVolume={micVolume}
      isSpeaking={isSpeaking}
      speakerVolume={speakerVolume}
      audioOut={audioOut}
      audioIn={audioIn}
      subtitle={subtitle}
      userSubtitle={userSubtitle}
      logs={logs}
      onConnect={connect}
      onDisconnect={disconnect}
      onStartVoice={startVoice}
      onStopVoice={stopVoice}
      onClearLogs={clearLogs}
      token={getToken()}
    />
  );
}
