import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "../src/app/App";
import { ErrorBoundary } from "../src/app/ErrorBoundary";
import { screenFromHash } from "../src/app/useScreen";
import type { HistoryApi, PairingApi, ReceiveApi, TransferApi } from "../src/services/api";
import { saveCredentials } from "../src/services/credentials";
import type { Transfer } from "../src/services/schemas";
import { FakeRealtime } from "./fakes";

const HOUR = 3_600_000;

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

function offer(id: string): Transfer {
  return {
    id,
    direction: "download",
    filename: `${id}.pdf`,
    safe_filename: `${id}.pdf`,
    size: 10,
    chunk_size: 4,
    total_chunks: 3,
    status: "waiting",
    received_bytes: 0,
    sha256: null,
    error_code: null,
    fully_served: false,
    created_at: "2026-11-20T10:00:00Z",
  };
}

const receive: ReceiveApi = {
  list: () => Promise.resolve([offer("a"), offer("b")]),
  ticket: (_t, id) =>
    Promise.resolve({
      url: `/api/v1/transfers/${id}/download?ticket=x`,
      expires_at: new Date(Date.now() + HOUR).toISOString(),
    }),
  confirm: () => Promise.reject(new Error("non utilisé")),
  cancel: () => Promise.reject(new Error("non utilisé")),
};

const history: HistoryApi = {
  list: () => Promise.resolve({ items: [], total: 0, limit: 20, offset: 0 }),
};

/** Serveur d'envoi dont on contrôle le rythme : chaque bloc attend un feu vert. */
function slowTransfers() {
  const releases: Array<() => void> = [];
  const api: TransferApi = {
    create: (_t, name, size) =>
      Promise.resolve({ ...offer("up"), direction: "upload", filename: name, safe_filename: name, size, chunk_size: 4, total_chunks: Math.ceil(size / 4) }),
    putChunk: (_t, _id, index, data) =>
      new Promise((resolve) =>
        releases.push(() =>
          resolve({ index, already_received: false, received_bytes: index * 4 + data.length, status: "transferring" }),
        ),
      ),
    receivedChunks: () => Promise.resolve([]),
    complete: (_t, _id) => Promise.resolve({ ...offer("up"), direction: "upload", status: "completed", received_bytes: 8, size: 8 }),
    cancel: vi.fn(() =>
      Promise.resolve({ ...offer("up"), direction: "upload" as const, status: "cancelled" as const }),
    ),
    list: () => Promise.resolve([]),
    resume: () => Promise.reject(new Error("non utilisé")),
  };
  return { api, releaseNext: () => releases.shift()?.(), pending: () => releases.length };
}

function renderApp(transfers: TransferApi = slowTransfers().api) {
  saveCredentials({ deviceId: "dev1", token: "tok" });
  return render(
    <App
      realtime={new FakeRealtime()}
      pairing={{ api: connected, connectedPollMs: HOUR }}
      transfers={transfers}
      receive={receive}
      receivePollMs={HOUR}
      history={history}
    />,
  );
}

const nav = () => screen.getByRole("navigation", { name: "Navigation principale" });

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});

it("analyse le hash de navigation", () => {
  expect(screenFromHash("")).toBe("accueil");
  expect(screenFromHash("#/")).toBe("accueil");
  expect(screenFromHash("#/envoyer")).toBe("envoyer");
  expect(screenFromHash("#/historique?x=1")).toBe("historique");
  expect(screenFromHash("#/inconnu")).toBe("accueil");
});

it("§14.3 : accueil avec nom du PC, actions et pastille de fichiers en attente", async () => {
  renderApp();
  expect(await screen.findByText("Connecté à PC-SALON")).toBeVisible();
  // Pas de doublon : la carte d'état de l'appairage s'efface une fois connecté.
  expect(screen.getByTestId("pairing-status")).not.toBeVisible();
  expect(await screen.findByText("2 fichiers vous attendent")).toBeInTheDocument();
  const receiveTab = within(nav()).getByRole("button", { name: /Recevoir/ });
  expect(within(receiveTab).getByLabelText("2 fichiers à recevoir")).toHaveTextContent("2");
  expect(within(nav()).getByRole("button", { name: "Accueil" })).toHaveAttribute("aria-current", "page");
});

it("navigue par onglets, met à jour le hash, déplace le focus et gère le bouton Retour", async () => {
  renderApp();
  await screen.findByText("Connecté à PC-SALON");

  await userEvent.click(within(nav()).getByRole("button", { name: "Historique" }));
  expect(window.location.hash).toBe("#/historique");
  expect(within(nav()).getByRole("button", { name: "Historique" })).toHaveAttribute("aria-current", "page");
  await waitFor(() => expect(document.activeElement).toHaveTextContent("Historique"));
  expect(screen.queryByText("Connecté à PC-SALON")).not.toBeVisible();

  // Bouton Retour du téléphone : le hash revient en arrière.
  act(() => {
    window.history.replaceState(null, "", "/#/recevoir");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  expect(await screen.findByRole("heading", { name: "Recevoir du PC" })).toBeVisible();
  expect(screen.getByText("a.pdf")).toBeVisible();
});

it("un envoi continue pendant qu'on change d'écran, puis s'annule (FR-025)", async () => {
  const server = slowTransfers();
  renderApp(server.api);
  await screen.findByText("Connecté à PC-SALON");
  await userEvent.click(within(nav()).getByRole("button", { name: "Envoyer" }));
  await userEvent.upload(screen.getByLabelText("Choisir des fichiers"), new File(["0123456789ab"], "film.mp4"));
  await waitFor(() => expect(server.pending()).toBe(1));

  // Changement d'écran pendant l'envoi : le bloc en cours aboutit quand même.
  await userEvent.click(within(nav()).getByRole("button", { name: "Historique" }));
  act(() => server.releaseNext());
  await waitFor(() => expect(server.pending()).toBe(1)); // le bloc suivant est parti
  const sendTab = within(nav()).getByRole("button", { name: /Envoyer/ });
  expect(within(sendTab).getByLabelText("1 envoi en cours")).toBeInTheDocument();

  await userEvent.click(sendTab);
  await userEvent.click(screen.getByRole("button", { name: "Annuler l'envoi de film.mp4" }));
  act(() => server.releaseNext()); // le bloc en vol se termine, puis l'annulation s'applique
  await waitFor(() => expect(screen.getByText("Annulé")).toBeInTheDocument());
  expect(server.api.cancel).toHaveBeenCalledWith("tok", "up"); // place libérée sur le PC
  expect(window.localStorage.getItem("localdrop.uploads")).toBe("{}");
  await waitFor(() => expect(within(sendTab).queryByLabelText(/envoi en cours/)).toBeNull());
  expect(within(nav()).getByLabelText("2 fichiers à recevoir")).toBeInTheDocument();
});

it("affiche un écran de secours au lieu d'une page blanche", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  function Broken(): never {
    throw new Error("panne");
  }
  render(
    <ErrorBoundary>
      <Broken />
    </ErrorBoundary>,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Une erreur inattendue est survenue");
  expect(screen.getByRole("button", { name: "Recharger la page" })).toBeInTheDocument();
});
