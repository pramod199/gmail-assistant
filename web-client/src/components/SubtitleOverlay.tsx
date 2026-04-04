"use client";

import { useEffect, useRef } from "react";

interface SubtitleOverlayProps {
  subtitle: string;
  userSubtitle: string;
}

export function SubtitleOverlay({ subtitle, userSubtitle }: SubtitleOverlayProps) {
  const assistantRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom like movie subtitles as text streams in
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
    <div className="pointer-events-none absolute inset-x-0 bottom-28 z-20 flex flex-col items-center gap-2 px-4">
      {hasUser && (
        <div
          ref={userRef}
          className="max-w-3xl w-full max-h-20 overflow-y-auto rounded-lg bg-black/60 backdrop-blur-sm px-4 py-2 text-center text-sm italic text-gray-300 shadow-lg ring-1 ring-white/5"
        >
          {userSubtitle}
        </div>
      )}
      {hasAssistant && (
        <div
          ref={assistantRef}
          className="max-w-3xl w-full max-h-32 overflow-y-auto rounded-lg bg-black/75 backdrop-blur-sm px-5 py-3 text-center text-lg font-medium text-white shadow-xl ring-1 ring-white/10 leading-snug"
          style={{ scrollbarWidth: "none" }}
        >
          {subtitle}
        </div>
      )}
    </div>
  );
}
