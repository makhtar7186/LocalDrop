import { useEffect, useState } from "react";

import { formatBytes, formatDate } from "../../app/format";
import { messages } from "../../app/messages";
import { useRealtimeNudge } from "../../hooks/useRealtimeNudge";
import type { HistoryApi, HistoryFilters } from "../../services/api";
import type { RealtimeConnection, RealtimeEvent } from "../../services/realtime";
import type { Transfer } from "../../services/schemas";

// Historique des transferts de ce téléphone (FR-034, §14.3), relu à chaque événement
// temps réel. Le serveur ne renvoie que les transferts de l'appareil authentifié.

export interface HistoryPanelProps {
  token: string;
  api: HistoryApi;
  realtime?: RealtimeConnection;
  pageSize?: number;
  searchDelayMs?: number;
}

type Tab = "all" | "upload" | "download";

const isTransferEvent = (event: RealtimeEvent) => event.type.startsWith("transfer.");

const statusTone: Partial<Record<Transfer["status"], string>> = {
  completed: "text-success",
  failed: "text-danger",
  cancelled: "text-text-muted",
};

function statusLabel(transfer: Transfer): string {
  if (transfer.status === "cancelled" && transfer.error_code === "EXPIRED") return messages.expired;
  return messages.transferStatus[transfer.status] ?? transfer.status;
}

export function HistoryPanel({
  token,
  api,
  realtime,
  pageSize = 20,
  searchDelayMs = 300,
}: HistoryPanelProps) {
  const [tab, setTab] = useState<Tab>("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(pageSize);
  const [items, setItems] = useState<Transfer[] | null>(null);
  const [total, setTotal] = useState(0);
  const [failed, setFailed] = useState(false);
  const nudge = useRealtimeNudge(realtime, isTransferEvent);

  // Recherche différée : pas une requête par frappe.
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), searchDelayMs);
    return () => window.clearTimeout(timer);
  }, [search, searchDelayMs]);

  useEffect(() => {
    let cancelled = false;
    const filters: HistoryFilters = {
      limit: shown,
      offset: 0,
      ...(tab === "all" ? {} : { direction: tab }),
      ...(query ? { q: query } : {}),
    };
    api.list(token, filters).then(
      (page) => {
        if (cancelled) return;
        setItems(page.items);
        setTotal(page.total);
        setFailed(false);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [api, token, tab, query, shown, nudge]);

  const tabs: Array<[Tab, string]> = [
    ["all", messages.historyAll],
    ["upload", messages.historySent],
    ["download", messages.historyReceived],
  ];

  return (
    <section className="flex flex-col gap-3" aria-labelledby="history-title">
      <h2 id="history-title" tabIndex={-1} className="text-lg font-medium">
        {messages.historyTitle}
      </h2>

      <div role="tablist" aria-label={messages.historyTitle} className="flex gap-2">
        {tabs.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => {
              setTab(value);
              setShown(pageSize);
            }}
            className={`min-h-11 flex-1 rounded-lg border px-3 ${
              tab === value ? "border-accent bg-accent text-white" : "border-border text-text-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <input
        type="search"
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setShown(pageSize);
        }}
        placeholder={messages.historySearch}
        aria-label={messages.historySearch}
        className="min-h-11 rounded-lg border border-border bg-surface-raised px-3 text-text placeholder:text-text-muted"
      />

      {failed && <p className="text-sm text-warning">{messages.historyError}</p>}

      {items === null ? (
        !failed && <p className="text-text-muted">{messages.historyLoading}</p>
      ) : items.length === 0 ? (
        <p className="text-text-muted">
          {query || tab !== "all" ? messages.historyNoMatch : messages.historyEmpty}
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-2" aria-label={messages.historyListLabel}>
            {items.map((transfer) => (
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
                <div className="mt-1 flex flex-wrap justify-between gap-x-3 text-sm">
                  <span className="text-text-muted">
                    {transfer.direction === "upload"
                      ? messages.directionSent
                      : messages.directionReceived}
                    {" · "}
                    {formatDate(transfer.created_at)}
                  </span>
                  <span className={statusTone[transfer.status] ?? "text-warning"}>
                    {statusLabel(transfer)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          {items.length < total && (
            <button
              type="button"
              onClick={() => setShown((n) => n + pageSize)}
              className="min-h-11 rounded-lg border border-border px-4 text-text-muted"
            >
              {messages.historyMore}
            </button>
          )}
        </>
      )}
    </section>
  );
}
