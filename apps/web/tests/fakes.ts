import type {
  RealtimeConnection,
  RealtimeEvent,
  RealtimeListener,
  RealtimeStatus,
} from "../src/services/realtime";

/** Client temps réel piloté par le test (aucun socket réel). */
export class FakeRealtime implements RealtimeConnection {
  token: string | null = null;
  private status: RealtimeStatus = "idle";
  private readonly listeners = new Set<RealtimeListener>();
  private readonly statusListeners = new Set<() => void>();

  connect(token: string): void {
    this.token = token;
    this.setStatus("open");
  }

  disconnect(): void {
    this.token = null;
    this.setStatus("idle");
  }

  subscribe(listener: RealtimeListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  readonly subscribeStatus = (listener: () => void) => {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  };

  readonly getStatus = () => this.status;

  emit(type: string, data: Record<string, unknown> = {}): void {
    const event: RealtimeEvent = { id: crypto.randomUUID(), type, ts: new Date().toISOString(), data };
    for (const listener of this.listeners) listener.onEvent?.(event);
  }

  ready(): void {
    for (const listener of this.listeners) listener.onReady?.();
  }

  setStatus(status: RealtimeStatus): void {
    this.status = status;
    for (const listener of this.statusListeners) listener();
  }
}
