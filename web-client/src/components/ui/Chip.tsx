"use client";

import type { ReactNode, ButtonHTMLAttributes } from "react";

type Tone = "neutral" | "accent" | "success" | "warn" | "live" | "cyan" | "purple";

interface ChipProps {
  icon?: ReactNode;
  label?: string;
  value?: ReactNode;
  tone?: Tone;
  dot?: boolean;
  dotPulse?: boolean;
  onClick?: ButtonHTMLAttributes<HTMLButtonElement>["onClick"];
  title?: string;
  className?: string;
  truncate?: boolean;
}

const toneStyles: Record<
  Tone,
  { bg: string; border: string; dot: string; icon: string; value: string }
> = {
  neutral: {
    bg: "bg-[var(--surface-2)]",
    border: "border-[var(--border-subtle)]",
    dot: "bg-[var(--text-4)]",
    icon: "text-[var(--text-3)]",
    value: "text-[var(--text-1)]",
  },
  accent: {
    bg: "bg-[var(--accent-soft)]",
    border: "border-[color:var(--accent)]/30",
    dot: "bg-[var(--accent)]",
    icon: "text-[var(--accent-hover)]",
    value: "text-[var(--text-1)]",
  },
  success: {
    bg: "bg-[var(--success-soft)]",
    border: "border-[color:var(--success)]/30",
    dot: "bg-[var(--success)]",
    icon: "text-[var(--success)]",
    value: "text-[var(--text-1)]",
  },
  warn: {
    bg: "bg-[var(--warn-soft)]",
    border: "border-[color:var(--warn)]/30",
    dot: "bg-[var(--warn)]",
    icon: "text-[var(--warn)]",
    value: "text-[var(--text-1)]",
  },
  live: {
    bg: "bg-[var(--live-soft)]",
    border: "border-[color:var(--live)]/30",
    dot: "bg-[var(--live)]",
    icon: "text-[var(--live)]",
    value: "text-[var(--text-1)]",
  },
  cyan: {
    bg: "bg-[rgba(34,211,238,0.12)]",
    border: "border-[color:var(--accent-2)]/30",
    dot: "bg-[var(--accent-2)]",
    icon: "text-[var(--accent-2)]",
    value: "text-[var(--text-1)]",
  },
  purple: {
    bg: "bg-[rgba(168,85,247,0.12)]",
    border: "border-[color:var(--accent-3)]/30",
    dot: "bg-[var(--accent-3)]",
    icon: "text-[var(--accent-3)]",
    value: "text-[var(--text-1)]",
  },
};

export function Chip({
  icon,
  label,
  value,
  tone = "neutral",
  dot,
  dotPulse,
  onClick,
  title,
  className = "",
  truncate = false,
}: ChipProps) {
  const t = toneStyles[tone];
  const interactive = Boolean(onClick);
  const content = (
    <span
      className={`inline-flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 h-8 rounded-[var(--r-full)] border ${t.bg} ${t.border} text-[13px] sm:text-[14px] leading-none shrink-0 ${interactive ? "transition-colors hover:bg-[var(--surface-3)] cursor-pointer focus-ring" : ""} ${className}`}
      title={title}
    >
      {dot && (
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${t.dot} ${dotPulse ? "animate-pulse" : ""}`}
        />
      )}
      {icon && <span className={`shrink-0 ${t.icon}`}>{icon}</span>}
      {label && (
        <span className="text-[var(--text-3)] t-micro shrink-0">{label}</span>
      )}
      {value !== undefined && (
        <span
          className={`font-medium ${t.value} ${truncate ? "truncate max-w-[200px]" : ""}`}
        >
          {value}
        </span>
      )}
    </span>
  );

  if (interactive) {
    return (
      <button type="button" onClick={onClick} className="focus:outline-none">
        {content}
      </button>
    );
  }
  return content;
}
