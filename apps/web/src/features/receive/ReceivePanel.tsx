import { useEffect, useRef, useState } from "react";

import { formatBytes } from "../../app/format";
import { messages } from "../../app/messages";
import { useRealtimeNudge } from "../../hooks/useRealtimeNudge";
import type { ReceiveApi } from "../../services/api";
import type { RealtimeConnection, RealtimeEvent } from "../../services/realtime";
import type { Transfer } from "../../services/schemas";

// PC -> téléphone (FR-020, FR-029). Téléchargement natif du navigateur via un vrai
// lien <a> : un tap direct, compatible avec les restrictions iOS, sans assembler le
// fichier en mémoire (§9.4). La livraison n'est confirmée que par l'utilisateur (§6.3).

export interface ReceivePanelProps {
  token: string;
  api: ReceiveApi;
  /** Filet de sécurité : le temps réel déclenche une relecture immédiate. */
  pollMs?: number;
  realtime?: RealtimeConnection;
}

const isDownloadEvent = (event: RealtimeEvent) =>
  event.type.startsWith("transfer.") && event.data["direction"] === "download";

interface Link {
  url: string;
  expiresAt: number;
}

const VISIBLE = new Set<Transfer["status"]>(["waiting", "transferring", "completed"]);
const LINK_MARGIN_MS = 60_000; // renouveler un ticket une minute avant expiration

export function ReceivePanel({ token, api, pollMs = 15000, realtime }: ReceivePanelProps) {
  const nudge = useRealtimeNudge(realtime, isDownloadEvent);
  const [items, setItems] = useState<Transfer[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [links, setLinks] = useState<Record<string, Link>>({});
  const [started, setStarted] = useState<ReadonlySet<string>>(new Set());
  const [busy, setBusy] = useState<ReadonlySet<string>>(new Set());
  const [actionError, setActionError] = useState(false);
  const pendingTickets = useRef(new Set<string>());

  // Liste des fichiers proposés : relue à chaque événement temps réel pertinent (nudge)
  // et périodiquement ; REST reste la source de vérité.
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const load = () => {
      api.list(token).then(
        (all) => {
          if (cancelled) return;
          setItems(all.filter((t) => t.direction === "download" && VISIBLE.has(t.status)).reverse());
          setOffline(false);
          timer = window.setTimeout(load, pollMs);
        },
        () => {
          if (cancelled) return;
          setOffline(true);
          timer = window.setTimeout(load, pollMs);
        },
      );
    };
    load();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [api, token, pollMs, nudge]);

  // Un ticket par fichier téléchargeable, obtenu à l'avance pour un lien direct.
  useEffect(() => {
    if (!items) return;
    const now = Date.now();
    for (const transfer of items) {
      if (transfer.status === "completed") continue;
      const link = links[transfer.id];
      if (link && link.expiresAt - now > LINK_MARGIN_MS) continue;
      if (pendingTickets.current.has(transfer.id)) continue;
      pendingTickets.current.add(transfer.id);
      api
        .ticket(token, transfer.id)
        .then(
          (ticket) => {
            setLinks((prev) => ({
              ...prev,
              [transfer.id]: { url: ticket.url, expiresAt: Date.parse(ticket.expires_at) },
            }));
          },
          () => {
            // nouvel essai au prochain rafraîchissement de la liste
          },
        )
        .finally(() => pendingTickets.current.delete(transfer.id));
    }
  }, [api, token, items, links]);

  const act = (transfer: Transfer, action: "confirm" | "cancel") => {
    setBusy((prev) => new Set(prev).add(transfer.id));
    setActionError(false);
    api[action](token, transfer.id)
      .then(
        (updated) => {
          setItems(
            (prev) =>
              prev
                ?.map((t) => (t.id === updated.id ? updated : t))
                .filter((t) => VISIBLE.has(t.status)) ?? null,
          );
        },
        () => setActionError(true),
      )
      .finally(() =>
        setBusy((prev) => {
          const next = new Set(prev);
          next.delete(transfer.id);
          return next;
        }),
      );
  };

  return (
    <section className="flex flex-col gap-4" aria-labelledby="receive-title">
      <h2 id="receive-title" className="text-lg font-medium">
        {messages.receiveTitle}
      </h2>

      {offline && <p className="text-sm text-warning">{messages.receiveOffline}</p>}
      {actionError && <p className="text-sm text-danger">{messages.actionFailed}</p>}

      {items === null ? (
        <p className="text-text-muted">{messages.receiveLoading}</p>
      ) : items.length === 0 ? (
        <p className="text-text-muted">{messages.receiveEmpty}</p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label={messages.receiveListLabel}>
          {items.map((transfer) => {
            const link = links[transfer.id];
            const done = transfer.status === "completed";
            const awaitingConfirmation =
              !done && (started.has(transfer.id) || transfer.status === "transferring");
            const disabled = busy.has(transfer.id);
            return (
              <li
                key={transfer.id}
                data-status={transfer.status}
                className="rounded-lg border border-border bg-surface-raised p-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate font-medium" title={transfer.safe_filename}>
                    {transfer.safe_filename}
                  </span>
                  <span className="shrink-0 text-sm text-text-muted">
                    {formatBytes(transfer.size)}
                  </span>
                </div>

                {done ? (
                  <p className="mt-1 text-sm text-success">{messages.received}</p>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {link ? (
                      <a
                        href={link.url}
                        download={transfer.safe_filename}
                        rel="noopener"
                        onClick={() => setStarted((prev) => new Set(prev).add(transfer.id))}
                        className="flex min-h-11 items-center rounded-lg bg-accent px-4 font-medium text-white"
                      >
                        {messages.download}
                      </a>
                    ) : (
                      <span className="flex min-h-11 items-center text-sm text-text-muted">
                        {messages.preparingLink}
                      </span>
                    )}
                    {awaitingConfirmation && (
                      <button
                        type="button"
                        disabled={disabled}
                        onClick={() => act(transfer, "confirm")}
                        className="min-h-11 rounded-lg border border-success px-4 text-success disabled:opacity-50"
                      >
                        {messages.confirmReceived}
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => act(transfer, "cancel")}
                      className="min-h-11 rounded-lg border border-border px-4 text-text-muted disabled:opacity-50"
                    >
                      {messages.dismiss}
                    </button>
                  </div>
                )}
                {awaitingConfirmation && (
                  <p className="mt-2 text-sm text-text-muted">{messages.downloadStarted}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
