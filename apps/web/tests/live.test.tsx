import { render, screen, waitFor } from "@testing-library/react";

import { App } from "../src/app/App";
import { ApiError, type PairingApi, type ReceiveApi } from "../src/services/api";
import { loadCredentials, saveCredentials } from "../src/services/credentials";
import type { DeviceStatus, SessionStatus, Transfer } from "../src/services/schemas";
import { FakeRealtime } from "./fakes";

const HOUR = 3_600_000; // aucun rafraîchissement périodique pendant le test

function pairingApi(statuses: Array<DeviceStatus | Error>): PairingApi {
  return {
    join: () => Promise.reject(new Error("non utilisé")),
    status: vi.fn(() => {
      const next = (statuses.length > 1 ? statuses.shift() : statuses[0]) ?? "pending";
      if (next instanceof Error) return Promise.reject(next);
      const status: SessionStatus = {
        device_id: "dev1",
        display_name: "Pixel 8",
        status: next,
        server_name: "PC-SALON",
        session_expires_at: "2026-11-20T23:00:00Z",
      };
      return Promise.resolve(status);
    }),
  };
}

const offered: Transfer = {
  id: "t1",
  direction: "download",
  filename: "plan.pdf",
  safe_filename: "plan.pdf",
  size: 1024,
  chunk_size: 1024,
  total_chunks: 1,
  status: "waiting",
  received_bytes: 0,
  sha256: null,
  error_code: null,
  fully_served: false,
};

function receiveApi(lists: Transfer[][]): ReceiveApi {
  return {
    list: vi.fn(() => Promise.resolve((lists.length > 1 ? lists.shift() : lists[0]) ?? [])),
    ticket: vi.fn(() =>
      Promise.resolve({
        url: "/api/v1/transfers/t1/download?ticket=x",
        expires_at: new Date(Date.now() + HOUR).toISOString(),
      }),
    ),
    confirm: vi.fn(() => Promise.reject(new Error("non utilisé"))),
    cancel: vi.fn(() => Promise.reject(new Error("non utilisé"))),
  };
}

const status = () => screen.getByTestId("pairing-status");

beforeEach(() => {
  window.localStorage.clear();
  saveCredentials({ deviceId: "dev1", token: "tok" });
});

it("FR-011 : l'approbation arrive en temps réel, sans attendre le rafraîchissement", async () => {
  const realtime = new FakeRealtime();
  render(
    <App
      realtime={realtime}
      pairing={{ api: pairingApi(["pending", "connected"]), pendingPollMs: HOUR }}
      receive={receiveApi([[]])}
    />,
  );
  await waitFor(() => expect(status()).toHaveAttribute("data-state", "pending"));
  expect(realtime.token).toBe("tok"); // un appareil en attente écoute déjà

  realtime.emit("device.connected", { device_id: "dev1", status: "connected" });
  await waitFor(() => expect(status()).toHaveAttribute("data-state", "connected"));
  expect(screen.getByTestId("live-status")).toHaveTextContent("En direct");
});

it("FR-042 : un fichier proposé par le PC apparaît immédiatement", async () => {
  const realtime = new FakeRealtime();
  const receive = receiveApi([[], [offered]]);
  render(
    <App
      realtime={realtime}
      pairing={{ api: pairingApi(["connected"]), connectedPollMs: HOUR }}
      receive={receive}
      receivePollMs={HOUR}
    />,
  );
  expect(await screen.findByText(/Aucun fichier proposé/)).toBeInTheDocument();

  realtime.emit("transfer.created", { transfer_id: "t1", direction: "download" });
  expect(await screen.findByText("plan.pdf")).toBeInTheDocument();

  realtime.emit("transfer.progress", { transfer_id: "u1", direction: "upload" }); // non pertinent
  expect(receive.list).toHaveBeenCalledTimes(2);
});

it("FR-013 : une révocation poussée déconnecte immédiatement", async () => {
  const realtime = new FakeRealtime();
  render(
    <App
      realtime={realtime}
      pairing={{
        api: pairingApi(["connected", new ApiError(401, "DEVICE_UNAUTHORIZED", "Session terminée")]),
        connectedPollMs: HOUR,
      }}
      receive={receiveApi([[]])}
    />,
  );
  await waitFor(() => expect(status()).toHaveAttribute("data-state", "connected"));

  realtime.emit("device.revoked", { device_id: "dev1", status: "revoked" });
  await waitFor(() => expect(status()).toHaveAttribute("data-state", "ended"));
  expect(loadCredentials()).toBeNull();
  expect(realtime.token).toBeNull(); // plus de temps réel sans jeton
});

it("FR-043 : indique la reconnexion en cours", async () => {
  const realtime = new FakeRealtime();
  render(
    <App
      realtime={realtime}
      pairing={{ api: pairingApi(["connected"]), connectedPollMs: HOUR }}
      receive={receiveApi([[]])}
    />,
  );
  await waitFor(() => expect(status()).toHaveAttribute("data-state", "connected"));
  realtime.setStatus("reconnecting");
  expect(await screen.findByText("○ Reconnexion…")).toBeInTheDocument();
});
