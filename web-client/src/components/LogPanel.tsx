"use client";

import { useEffect, useRef } from "react";
import type { LogEntry } from "@/lib/logger";

const levelColors: Record<string, string> = {
  info: "text-gray-300",
  warn: "text-yellow-400",
  error: "text-red-400",
};

const levelBadge: Record<string, string> = {
  info: "bg-gray-700",
  warn: "bg-yellow-900",
  error: "bg-red-900",
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
  } as Intl.DateTimeFormatOptions);
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
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <span className="text-sm font-medium text-gray-400">
          Logs ({logs.length})
        </span>
        <button
          onClick={onClear}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Clear
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 font-mono text-xs space-y-0.5">
        {logs.length === 0 && (
          <div className="text-gray-600 text-center py-4">No logs yet</div>
        )}
        {logs.map((entry, i) => (
          <div key={i} className={`flex gap-2 ${levelColors[entry.level]}`}>
            <span className="text-gray-500 shrink-0">
              {formatTime(entry.timestamp)}
            </span>
            <span
              className={`px-1 rounded text-[10px] uppercase shrink-0 ${levelBadge[entry.level]}`}
            >
              {entry.level}
            </span>
            <span className="break-all">{entry.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
