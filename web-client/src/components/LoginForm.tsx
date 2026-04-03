"use client";

import { useState } from "react";

export function LoginForm({
  onLogin,
  error,
  loading,
}: {
  onLogin: (email: string, password: string) => void;
  error: string | null;
  loading: boolean;
}) {
  const [email, setEmail] = useState("test@example.com");
  const [password, setPassword] = useState("testpass123");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email && password) onLogin(email, password);
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-950">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm p-6 space-y-4 bg-gray-900 rounded-lg border border-gray-800"
      >
        <h1 className="text-xl font-semibold text-white text-center">
          Gmail Voice Assistant
        </h1>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:outline-none focus:border-blue-500"
            placeholder="you@example.com"
            required
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm focus:outline-none focus:border-blue-500"
            required
          />
        </div>
        {error && (
          <div className="text-sm text-red-400 bg-red-900/30 p-2 rounded">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded text-sm font-medium transition-colors"
        >
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </form>
    </div>
  );
}
