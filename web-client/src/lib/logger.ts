export type LogLevel = "info" | "warn" | "error";

export interface LogEntry {
  timestamp: Date;
  level: LogLevel;
  message: string;
}

type Listener = () => void;

class Logger {
  private entries: LogEntry[] = [];
  private listeners = new Set<Listener>();
  private snapshot: LogEntry[] = [];

  log(level: LogLevel, message: string) {
    this.entries.push({ timestamp: new Date(), level, message });
    if (this.entries.length > 500) this.entries.shift();
    this.snapshot = [...this.entries];
    this.listeners.forEach((l) => l());
  }

  info(message: string) {
    this.log("info", message);
  }
  warn(message: string) {
    this.log("warn", message);
  }
  error(message: string) {
    this.log("error", message);
  }

  subscribe = (callback: Listener) => {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  };

  getSnapshot = (): LogEntry[] => {
    return this.snapshot;
  };

  private static EMPTY: LogEntry[] = [];
  getServerSnapshot = (): LogEntry[] => {
    return Logger.EMPTY;
  };

  clear() {
    this.entries = [];
    this.snapshot = [];
    this.listeners.forEach((l) => l());
  }
}

export const logger = new Logger();
