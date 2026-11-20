import { z } from "zod";

// Client WebSocket /ws (§8.5, §10.4).
// - Authentification par premier message : le jeton n'apparaît jamais dans l'URL.
// - Reconnexion avec backoff ; après chaque (re)connexion, l'événement « ready » invite
//   les écrans à relire l'état par REST : le WebSocket n'est pas la source de vérité.
// - 4401/4403 (révoqué, refusé) : pas de reconnexion, « unauthorized » est émis.

export const realtimeEventSchema = z.object({
  id: z.string(),
  type: z.string(),
  ts: z.string(),
  data: z.record(z.string(), z.unknown()),
});
export type RealtimeEvent = z.infer<typeof realtimeEventSchema>;

export type RealtimeStatus = "idle" | "connecting" | "open" | "reconnecting";

export interface RealtimeListener {
  onEvent?: (event: RealtimeEvent) => void;
  /** Connexion (ré)établie et authentifiée : resynchroniser par REST. */
  onReady?: () => void;
  onUnauthorized?: () => void;
}

export interface RealtimeConnection {
  connect(token: string): void;
  disconnect(): void;
  subscribe(listener: RealtimeListener): () => void;
  subscribeStatus(listener: () => void): () => void;
  getStatus(): RealtimeStatus;
}

interface SocketLike {
  readonly readyState: number;
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  send(data: string): void;
  close(code?: number): void;
}

export interface RealtimeOptions {
  url?: () => string;
  createSocket?: (url: string) => SocketLike;
  backoffMs?: readonly number[];
  pingIntervalMs?: number;
}

const DEFAULT_BACKOFF = [1000, 2000, 5000, 10000, 15000] as const;
const FINAL_CLOSE_CODES = new Set([4401, 4403]);

function defaultUrl(): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}/ws`;
}

export class RealtimeClient implements RealtimeConnection {
  private token: string | null = null;
  private socket: SocketLike | null = null;
  private status: RealtimeStatus = "idle";
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  private pingTimer: ReturnType<typeof setInterval> | undefined;
  private readonly listeners = new Set<RealtimeListener>();
  private readonly statusListeners = new Set<() => void>();
  private readonly url: () => string;
  private readonly createSocket: (url: string) => SocketLike;
  private readonly backoff: readonly number[];
  private readonly pingIntervalMs: number;

  constructor(options: RealtimeOptions = {}) {
    this.url = options.url ?? defaultUrl;
    this.createSocket = options.createSocket ?? ((url) => new WebSocket(url));
    this.backoff = options.backoffMs ?? DEFAULT_BACKOFF;
    this.pingIntervalMs = options.pingIntervalMs ?? 25_000;
  }

  connect(token: string): void {
    if (this.token === token && this.socket) return;
    this.disconnect();
    this.token = token;
    this.attempt = 0;
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", this.onVisibilityChange);
    }
    this.open();
  }

  disconnect(): void {
    this.token = null;
    clearTimeout(this.reconnectTimer);
    this.stopPing();
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", this.onVisibilityChange);
    }
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onclose = null;
      socket.close(1000);
    }
    this.setStatus("idle");
  }

  subscribe(listener: RealtimeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  readonly subscribeStatus = (listener: () => void): (() => void) => {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  };

  readonly getStatus = (): RealtimeStatus => this.status;

  // ------------------------------------------------------------------ interne
  private open(): void {
    const token = this.token;
    if (!token) return;
    this.setStatus(this.attempt === 0 ? "connecting" : "reconnecting");

    let socket: SocketLike;
    try {
      socket = this.createSocket(this.url());
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;

    socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
    socket.onmessage = (message) => this.handleMessage(message.data);
    socket.onerror = () => {
      // « close » suit toujours « error » : la reconnexion est gérée là.
    };
    socket.onclose = (event) => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.stopPing();
      if (FINAL_CLOSE_CODES.has(event.code)) {
        this.token = null;
        this.setStatus("idle");
        for (const listener of this.listeners) listener.onUnauthorized?.();
        return;
      }
      this.scheduleReconnect();
    };
  }

  private handleMessage(raw: unknown): void {
    let message: unknown;
    try {
      message = typeof raw === "string" ? JSON.parse(raw) : null;
    } catch {
      return;
    }
    if (typeof message !== "object" || message === null || !("type" in message)) return;

    if (message.type === "auth.ok") {
      this.attempt = 0;
      this.setStatus("open");
      this.startPing();
      for (const listener of this.listeners) listener.onReady?.();
      return;
    }
    if (message.type === "pong") return;

    const parsed = realtimeEventSchema.safeParse(message);
    if (!parsed.success) return;
    for (const listener of this.listeners) listener.onEvent?.(parsed.data);
  }

  private scheduleReconnect(): void {
    if (!this.token) return;
    const delay = this.backoff[Math.min(this.attempt, this.backoff.length - 1)] ?? 15_000;
    this.attempt += 1;
    this.setStatus("reconnecting");
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }

  private readonly onVisibilityChange = (): void => {
    // Au retour au premier plan (iOS suspend les pages), reconnecter sans attendre.
    if (document.visibilityState === "visible" && this.token && !this.socket) {
      clearTimeout(this.reconnectTimer);
      this.attempt = 0;
      this.open();
    }
  };

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.socket?.readyState === 1) this.socket.send(JSON.stringify({ type: "ping" }));
    }, this.pingIntervalMs);
  }

  private stopPing(): void {
    clearInterval(this.pingTimer);
  }

  private setStatus(status: RealtimeStatus): void {
    if (this.status === status) return;
    this.status = status;
    for (const listener of this.statusListeners) listener();
  }
}
