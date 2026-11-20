import { useEffect, useState, useSyncExternalStore } from "react";

import type { JoinParams } from "../features/pairing/joinLink";
import { type PairingOptions, type PairingState, usePairing } from "../features/pairing/usePairing";
import { ReceivePanel } from "../features/receive/ReceivePanel";
import { SendPanel } from "../features/send/SendPanel";
import {
  pairingApi,
  type ReceiveApi,
  receiveApi,
  type TransferApi,
  transferApi,
} from "../services/api";
import { RealtimeClient, type RealtimeConnection } from "../services/realtime";
import { messages } from "./messages";

export interface AppProps {
  joinParams?: JoinParams | null;
  pairing?: PairingOptions;
  transfers?: TransferApi;
  receive?: ReceiveApi;
  receivePollMs?: number;
  realtime?: RealtimeConnection;
}

const defaultPairing: PairingOptions = { api: pairingApi };

type Tone = "neutral" | "success" | "warning" | "danger";

const toneClasses: Record<Tone, string> = {
  neutral: "border-border",
  success: "border-success",
  warning: "border-warning",
  danger: "border-danger",
};

function describe(state: PairingState): { title?: string; text: string; tone: Tone } {
  switch (state.kind) {
    case "idle":
      return { text: messages.notPaired, tone: "neutral" };
    case "joining":
      return { text: messages.joining, tone: "neutral" };
    case "checking":
      return { text: messages.checking, tone: "neutral" };
    case "pending":
      return {
        title: messages.pendingTitle,
        text: messages.pending(state.displayName),
        tone: "warning",
      };
    case "connected":
      return {
        title: messages.connectedTitle,
        text: messages.connected(state.serverName),
        tone: "success",
      };
    case "rejected":
      return { text: messages.rejected, tone: "danger" };
    case "ended":
      return {
        text: state.reason === "expired" ? messages.sessionExpired : messages.sessionRevoked,
        tone: "danger",
      };
    case "invalid_qr":
      return { text: messages.invalidQr, tone: "danger" };
    case "offline":
      return { text: messages.offline, tone: "warning" };
    case "error":
      return { text: messages.genericError(state.message), tone: "danger" };
  }
}

export function App({
  joinParams = null,
  pairing = defaultPairing,
  transfers = transferApi,
  receive = receiveApi,
  receivePollMs,
  realtime: injectedRealtime,
}: AppProps) {
  const [realtime] = useState<RealtimeConnection>(() => injectedRealtime ?? new RealtimeClient());
  const state = usePairing(joinParams, { ...pairing, realtime });
  const { title, text, tone } = describe(state);
  const liveStatus = useSyncExternalStore(realtime.subscribeStatus, realtime.getStatus);

  // Temps réel dès qu'un jeton existe (en attente d'approbation ou connecté).
  const token = state.kind === "pending" || state.kind === "connected" ? state.token : null;
  useEffect(() => {
    if (token) realtime.connect(token);
    else realtime.disconnect();
  }, [realtime, token]);
  useEffect(() => () => realtime.disconnect(), [realtime]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 px-4 py-8">
      <header>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold">{messages.appName}</h1>
          {token && (
            <span
              data-testid="live-status"
              data-live={liveStatus}
              className={`text-sm ${liveStatus === "open" ? "text-success" : "text-warning"}`}
            >
              {liveStatus === "open" ? messages.liveOn : messages.liveReconnecting}
            </span>
          )}
        </div>
        <p className="text-text-muted">{messages.tagline}</p>
      </header>

      <section
        aria-live="polite"
        data-testid="pairing-status"
        data-state={state.kind}
        className={`rounded-lg border bg-surface-raised p-4 ${toneClasses[tone]}`}
      >
        {title && <h2 className="mb-1 text-lg font-medium">{title}</h2>}
        <p>{text}</p>
      </section>

      {state.kind === "connected" && (
        <>
          <SendPanel token={state.token} api={transfers} />
          <ReceivePanel
            token={state.token}
            api={receive}
            realtime={realtime}
            {...(receivePollMs ? { pollMs: receivePollMs } : {})}
          />
        </>
      )}

      <p role="note" className="mt-auto text-sm text-warning">
        {messages.trustedNetworkWarning}
      </p>
    </main>
  );
}
