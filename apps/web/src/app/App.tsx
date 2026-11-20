import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { BottomNav } from "../components/BottomNav";
import { HistoryPanel } from "../features/history/HistoryPanel";
import { HomeScreen } from "../features/home/HomeScreen";
import type { JoinParams } from "../features/pairing/joinLink";
import { type PairingOptions, type PairingState, usePairing } from "../features/pairing/usePairing";
import { ReceivePanel } from "../features/receive/ReceivePanel";
import { SendPanel } from "../features/send/SendPanel";
import {
  type HistoryApi,
  historyApi,
  pairingApi,
  type ReceiveApi,
  receiveApi,
  type TransferApi,
  transferApi,
} from "../services/api";
import { RealtimeClient, type RealtimeConnection } from "../services/realtime";
import { messages } from "./messages";
import { type Screen, useScreen } from "./useScreen";

export interface AppProps {
  joinParams?: JoinParams | null;
  pairing?: PairingOptions;
  transfers?: TransferApi;
  receive?: ReceiveApi;
  receivePollMs?: number;
  realtime?: RealtimeConnection;
  history?: HistoryApi;
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

const SCREEN_HEADING: Record<Screen, string> = {
  accueil: "accueil-title",
  envoyer: "send-title",
  recevoir: "receive-title",
  historique: "history-title",
};

export function App({
  joinParams = null,
  pairing = defaultPairing,
  transfers = transferApi,
  receive = receiveApi,
  receivePollMs,
  realtime: injectedRealtime,
  history = historyApi,
}: AppProps) {
  const [realtime] = useState<RealtimeConnection>(() => injectedRealtime ?? new RealtimeClient());
  const state = usePairing(joinParams, { ...pairing, realtime });
  const { title, text, tone } = describe(state);
  const liveStatus = useSyncExternalStore(realtime.subscribeStatus, realtime.getStatus);
  const [screen, navigate] = useScreen();
  const [sendActivity, setSendActivity] = useState(0);
  const [receiveWaiting, setReceiveWaiting] = useState(0);

  // Temps réel dès qu'un jeton existe (en attente d'approbation ou connecté).
  const token = state.kind === "pending" || state.kind === "connected" ? state.token : null;
  useEffect(() => {
    if (token) realtime.connect(token);
    else realtime.disconnect();
  }, [realtime, token]);
  useEffect(() => () => realtime.disconnect(), [realtime]);

  // Accessibilité : à chaque changement d'écran, le focus va sur son titre (lecteurs d'écran).
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    document.getElementById(SCREEN_HEADING[screen])?.focus();
  }, [screen]);

  const connected = state.kind === "connected";
  // Carte d'état visible tant que la connexion n'est pas établie. Une fois connecté,
  // l'accueil affiche déjà « Connecté à <PC> » (doublon vu sur capture, phase 10).
  const showStatus = !connected;

  return (
    <div className={`mx-auto flex min-h-screen max-w-md flex-col ${connected ? "pb-24" : ""}`}>
      <main className="flex flex-1 flex-col gap-6 px-4 py-6">
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
          {!connected && <p className="text-text-muted">{messages.tagline}</p>}
        </header>

        <section
          aria-live="polite"
          data-testid="pairing-status"
          data-state={state.kind}
          hidden={!showStatus}
          className={`rounded-lg border bg-surface-raised p-4 ${toneClasses[tone]}`}
        >
          {title && <h2 className="mb-1 text-lg font-medium">{title}</h2>}
          <p>{text}</p>
        </section>

        {connected && (
          <>
            {/* Écrans toujours montés, simplement masqués : un envoi en cours n'est jamais
                interrompu par un changement d'écran. */}
            <div hidden={screen !== "accueil"}>
              <HomeScreen
                serverName={state.serverName}
                sendActivity={sendActivity}
                receiveWaiting={receiveWaiting}
                onNavigate={navigate}
              />
            </div>
            <div hidden={screen !== "envoyer"}>
              <SendPanel token={state.token} api={transfers} onActivity={setSendActivity} />
            </div>
            <div hidden={screen !== "recevoir"}>
              <ReceivePanel
                token={state.token}
                api={receive}
                realtime={realtime}
                onActivity={setReceiveWaiting}
                {...(receivePollMs ? { pollMs: receivePollMs } : {})}
              />
            </div>
            <div hidden={screen !== "historique"}>
              <HistoryPanel token={state.token} api={history} realtime={realtime} />
            </div>
          </>
        )}

        <p role="note" className="mt-auto text-sm text-warning">
          {messages.trustedNetworkWarning}
        </p>
      </main>

      {connected && (
        <BottomNav
          current={screen}
          onNavigate={navigate}
          badges={{ envoyer: sendActivity, recevoir: receiveWaiting }}
        />
      )}
    </div>
  );
}
