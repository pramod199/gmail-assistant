"use client";

import { useEffect, useRef } from "react";
import type { ConversationEvent } from "@/lib/use-voice-session";

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  return JSON.stringify(value, null, 2);
}

function FunctionCard({
  name,
  args,
  result,
}: {
  name: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
}) {
  const argEntries = Object.entries(args).filter(
    ([, v]) => v !== null && v !== undefined && v !== ""
  );
  const resultEntries = result
    ? Object.entries(result).filter(
        ([, v]) => v !== null && v !== undefined && v !== ""
      )
    : [];

  return (
    <div className="px-4 py-3 bg-blue-950/30 border border-blue-900/30 rounded-lg font-mono space-y-2">
      <div className="flex items-center gap-2">
        <svg
          viewBox="0 0 16 16"
          fill="currentColor"
          className="w-4 h-4 text-blue-400 shrink-0"
        >
          <path d="M6.646 5.646a.5.5 0 11.708.708L5.707 8l1.647 1.646a.5.5 0 01-.708.708l-2-2a.5.5 0 010-.708l2-2zm2.708 0a.5.5 0 10-.708.708L10.293 8l-1.647 1.646a.5.5 0 00.708.708l2-2a.5.5 0 000-.708l-2-2z" />
        </svg>
        <span className="text-base font-medium text-blue-300">{name}()</span>
      </div>

      {argEntries.length > 0 && (
        <div className="pl-6 border-l-2 border-blue-800/30 space-y-0.5">
          {argEntries.map(([key, value]) => (
            <div key={key} className="text-sm text-gray-400">
              <span className="text-blue-400/70">{key}</span>
              <span className="text-gray-600"> = </span>
              <span className="text-gray-200">{formatValue(value)}</span>
            </div>
          ))}
        </div>
      )}

      {resultEntries.length > 0 && (
        <div className="pl-6 border-l-2 border-green-800/30 space-y-0.5">
          {resultEntries.map(([key, value]) => (
            <div key={key} className="text-sm text-gray-400">
              <span className="text-green-400/70">{key}</span>
              <span className="text-gray-600"> = </span>
              <span className="text-gray-200 break-all whitespace-pre-wrap">
                {formatValue(value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ConversationPanel({
  events,
}: {
  events: ConversationEvent[];
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center space-y-3">
          <div className="text-gray-500 text-lg">
            Conversation will appear here
          </div>
          <div className="text-gray-600 text-base space-y-1">
            <div className="text-gray-400">
              &quot;Read my unread emails&quot;
            </div>
            <div className="text-gray-400">
              &quot;Summarize this message&quot;
            </div>
            <div className="text-gray-400">
              &quot;Draft a reply saying thanks&quot;
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {events.map((event, i) => {
        if (event.type === "user_transcription") {
          return (
            <div key={i} className="text-base text-gray-400 italic leading-relaxed pl-4 border-l-2 border-gray-700">
              {event.text}
            </div>
          );
        }

        if (event.type === "assistant") {
          return (
            <div key={i} className="text-base text-gray-200 leading-relaxed">
              {event.text}
            </div>
          );
        }

        if (event.type === "function") {
          return (
            <FunctionCard
              key={i}
              name={event.name}
              args={event.args}
              result={event.result}
            />
          );
        }

        if (event.type === "error") {
          return (
            <div
              key={i}
              className="px-4 py-2 bg-red-950/30 border border-red-800/30 rounded-lg text-sm text-red-300"
            >
              {event.message}
            </div>
          );
        }

        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
