import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { HistoryPanel } from "../src/features/history/HistoryPanel";
import type { HistoryApi, HistoryFilters } from "../src/services/api";
import type { Transfer } from "../src/services/schemas";
import { FakeRealtime } from "./fakes";

function transfer(
  id: string,
  direction: Transfer["direction"],
  status: Transfer["status"],
  name: string,
  extra: Partial<Transfer> = {},
): Transfer {
  return {
    id,
    direction,
    filename: name,
    safe_filename: name,
    size: 2048,
    chunk_size: 1024,
    total_chunks: 2,
    status,
    received_bytes: 2048,
    sha256: null,
    error_code: null,
    fully_served: false,
    created_at: "2026-11-20T09:05:00",
    ...extra,
  };
}

/** Faux serveur : applique réellement les filtres demandés. */
function fakeHistory(initial: Transfer[]) {
  let rows = initial;
  const calls: HistoryFilters[] = [];
  const api: HistoryApi = {
    list: vi.fn((_token: string, filters: HistoryFilters) => {
      calls.push(filters);
      const matching = rows.filter(
        (t) =>
          (!filters.direction || t.direction === filters.direction) &&
          (!filters.q || t.safe_filename.toLowerCase().includes(filters.q.toLowerCase())),
      );
      return Promise.resolve({
        items: matching.slice(0, filters.limit ?? 20),
        total: matching.length,
        limit: filters.limit ?? 20,
        offset: 0,
      });
    }),
  };
  return { api, calls, set: (next: Transfer[]) => (rows = next) };
}

const ROWS = [
  transfer("t3", "download", "completed", "Plan été.pdf"),
  transfer("t2", "upload", "cancelled", "vieux.iso", { error_code: "EXPIRED" }),
  transfer("t1", "upload", "completed", "Vacances.mp4"),
];

const list = () => screen.findByRole("list", { name: "Transferts passés" });
const names = async () =>
  within(await list())
    .getAllByRole("listitem")
    .map((li) => li.querySelector("span")?.textContent);

it("FR-034 : affiche l'historique avec sens, date et statut", async () => {
  render(<HistoryPanel token="tok" api={fakeHistory(ROWS).api} />);
  expect(await names()).toEqual(["Plan été.pdf", "vieux.iso", "Vacances.mp4"]);
  const items = within(await list()).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Reçu du PC");
  expect(items[0]).toHaveTextContent("Terminé");
  expect(items[1]).toHaveTextContent("Annulé (expiré)");
  expect(items[2]).toHaveTextContent("Envoyé au PC");
  expect(items[2]).toHaveTextContent(/\d{2}\/\d{2} \d{2}:\d{2}/);
});

it("FR-034 : filtre par sens et par nom", async () => {
  const { api, calls } = fakeHistory(ROWS);
  render(<HistoryPanel token="tok" api={api} searchDelayMs={10} />);
  await list();

  await userEvent.click(screen.getByRole("tab", { name: "Envoyés" }));
  await waitFor(async () => expect(await names()).toEqual(["vieux.iso", "Vacances.mp4"]));
  expect(screen.getByRole("tab", { name: "Envoyés" })).toHaveAttribute("aria-selected", "true");

  await userEvent.type(screen.getByRole("searchbox", { name: "Rechercher un fichier" }), "vac");
  await waitFor(async () => expect(await names()).toEqual(["Vacances.mp4"]));
  expect(calls.at(-1)).toMatchObject({ direction: "upload", q: "vac" });

  await userEvent.type(screen.getByRole("searchbox"), "zzz");
  expect(await screen.findByText("Aucun transfert ne correspond à la recherche.")).toBeInTheDocument();
});

it("se met à jour en temps réel et pagine", async () => {
  const { api, set } = fakeHistory([ROWS[2] as Transfer]);
  const realtime = new FakeRealtime();
  render(<HistoryPanel token="tok" api={api} realtime={realtime} pageSize={2} />);
  expect(await names()).toEqual(["Vacances.mp4"]);

  set(ROWS);
  realtime.emit("transfer.completed", { transfer_id: "t3" });
  await waitFor(async () => expect(await names()).toEqual(["Plan été.pdf", "vieux.iso"]));

  await userEvent.click(screen.getByRole("button", { name: "Afficher plus" }));
  await waitFor(async () => expect(await names()).toHaveLength(3));
  expect(screen.queryByRole("button", { name: "Afficher plus" })).toBeNull();
});

it("FR-043 : états vide et erreur", async () => {
  const empty = fakeHistory([]);
  const { unmount } = render(<HistoryPanel token="tok" api={empty.api} />);
  expect(await screen.findByText("Aucun transfert pour le moment.")).toBeInTheDocument();
  unmount();

  const broken: HistoryApi = { list: () => Promise.reject(new Error("réseau")) };
  render(<HistoryPanel token="tok" api={broken} />);
  expect(await screen.findByText(/PC injoignable/)).toBeInTheDocument();
});
