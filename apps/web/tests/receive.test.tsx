import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { ReceivePanel } from "../src/features/receive/ReceivePanel";
import type { ReceiveApi } from "../src/services/api";
import type { Transfer } from "../src/services/schemas";

function download(id: string, status: Transfer["status"], name = `${id}.pdf`): Transfer {
  return {
    id,
    direction: "download",
    filename: name,
    safe_filename: name,
    size: 2048,
    chunk_size: 1024,
    total_chunks: 2,
    status,
    received_bytes: 0,
    sha256: null,
    error_code: null,
    fully_served: false,
  };
}

function fakeReceive(initial: Transfer[]) {
  let state = initial;
  const update = (id: string, status: Transfer["status"]) => {
    state = state.map((t) => (t.id === id ? { ...t, status } : t));
    return Promise.resolve(state.find((t) => t.id === id) ?? download(id, status));
  };
  return {
    list: vi.fn((_token: string) => Promise.resolve(state)),
    ticket: vi.fn((_t: string, id: string) =>
      Promise.resolve({
        url: `/api/v1/transfers/${id}/download?ticket=T-${id}`,
        expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
      }),
    ),
    confirm: vi.fn((_t: string, id: string) => update(id, "completed")),
    cancel: vi.fn((_t: string, id: string) => update(id, "cancelled")),
  } satisfies ReceiveApi;
}

const UPLOAD: Transfer = { ...download("up", "completed"), direction: "upload" };

beforeEach(() => {
  // jsdom ne sait pas naviguer : on neutralise le téléchargement réel.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

it("affiche l'état vide", async () => {
  render(<ReceivePanel token="tok" api={fakeReceive([UPLOAD])} pollMs={60_000} />);
  expect(await screen.findByText(/Aucun fichier proposé/)).toBeInTheDocument();
});

it("FR-029 : lien direct avec ticket, puis confirmation de réception (§6.3)", async () => {
  const api = fakeReceive([download("a", "waiting", "Rapport été.pdf"), UPLOAD]);
  render(<ReceivePanel token="tok" api={api} pollMs={60_000} />);

  const list = await screen.findByRole("list", { name: "Fichiers proposés par le PC" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(1); // les envois du téléphone sont exclus
  expect(within(list).getByText("2 Ko")).toBeInTheDocument();

  const link = await within(list).findByRole("link", { name: "Télécharger" });
  expect(link).toHaveAttribute("href", "/api/v1/transfers/a/download?ticket=T-a");
  expect(link).toHaveAttribute("download", "Rapport été.pdf");
  expect(within(list).queryByRole("button", { name: "J'ai reçu le fichier" })).toBeNull();

  fireEvent.click(link);
  fireEvent.click(await within(list).findByRole("button", { name: "J'ai reçu le fichier" }));

  await waitFor(() => expect(within(list).getByText("Reçu ✓")).toBeInTheDocument());
  expect(api.confirm).toHaveBeenCalledWith("tok", "a");
});

it("propose la confirmation si le téléchargement a commencé avant un rechargement", async () => {
  render(
    <ReceivePanel token="tok" api={fakeReceive([download("b", "transferring")])} pollMs={60_000} />,
  );
  expect(await screen.findByRole("button", { name: "J'ai reçu le fichier" })).toBeInTheDocument();
});

it("FR-025 : ignorer un fichier le retire de la liste", async () => {
  const api = fakeReceive([download("c", "waiting")]);
  render(<ReceivePanel token="tok" api={api} pollMs={60_000} />);
  fireEvent.click(await screen.findByRole("button", { name: "Ignorer" }));
  await waitFor(() => expect(screen.getByText(/Aucun fichier proposé/)).toBeInTheDocument());
  expect(api.cancel).toHaveBeenCalledWith("tok", "c");
});

it("FR-043 : signale un PC injoignable puis se rétablit", async () => {
  const api = fakeReceive([download("d", "waiting")]);
  api.list.mockRejectedValueOnce(new Error("réseau"));
  render(<ReceivePanel token="tok" api={api} pollMs={10} />);
  expect(await screen.findByText(/PC injoignable/)).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByText(/PC injoignable/)).toBeNull());
  expect(await screen.findByRole("link", { name: "Télécharger" })).toBeInTheDocument();
});
