import { type RealtimeEvent, RealtimeClient } from "../src/services/realtime";

class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 0;
  sent: unknown[] = [];
  closedWith: number | undefined;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(JSON.parse(data));
  }

  close(code?: number) {
    this.closedWith = code;
  }

  // --- pilotage par le test
  serverOpen() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  serverSend(message: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(message) }));
  }

  serverClose(code: number) {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close", { code }));
  }
}

const latest = () => {
  const socket = FakeSocket.instances.at(-1);
  if (!socket) throw new Error("aucun socket");
  return socket;
};

function makeClient() {
  return new RealtimeClient({
    url: () => "ws://pc.local:8765/ws",
    createSocket: (url) => new FakeSocket(url),
    backoffMs: [100, 200, 400],
    pingIntervalMs: 1000,
  });
}

const EVENT = {
  id: "e1",
  type: "transfer.created",
  ts: "2026-11-20T10:00:00Z",
  data: { transfer_id: "t1", direction: "download" },
};

beforeEach(() => {
  FakeSocket.instances = [];
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

it("s'authentifie par premier message, jamais dans l'URL", () => {
  const client = makeClient();
  client.connect("jeton-secret");
  const socket = latest();
  expect(socket.url).toBe("ws://pc.local:8765/ws");
  expect(socket.url).not.toContain("jeton-secret");
  socket.serverOpen();
  expect(socket.sent).toEqual([{ type: "auth", token: "jeton-secret" }]);
  expect(client.getStatus()).toBe("connecting");
});

it("FR-042 : émet ready puis les événements valides uniquement", () => {
  const client = makeClient();
  const events: RealtimeEvent[] = [];
  const ready = vi.fn();
  client.subscribe({ onEvent: (e) => events.push(e), onReady: ready });
  client.connect("t");
  latest().serverOpen();
  latest().serverSend({ type: "auth.ok", data: { role: "device" } });
  expect(client.getStatus()).toBe("open");
  expect(ready).toHaveBeenCalledTimes(1);

  latest().serverSend(EVENT);
  latest().serverSend({ type: "transfer.progress" }); // invalide : ignoré
  latest().onmessage?.(new MessageEvent("message", { data: "pas du json" }));
  latest().serverSend({ type: "pong" });
  expect(events).toEqual([EVENT]);
});

it("se reconnecte avec backoff et redemande une resynchronisation", () => {
  const client = makeClient();
  const ready = vi.fn();
  client.subscribe({ onReady: ready });
  client.connect("t");
  latest().serverOpen();
  latest().serverSend({ type: "auth.ok" });

  latest().serverClose(1006); // coupure Wi-Fi
  expect(client.getStatus()).toBe("reconnecting");
  expect(FakeSocket.instances).toHaveLength(1);
  vi.advanceTimersByTime(99);
  expect(FakeSocket.instances).toHaveLength(1);
  vi.advanceTimersByTime(1);
  expect(FakeSocket.instances).toHaveLength(2);

  latest().serverClose(1006); // échec : délai suivant
  vi.advanceTimersByTime(199);
  expect(FakeSocket.instances).toHaveLength(2);
  vi.advanceTimersByTime(1);
  latest().serverOpen();
  latest().serverSend({ type: "auth.ok" });
  expect(ready).toHaveBeenCalledTimes(2); // relecture REST après reconnexion
  expect(client.getStatus()).toBe("open");
});

it.each([4401, 4403])("FR-013 : %i (révoqué/refusé) arrête les reconnexions", (code) => {
  const client = makeClient();
  const unauthorized = vi.fn();
  client.subscribe({ onUnauthorized: unauthorized });
  client.connect("t");
  latest().serverOpen();
  latest().serverClose(code);
  vi.advanceTimersByTime(10_000);
  expect(unauthorized).toHaveBeenCalledTimes(1);
  expect(FakeSocket.instances).toHaveLength(1);
  expect(client.getStatus()).toBe("idle");
});

it("envoie des pings et s'arrête proprement à la déconnexion", () => {
  const client = makeClient();
  client.connect("t");
  const socket = latest();
  socket.serverOpen();
  socket.serverSend({ type: "auth.ok" });
  vi.advanceTimersByTime(1000);
  expect(socket.sent.at(-1)).toEqual({ type: "ping" });

  client.disconnect();
  expect(socket.closedWith).toBe(1000);
  vi.advanceTimersByTime(10_000);
  expect(FakeSocket.instances).toHaveLength(1);
  expect(socket.sent.filter((m) => (m as { type: string }).type === "ping")).toHaveLength(1);
});

it("ne rouvre pas de connexion pour le même jeton", () => {
  const client = makeClient();
  client.connect("t");
  client.connect("t");
  expect(FakeSocket.instances).toHaveLength(1);
  client.connect("autre");
  expect(FakeSocket.instances).toHaveLength(2);
  expect(FakeSocket.instances[0]?.closedWith).toBe(1000);
});
