import type { Platform } from "../../services/schemas";

export interface JoinParams {
  sessionId: string;
  secret: string;
}

/** Extrait les paramètres d'appairage du fragment `#/join?s=…&k=…`. */
export function parseJoinFragment(hash: string): JoinParams | null {
  const match = /^#\/join\?(.*)$/.exec(hash);
  if (!match) return null;
  const params = new URLSearchParams(match[1]);
  const sessionId = params.get("s");
  const secret = params.get("k");
  if (!sessionId || !secret) return null;
  return { sessionId, secret };
}

/**
 * Lit puis efface le fragment d'appairage : le secret ne reste ni dans la barre
 * d'adresse ni dans l'historique (ADR-006). À appeler une seule fois, avant le rendu.
 */
export function consumeJoinFragment(win: Window = window): JoinParams | null {
  const params = parseJoinFragment(win.location.hash);
  if (params) {
    win.history.replaceState(null, "", win.location.pathname + win.location.search);
  }
  return params;
}

export function detectPlatform(userAgent: string, maxTouchPoints = 0): Platform {
  if (/iPhone|iPad|iPod/i.test(userAgent)) return "ios";
  // iPadOS se présente comme un Mac : on le distingue par l'écran tactile.
  if (/Macintosh/i.test(userAgent) && maxTouchPoints > 1) return "ios";
  if (/Android/i.test(userAgent)) return "android";
  if (/Windows/i.test(userAgent)) return "windows";
  return "other";
}

export function defaultDeviceName(userAgent: string, maxTouchPoints = 0): string {
  if (/iPad/i.test(userAgent) || (/Macintosh/i.test(userAgent) && maxTouchPoints > 1)) {
    return "iPad";
  }
  if (/iPhone/i.test(userAgent)) return "iPhone";
  const android = /Android [\d.]+; ([^;)]+)/i.exec(userAgent);
  if (android?.[1] && android[1].trim() !== "K") return android[1].trim();
  if (/Android/i.test(userAgent)) return "Téléphone Android";
  return "Appareil";
}
