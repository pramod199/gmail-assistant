"use client";

import { useEffect, useRef } from "react";
import type { LogEntry } from "@/lib/logger";

const levelColors: Record<string, string> = {
  info: "text-gray-400",
  warn: "text-yellow-400",
  error: "text-red-400",
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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800/60 shrink-0">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          Logs ({logs.length})
        </span>
        <button
          onClick={onClear}
          className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
        >
          Clear
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-1.5 font-mono text-sm leading-snug">
        {logs.length === 0 && (
          <div className="text-gray-700 text-center py-3 text-sm">
            No logs yet
          </div>
        )}
        {logs.map((entry, i) => (
          <div
            key={i}
            className={`flex gap-1.5 py-px ${levelColors[entry.level]}`}
          >
            <span className="text-gray-600 shrink-0">
              {formatTime(entry.timestamp)}
            </span>
            <span className="break-all">{entry.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
