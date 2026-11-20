import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SendPanel } from "../src/features/send/SendPanel";
import type { TransferApi } from "../src/services/api";
import { rememberUpload } from "../src/services/pendingUploads";
import type { Transfer } from "../src/services/schemas";

const CHUNK = 4;

function interrupted(): Transfer {
  return {
    id: "t1",
    direction: "upload",
    filename: "vacances.mp4",
    safe_filename: "vacances.mp4",
    size: 10,
    chunk_size: CHUNK,
    total_chunks: 3,
    status: "paused",
    received_bytes: 4,
    sha256: null,
    error_code: null,
    fully_served: false,
    created_at: "2026-11-20T10:00:00Z",
  };
}

function fakeApi(): TransferApi {
  return {
    create: vi.fn(() => Promise.reject(new Error("pas de création lors d'une reprise"))),
    putChunk: vi.fn((_t: string, _id: string, index: number, data: Uint8Array) =>
      Promise.resolve({
        index,
        already_received: false,
        received_bytes: Math.min(10, index * CHUNK + data.length),
        status: "transferring" as const,
      }),
    ),
    receivedChunks: vi.fn(() => Promise.resolve([0])),
    complete: vi.fn(() =>
      Promise.resolve({ ...interrupted(), status: "completed" as const, received_bytes: 10 }),
    ),
    cancel: vi.fn(() => Promise.resolve({ ...interrupted(), status: "cancelled" as const })),
    list: vi.fn(() => Promise.resolve([interrupted()])),
    resume: vi.fn(() => Promise.resolve({ ...interrupted(), status: "transferring" as const })),
  };
}

beforeEach(() => {
  window.localStorage.clear();
  rememberUpload({ transferId: "t1", name: "vacances.mp4", size: 10 });
});

it("FR-026 : propose la reprise et n'envoie que la partie manquante", async () => {
  const api = fakeApi();
  render(<SendPanel token="tok" api={api} />);

  const list = await screen.findByRole("list", { name: "Envois interrompus" });
  expect(within(list).getByText(/interrompu à 40 %/)).toBeInTheDocument();

  await userEvent.upload(
    within(list).getByLabelText("Reprendre l'envoi de vacances.mp4"),
    new File(["0123456789"], "vacances.mp4"),
  );

  const uploads = await screen.findByRole("list", { name: "Envois en cours et terminés" });
  await waitFor(() => expect(within(uploads).getByText("Reçu sur le PC ✓")).toBeInTheDocument());
  expect(api.create).not.toHaveBeenCalled();
  expect(api.resume).toHaveBeenCalledWith("tok", "t1");
  expect(vi.mocked(api.putChunk).mock.calls.map((c) => c[2])).toEqual([1, 2]);
  expect(screen.queryByRole("list", { name: "Envois interrompus" })).toBeNull();
});

it("refuse un fichier différent", async () => {
  const api = fakeApi();
  render(<SendPanel token="tok" api={api} />);
  const list = await screen.findByRole("list", { name: "Envois interrompus" });

  await userEvent.upload(
    within(list).getByLabelText("Reprendre l'envoi de vacances.mp4"),
    new File(["autre"], "autre.mp4"),
  );

  expect(await within(list).findByText(/Ce n'est pas le même fichier/)).toBeInTheDocument();
  expect(api.putChunk).not.toHaveBeenCalled();
});

it("FR-025 : abandonner annule le transfert sur le PC", async () => {
  const api = fakeApi();
  render(<SendPanel token="tok" api={api} />);
  const list = await screen.findByRole("list", { name: "Envois interrompus" });
  await userEvent.click(within(list).getByRole("button", { name: "Abandonner" }));
  await waitFor(() => expect(screen.queryByRole("list", { name: "Envois interrompus" })).toBeNull());
  expect(api.cancel).toHaveBeenCalledWith("tok", "t1");
  expect(window.localStorage.getItem("localdrop.uploads")).toBe("{}");
});
