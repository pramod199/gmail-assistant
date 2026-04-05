"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white shadow-[var(--elev-1)] disabled:bg-[var(--surface-3)] disabled:text-[var(--text-4)] disabled:shadow-none",
  secondary:
    "bg-[var(--surface-2)] hover:bg-[var(--surface-3)] text-[var(--text-1)] border border-[var(--border-subtle)] disabled:text-[var(--text-4)]",
  ghost:
    "bg-transparent hover:bg-[var(--surface-2)] text-[var(--text-2)] hover:text-[var(--text-1)] disabled:text-[var(--text-4)] disabled:hover:bg-transparent",
  danger:
    "bg-[var(--live)] hover:bg-red-500 text-white shadow-[var(--elev-1)]",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-9 px-3.5 text-[14px] rounded-[var(--r-sm)] gap-1.5",
  md: "h-11 px-4 text-[15px] rounded-[var(--r-md)] gap-2",
  lg: "h-12 px-6 text-[17px] rounded-[var(--r-md)] gap-2",
  icon: "h-10 w-10 rounded-[var(--r-md)] shrink-0",
};

export function Button({
  variant = "primary",
  size = "md",
  leftIcon,
  rightIcon,
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center font-medium transition-colors focus-ring disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
    >
      {leftIcon && <span className="shrink-0 opacity-90">{leftIcon}</span>}
      {children}
      {rightIcon && <span className="shrink-0 opacity-90">{rightIcon}</span>}
    </button>
  );
}
