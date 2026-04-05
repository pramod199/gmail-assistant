"use client";

import { useEffect, useRef } from "react";

interface SubtitleOverlayProps {
  subtitle: string;
  userSubtitle: string;
  accent?: boolean;
}

export function SubtitleOverlay({
  subtitle,
  userSubtitle,
  accent = false,
}: SubtitleOverlayProps) {
  const assistantRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (assistantRef.current) {
      assistantRef.current.scrollTop = assistantRef.current.scrollHeight;
    }
  }, [subtitle]);

  useEffect(() => {
    if (userRef.current) {
      userRef.current.scrollTop = userRef.current.scrollHeight;
    }
  }, [userSubtitle]);

  const hasAssistant = subtitle.trim().length > 0;
  const hasUser = userSubtitle.trim().length > 0;

  if (!hasAssistant && !hasUser) return null;

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-4 z-20 flex flex-col items-center gap-2 px-4">
      {hasUser && (
        <div
          ref={userRef}
          className="max-w-2xl w-full max-h-20 overflow-y-auto rounded-[var(--r-md)] bg-black/70 backdrop-blur-md px-4 py-2 text-center t-body italic text-[var(--text-2)] shadow-[var(--elev-2)] ring-1 ring-white/5"
          style={{ scrollbarWidth: "none" }}
        >
          {userSubtitle}
        </div>
      )}
      {hasAssistant && (
        <div
          ref={assistantRef}
          className={`max-w-2xl w-full max-h-32 overflow-y-auto rounded-[var(--r-md)] bg-black/80 backdrop-blur-md px-5 py-3 text-center t-body-lg text-white shadow-[var(--elev-2)] ring-1 leading-snug ${
            accent ? "ring-[color:var(--accent)]/40" : "ring-white/10"
          }`}
          style={{ scrollbarWidth: "none" }}
        >
          {subtitle}
        </div>
      )}
    </div>
  );
}
