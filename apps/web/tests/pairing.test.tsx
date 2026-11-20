import { render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";

import { App } from "../src/app/App";
import type { PairingOptions } from "../src/features/pairing/usePairing";
import { ApiError, NetworkError, type PairingApi } from "../src/services/api";
import { loadCredentials, saveCredentials } from "../src/services/credentials";
import type { DeviceStatus, SessionStatus } from "../src/services/schemas";
import { FakeRealtime } from "./fakes";

const JOIN = { sessionId: "sess", secret: "secret" };

function sessionStatus(status: DeviceStatus): SessionStatus {
  return {
    device_id: "dev1",
    display_name: "Pixel 8",
    status,
    server_name: "PC-SALON",
    session_expires_at: "2026-11-20T23:00:00Z",
  };
}

function fakeApi(statuses: Array<SessionStatus | Error>): PairingApi & { joinCalls: number } {
  const api = {
    joinCalls: 0,
    join: vi.fn(() => {
      api.joinCalls += 1;
      return Promise.resolve({ device_id: "dev1", device_token: "tok", status: "pending" as const });
    }),
    status: vi.fn(() => {
      const next = (statuses.length > 1 ? statuses.shift() : statuses[0]) ?? new Error("vide");
      return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
    }),
  };
  return api;
}

const fast = (api: PairingApi): PairingOptions => ({
  api,
  pendingPollMs: 5,
  connectedPollMs: 5,
  offlineRetryMs: 5,
});

const panel = () => screen.getByTestId("pairing-status");

beforeEach(() => window.localStorage.clear());

describe("appairage", () => {
  it("affiche l'invitation à scanner sans jeton", () => {
    render(<App realtime={new FakeRealtime()} pairing={fast(fakeApi([sessionStatus("pending")]))} />);
    expect(panel()).toHaveAttribute("data-state", "idle");
  });

  it("FR-011 : rejoint, attend l'approbation puis se connecte", async () => {
    const api = fakeApi([sessionStatus("pending"), sessionStatus("connected")]);
    render(
      <StrictMode>
        <App realtime={new FakeRealtime()} joinParams={JOIN} pairing={fast(api)} />
      </StrictMode>,
    );

    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "pending"));
    expect(screen.getByText(/Acceptez « Pixel 8 » sur le PC/)).toBeInTheDocument();

    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "connected"));
    expect(screen.getByText(/connecté à PC-SALON/)).toBeInTheDocument();

    // Secret à usage unique : un seul join malgré le double effet de StrictMode.
    expect(api.joinCalls).toBe(1);
    expect(loadCredentials()).toEqual({ deviceId: "dev1", token: "tok" });
  });

  it("reprend une session existante au rechargement de la page", async () => {
    saveCredentials({ deviceId: "dev1", token: "tok" });
    render(<App realtime={new FakeRealtime()} pairing={fast(fakeApi([sessionStatus("connected")]))} />);
    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "connected"));
  });

  it("FR-013 : une révocation efface le jeton et demande un nouveau scan", async () => {
    saveCredentials({ deviceId: "dev1", token: "tok" });
    const api = fakeApi([
      sessionStatus("connected"),
      new ApiError(401, "DEVICE_UNAUTHORIZED", "Session terminée"),
    ]);
    render(<App realtime={new FakeRealtime()} pairing={fast(api)} />);
    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "ended"));
    expect(screen.getByText(/Session terminée/)).toBeInTheDocument();
    expect(loadCredentials()).toBeNull();
  });

  it("FR-011 : un refus est affiché et le jeton oublié", async () => {
    saveCredentials({ deviceId: "dev1", token: "tok" });
    const api = fakeApi([new ApiError(403, "DEVICE_REJECTED", "Appareil refusé")]);
    render(<App realtime={new FakeRealtime()} pairing={fast(api)} />);
    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "rejected"));
    expect(loadCredentials()).toBeNull();
  });

  it("FR-014 : un QR Code déjà utilisé est signalé", async () => {
    const api = fakeApi([sessionStatus("pending")]);
    api.join = vi.fn(() =>
      Promise.reject(new ApiError(401, "PAIRING_SECRET_INVALID", "QR Code invalide")),
    );
    render(<App realtime={new FakeRealtime()} joinParams={JOIN} pairing={fast(api)} />);
    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "invalid_qr"));
  });

  it("FR-043 : hors connexion puis retour du réseau", async () => {
    saveCredentials({ deviceId: "dev1", token: "tok" });
    const api = fakeApi([new NetworkError(), sessionStatus("connected")]);
    render(<App realtime={new FakeRealtime()} pairing={fast(api)} />);
    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "offline"));
    await waitFor(() => expect(panel()).toHaveAttribute("data-state", "connected"));
    expect(loadCredentials()).not.toBeNull();
  });
});
