"use client";

import { useEffect, useRef } from "react";
import type { ConversationEvent } from "@/lib/use-voice-session";

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  return JSON.stringify(value, null, 2);
}

function KeyValueBlock({
  heading,
  entries,
  headingColor,
}: {
  heading: string;
  entries: [string, unknown][];
  headingColor: string;
}) {
  if (entries.length === 0) return null;
  return (
    <div className="space-y-1">
      <div
        className="t-micro"
        style={{ color: headingColor }}
      >
        {heading}
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 t-mono">
        {entries.map(([key, value]) => (
          <div key={key} className="contents">
            <span className="text-[var(--text-3)]">{key}</span>
            <span className="text-[var(--text-1)] break-all whitespace-pre-wrap">
              {formatValue(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
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
    <div
      className="rounded-[var(--r-md)] bg-[var(--surface-1)] border border-[var(--border-subtle)] overflow-hidden shadow-[var(--elev-1)]"
    >
      {/* Gradient header strip */}
      <div
        className="px-3 py-2 flex items-center gap-2 relative"
        style={{
          background:
            "linear-gradient(90deg, rgba(99,102,241,0.18) 0%, rgba(168,85,247,0.12) 60%, transparent 100%)",
        }}
      >
        <div
          className="w-6 h-6 rounded-[var(--r-sm)] flex items-center justify-center shrink-0"
          style={{ background: "var(--grad-primary)" }}
        >
          <svg
            viewBox="0 0 16 16"
            fill="currentColor"
            className="w-3.5 h-3.5 text-white"
          >
            <path d="M6.646 5.646a.5.5 0 11.708.708L5.707 8l1.647 1.646a.5.5 0 01-.708.708l-2-2a.5.5 0 010-.708l2-2zm2.708 0a.5.5 0 10-.708.708L10.293 8l-1.647 1.646a.5.5 0 00.708.708l2-2a.5.5 0 000-.708l-2-2z" />
          </svg>
        </div>
        <span className="t-mono text-[13px] font-semibold text-[var(--text-1)]">
          {name}
        </span>
        <span className="t-mono text-[13px] text-[var(--text-4)]">()</span>
        <span className="ml-auto t-micro text-[var(--accent-hover)]">FN</span>
      </div>
      <div className="px-3 py-2.5 space-y-2.5">
        <KeyValueBlock
          heading="args"
          entries={argEntries}
          headingColor="var(--accent-hover)"
        />
        {resultEntries.length > 0 && (
          <>
            <div className="h-px bg-[var(--border-subtle)]" />
            <KeyValueBlock
              heading="result"
              entries={resultEntries}
              headingColor="var(--success)"
            />
          </>
        )}
      </div>
    </div>
  );
}

function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end gap-2 sm:gap-3">
      <div className="max-w-[85%] space-y-1">
        <div className="t-micro text-[var(--text-3)] text-right">You</div>
        <div
          className="px-3.5 sm:px-4 py-2 sm:py-2.5 rounded-[var(--r-lg)] rounded-tr-sm t-body text-white relative overflow-hidden shadow-[var(--elev-1)]"
          style={{
            background:
              "linear-gradient(135deg, rgba(99,102,241,0.9) 0%, rgba(168,85,247,0.9) 100%)",
          }}
        >
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "radial-gradient(circle at 20% 0%, rgba(255,255,255,0.12) 0%, transparent 50%)",
            }}
          />
          <span className="relative">{text}</span>
        </div>
      </div>
      <div
        className="w-7 h-7 sm:w-8 sm:h-8 shrink-0 rounded-full flex items-center justify-center text-white text-[12px] sm:text-[13px] font-semibold"
        style={{
          background: "var(--grad-cool)",
          boxShadow: "0 0 12px rgba(34,211,238,0.3)",
        }}
      >
        U
      </div>
    </div>
  );
}

function AssistantMessage({ text }: { text: string }) {
  return (
    <div className="flex gap-2 sm:gap-3">
      <div
        className="w-7 h-7 sm:w-8 sm:h-8 shrink-0 rounded-full flex items-center justify-center relative"
        style={{
          background: "var(--grad-primary)",
          boxShadow: "var(--glow-accent)",
        }}
      >
        <div
          className="absolute inset-[2px] rounded-full pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 30% 20%, rgba(255,255,255,0.35) 0%, transparent 55%)",
          }}
        />
        <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-white relative z-10">
          <path d="M10 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4zm-6 14a6 6 0 1112 0H4z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="t-micro text-grad-primary">Assistant</div>
        <div className="t-body-lg text-[var(--text-1)]">{text}</div>
      </div>
    </div>
  );
}

function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 px-3 py-2 rounded-[var(--r-md)] bg-[var(--live-soft)] border border-[color:var(--live)]/30">
      <svg
        viewBox="0 0 20 20"
        fill="currentColor"
        className="w-4 h-4 text-[var(--live)] shrink-0 mt-0.5"
      >
        <path
          fillRule="evenodd"
          d="M10 2a8 8 0 100 16 8 8 0 000-16zm0 4a1 1 0 011 1v4a1 1 0 11-2 0V7a1 1 0 011-1zm0 8a1 1 0 100 2 1 1 0 000-2z"
          clipRule="evenodd"
        />
      </svg>
      <div className="t-body text-[var(--text-1)]">{message}</div>
    </div>
  );
}

function EmptyState() {
  const prompts = [
    "Read my unread emails",
    "Summarize this message",
    "Draft a reply saying thanks",
  ];
  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="text-center max-w-md space-y-6">
        <div className="mx-auto w-14 h-14 rounded-full bg-[var(--accent-soft)] border border-[color:var(--accent)]/20 flex items-center justify-center">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            className="w-7 h-7 text-[var(--accent-hover)]"
          >
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path
              strokeLinecap="round"
              d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5M12 16v5"
            />
          </svg>
        </div>
        <div className="space-y-1.5">
          <div className="t-title text-[var(--text-1)]">
            Ready when you are
          </div>
          <div className="t-body text-[var(--text-3)]">
            Press the mic and try one of these:
          </div>
        </div>
        <div className="flex flex-col gap-1.5 items-center">
          {prompts.map((p) => (
            <div
              key={p}
              className="px-3 py-1.5 rounded-[var(--r-full)] bg-[var(--surface-2)] border border-[var(--border-subtle)] t-body text-[var(--text-2)]"
            >
              &ldquo;{p}&rdquo;
            </div>
          ))}
        </div>
      </div>
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
    return <EmptyState />;
  }

  return (
    <div className="flex-1 overflow-y-auto scroll-thin">
      <div className="max-w-3xl mx-auto px-3 sm:px-4 py-4 sm:py-5 space-y-3 sm:space-y-4">
        {events.map((event, i) => {
          if (event.type === "user_transcription") {
            return <UserMessage key={i} text={event.text} />;
          }
          if (event.type === "assistant") {
            return <AssistantMessage key={i} text={event.text} />;
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
            return <ErrorMessage key={i} message={event.message} />;
          }
          return null;
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
