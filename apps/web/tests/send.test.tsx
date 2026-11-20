import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "../src/app/App";
import type { PairingApi, ReceiveApi, TransferApi } from "../src/services/api";
import { saveCredentials } from "../src/services/credentials";
import type { Transfer } from "../src/services/schemas";
import { FakeRealtime } from "./fakes";

const connected: PairingApi = {
  join: () => Promise.reject(new Error("non utilisé")),
  status: () =>
    Promise.resolve({
      device_id: "dev1",
      display_name: "Pixel 8",
      status: "connected",
      server_name: "PC-SALON",
      session_expires_at: "2026-11-20T23:00:00Z",
    }),
};

function transfer(id: string, size: number, status: Transfer["status"]): Transfer {
  return {
    id,
    direction: "upload",
    filename: id,
    safe_filename: id,
    size,
    chunk_size: 1024,
    total_chunks: Math.ceil(size / 1024),
    status,
    received_bytes: status === "completed" ? size : 0,
    sha256: null,
    error_code: null,
    fully_served: false,
  };
}

function fakeTransfers(): TransferApi {
  const sizes = new Map<string, number>();
  return {
    create: vi.fn((_t: string, name: string, size: number) => {
      sizes.set(name, size);
      return Promise.resolve(transfer(name, size, "waiting"));
    }),
    putChunk: vi.fn((_t: string, _id: string, index: number, data: Uint8Array) =>
      Promise.resolve({
        index,
        already_received: false,
        received_bytes: index * 1024 + data.length,
        status: "transferring" as const,
      }),
    ),
    receivedChunks: vi.fn(() => Promise.resolve([])),
    complete: vi.fn((_t: string, id: string) =>
      Promise.resolve(transfer(id, sizes.get(id) ?? 0, "completed")),
    ),
    cancel: vi.fn((_t: string, id: string) => Promise.resolve(transfer(id, 0, "cancelled"))),
    list: vi.fn(() => Promise.resolve([])),
    resume: vi.fn((_t: string, id: string) => Promise.resolve(transfer(id, 0, "transferring"))),
  };
}

const noDownloads: ReceiveApi = {
  list: () => Promise.resolve([]),
  ticket: () => Promise.reject(new Error("non utilisé")),
  confirm: () => Promise.reject(new Error("non utilisé")),
  cancel: () => Promise.reject(new Error("non utilisé")),
};

beforeEach(() => window.localStorage.clear());

it("FR-021/FR-022/FR-024 : envoie plusieurs fichiers avec progression", async () => {
  saveCredentials({ deviceId: "dev1", token: "tok" });
  const api = fakeTransfers();
  render(
    <App realtime={new FakeRealtime()}
      pairing={{ api: connected, connectedPollMs: 60_000 }}
      transfers={api}
      receive={noDownloads}
    />,
  );

  const input = await screen.findByLabelText("Choisir des fichiers");
  expect(screen.getByText("Aucun envoi pour le moment.")).toBeInTheDocument();

  await userEvent.upload(input, [
    new File(["a".repeat(3000)], "video.mp4"),
    new File(["bonjour"], "note.txt"),
  ]);

  const list = await screen.findByRole("list", { name: "Envois en cours et terminés" });
  await waitFor(() => expect(within(list).getAllByText("Reçu sur le PC ✓")).toHaveLength(2));
  expect(within(list).getByRole("progressbar", { name: "video.mp4" })).toHaveAttribute(
    "aria-valuenow",
    "100",
  );
  expect(within(list).getByText("2,9 Ko")).toBeInTheDocument();
  expect(api.putChunk).toHaveBeenCalledTimes(4); // 3 blocs + 1 bloc
});
