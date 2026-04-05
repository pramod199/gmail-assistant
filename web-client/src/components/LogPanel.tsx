"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { LogEntry, LogLevel } from "@/lib/logger";

type Filter = "all" | LogLevel;

const levelMeta: Record<
  LogLevel,
  { label: string; dot: string; text: string }
> = {
  info: {
    label: "INF",
    dot: "bg-[var(--text-3)]",
    text: "text-[var(--text-2)]",
  },
  warn: {
    label: "WRN",
    dot: "bg-[var(--warn)]",
    text: "text-[var(--warn)]",
  },
  error: {
    label: "ERR",
    dot: "bg-[var(--live)]",
    text: "text-[var(--live)]",
  },
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function LogPanel({
  logs,
  onClear,
}: {
  logs: LogEntry[];
  onClear: () => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Count per level
  const counts = useMemo(() => {
    const c = { all: logs.length, info: 0, warn: 0, error: 0 };
    for (const l of logs) c[l.level]++;
    return c;
  }, [logs]);

  const visible = useMemo(
    () => (filter === "all" ? logs : logs.filter((l) => l.level === filter)),
    [logs, filter]
  );

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visible.length, autoScroll]);

  // Pause auto-scroll when user scrolls up
  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(nearBottom);
  }

  const filterBtn = (key: Filter, label: string, count: number) => {
    const active = filter === key;
    return (
      <button
        key={key}
        onClick={() => setFilter(key)}
        className={`h-7 px-2.5 rounded-[var(--r-sm)] t-micro transition-colors focus-ring ${
          active
            ? "bg-[var(--surface-3)] text-[var(--text-1)]"
            : "text-[var(--text-3)] hover:text-[var(--text-2)] hover:bg-[var(--surface-2)]"
        }`}
      >
        {label}
        <span className="ml-1 text-[var(--text-4)] tabular-nums">{count}</span>
      </button>
    );
  };

  return (
    <div className="flex flex-col h-full bg-[var(--surface-1)]">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-[var(--border-subtle)] shrink-0">
        <span className="t-label text-[var(--text-2)] mr-2">Logs</span>
        {filterBtn("all", "All", counts.all)}
        {filterBtn("info", "Info", counts.info)}
        {filterBtn("warn", "Warn", counts.warn)}
        {filterBtn("error", "Err", counts.error)}
        <button
          onClick={onClear}
          className="ml-auto h-7 px-2.5 t-micro text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] rounded-[var(--r-sm)] transition-colors focus-ring"
        >
          Clear
        </button>
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="flex-1 overflow-y-auto scroll-thin relative"
      >
        {visible.length === 0 ? (
          <div className="px-3 py-4 t-body text-[var(--text-4)] text-center">
            {logs.length === 0 ? "No logs yet" : "No matching logs"}
          </div>
        ) : (
          <div className="px-3 py-1.5">
            {visible.map((entry, i) => {
              const m = levelMeta[entry.level];
              return (
                <div
                  key={i}
                  className={`flex gap-2 py-1 t-mono text-[13px] ${
                    i % 2 === 1 ? "bg-[var(--surface-2)]/20" : ""
                  }`}
                >
                  <span className="text-[var(--text-4)] shrink-0 tabular-nums">
                    {formatTime(entry.timestamp)}
                  </span>
                  <span
                    className={`shrink-0 inline-flex items-center gap-1 ${m.text}`}
                  >
                    <span className={`w-1 h-1 rounded-full ${m.dot}`} />
                    {m.label}
                  </span>
                  <span className="break-all text-[var(--text-2)]">
                    {entry.message}
                  </span>
                </div>
              );
            })}
            <div ref={bottomRef} />
          </div>
        )}
        {!autoScroll && (
          <button
            onClick={() => {
              setAutoScroll(true);
              bottomRef.current?.scrollIntoView({ behavior: "smooth" });
            }}
            className="absolute bottom-3 right-3 h-7 px-2.5 t-micro bg-[var(--surface-3)] hover:bg-[var(--accent)] text-[var(--text-1)] rounded-[var(--r-full)] border border-[var(--border-strong)] shadow-[var(--elev-2)] transition-colors focus-ring"
          >
            ↓ Jump to latest
          </button>
        )}
      </div>
    </div>
  );
}
