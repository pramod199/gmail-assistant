"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/Button";

export function LoginForm({
  onLogin,
  error,
  loading,
}: {
  onLogin: (email: string, password: string) => void;
  error: string | null;
  loading: boolean;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email && password) onLogin(email, password);
  };

  // Shake error on change
  useEffect(() => {
    if (error && errorRef.current) {
      errorRef.current.classList.remove("shake");
      void errorRef.current.offsetWidth;
      errorRef.current.classList.add("shake");
    }
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-screen login-bg p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm p-6 space-y-5 bg-[var(--surface-1)] rounded-[var(--r-lg)] border border-[var(--border-subtle)] shadow-[var(--elev-2)]"
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-11 h-11 rounded-[var(--r-md)] bg-[var(--accent-soft)] border border-[color:var(--accent)]/30 flex items-center justify-center">
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-6 h-6 text-[var(--accent-hover)]"
            >
              <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
              <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
            </svg>
          </div>
          <div className="space-y-1">
            <h1 className="t-title text-[var(--text-1)]">
              Gmail Voice Assistant
            </h1>
            <p className="t-body text-[var(--text-3)]">
              Sign in to start talking to your inbox
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="t-label text-[var(--text-3)]">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-11 px-3.5 bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-[var(--r-md)] text-[var(--text-1)] text-[15px] focus-ring hover:border-[var(--border-strong)] transition-colors placeholder:text-[var(--text-4)]"
              placeholder="test@example.com"
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="t-label text-[var(--text-3)]">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-11 px-3.5 bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-[var(--r-md)] text-[var(--text-1)] text-[15px] focus-ring hover:border-[var(--border-strong)] transition-colors placeholder:text-[var(--text-4)]"
              placeholder="testpass123"
              required
            />
          </div>
        </div>

        {error && (
          <div
            ref={errorRef}
            className="flex items-start gap-2 px-3 py-2 t-body rounded-[var(--r-md)] bg-[var(--live-soft)] border border-[color:var(--live)]/30 text-[var(--text-1)]"
          >
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
            <span>{error}</span>
          </div>
        )}

        <Button
          type="submit"
          disabled={loading}
          size="md"
          className="w-full"
        >
          {loading ? "Signing in…" : "Sign In"}
        </Button>
      </form>
    </div>
  );
}
