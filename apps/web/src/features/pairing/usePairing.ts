import { useEffect, useRef, useState } from "react";

import { useRealtimeNudge } from "../../hooks/useRealtimeNudge";
import { ApiError, NetworkError, type PairingApi } from "../../services/api";
import {
  clearCredentials,
  type Credentials,
  loadCredentials,
  saveCredentials,
} from "../../services/credentials";
import type { RealtimeConnection, RealtimeEvent } from "../../services/realtime";
import type { JoinResponse } from "../../services/schemas";
import { defaultDeviceName, detectPlatform, type JoinParams } from "./joinLink";

export type PairingState =
  | { kind: "idle" } // aucun jeton : scanner le QR Code
  | { kind: "joining" }
  | { kind: "checking" } // jeton présent, vérification en cours
  | { kind: "pending"; displayName: string; token: string }
  | { kind: "connected"; serverName: string; displayName: string; token: string }
  | { kind: "rejected" }
  | { kind: "ended"; reason: "expired" | "revoked" }
  | { kind: "invalid_qr" }
  | { kind: "offline" }
  | { kind: "error"; message: string };

export interface PairingOptions {
  api: PairingApi;
  /** Intervalle de vérification pendant l'attente d'approbation. */
  pendingPollMs?: number;
  /** Intervalle de vérification une fois connecté (détecte une révocation). */
  connectedPollMs?: number;
  /** Nouvelle tentative quand le serveur est injoignable. */
  offlineRetryMs?: number;
  /** Temps réel : approbation et révocation prises en compte immédiatement. */
  realtime?: RealtimeConnection;
}

const isDeviceEvent = (event: RealtimeEvent) => event.type.startsWith("device.");

const POLLING_KINDS = new Set<PairingState["kind"]>(["checking", "pending", "connected", "offline"]);

function stateFromError(error: unknown): PairingState {
  if (error instanceof NetworkError) return { kind: "offline" };
  if (error instanceof ApiError) {
    if (error.code === "DEVICE_REJECTED") return { kind: "rejected" };
    if (error.code === "PAIRING_SECRET_INVALID") return { kind: "invalid_qr" };
    if (error.code === "SESSION_EXPIRED" || error.code === "SESSION_INVALID") {
      return { kind: "ended", reason: "expired" };
    }
    if (error.status === 401) return { kind: "ended", reason: "revoked" };
    return { kind: "error", message: error.message };
  }
  return { kind: "error", message: "Réponse inattendue du serveur" };
}

/** Tout état final invalide le jeton stocké. */
function isTerminal(state: PairingState): boolean {
  return state.kind === "rejected" || state.kind === "ended";
}

export function usePairing(joinParams: JoinParams | null, options: PairingOptions): PairingState {
  const {
    api,
    pendingPollMs = 5000,
    connectedPollMs = 30000, // filet de sécurité : le temps réel signale les révocations
    offlineRetryMs = 3000,
    realtime,
  } = options;
  const nudge = useRealtimeNudge(realtime, isDeviceEvent);
  const lastNudge = useRef(nudge);

  const [credentials, setCredentials] = useState<Credentials | null>(() =>
    joinParams ? null : loadCredentials(),
  );
  const [state, setState] = useState<PairingState>(() => {
    if (joinParams) return { kind: "joining" };
    return loadCredentials() ? { kind: "checking" } : { kind: "idle" };
  });

  // Une seule requête join, même si React (StrictMode) exécute l'effet deux fois :
  // le secret du QR Code est à usage unique.
  const joinRequest = useRef<Promise<JoinResponse> | null>(null);

  useEffect(() => {
    if (!joinParams) return;
    let cancelled = false;
    joinRequest.current ??= api.join({
      sessionId: joinParams.sessionId,
      secret: joinParams.secret,
      displayName: defaultDeviceName(navigator.userAgent, navigator.maxTouchPoints),
      platform: detectPlatform(navigator.userAgent, navigator.maxTouchPoints),
    });
    joinRequest.current.then(
      (joined) => {
        if (cancelled) return;
        const creds = { deviceId: joined.device_id, token: joined.device_token };
        saveCredentials(creds);
        setCredentials(creds);
        setState({ kind: "checking" });
      },
      (error: unknown) => {
        if (!cancelled) setState(stateFromError(error));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [api, joinParams]);

  useEffect(() => {
    if (!credentials || !POLLING_KINDS.has(state.kind)) return;
    let cancelled = false;
    const nudged = lastNudge.current !== nudge;
    lastNudge.current = nudge;
    const delay =
      state.kind === "checking" || nudged
        ? 0
        : state.kind === "pending"
          ? pendingPollMs
          : state.kind === "offline"
            ? offlineRetryMs
            : connectedPollMs;

    const timer = window.setTimeout(() => {
      api.status(credentials.token).then(
        (status) => {
          if (cancelled) return;
          if (status.status === "connected" || status.status === "disconnected") {
            setState({
              kind: "connected",
              serverName: status.server_name,
              displayName: status.display_name,
              token: credentials.token,
            });
          } else {
            setState({
              kind: "pending",
              displayName: status.display_name,
              token: credentials.token,
            });
          }
        },
        (error: unknown) => {
          if (cancelled) return;
          const next = stateFromError(error);
          if (isTerminal(next)) {
            clearCredentials();
            setCredentials(null);
          }
          setState(next);
        },
      );
    }, delay);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [api, credentials, state, nudge, pendingPollMs, connectedPollMs, offlineRetryMs]);

  return state;
}
