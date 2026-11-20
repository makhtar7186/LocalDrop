// Jeton d'appareil persistant (survit au rechargement de la page).
// localStorage peut être indisponible (navigation privée, stockage bloqué) : jamais bloquant.

const KEY = "localdrop.device";

export interface Credentials {
  deviceId: string;
  token: string;
}

export function loadCredentials(): Credentials | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" &&
      value !== null &&
      "deviceId" in value &&
      "token" in value &&
      typeof value.deviceId === "string" &&
      typeof value.token === "string"
    ) {
      return { deviceId: value.deviceId, token: value.token };
    }
  } catch {
    // stockage indisponible ou corrompu
  }
  return null;
}

export function saveCredentials(credentials: Credentials): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(credentials));
  } catch {
    // le jeton restera en mémoire pour cette page
  }
}

export function clearCredentials(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // rien à faire
  }
}
