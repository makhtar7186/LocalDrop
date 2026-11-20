import { type ChangeEvent, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { formatBytes, formatSpeed, percent } from "../../app/format";
import { messages } from "../../app/messages";
import type { TransferApi } from "../../services/api";
import { findUpload, forgetUpload, sameFile } from "../../services/pendingUploads";
import type { Transfer } from "../../services/schemas";
import { type UploadItem, UploadQueue } from "../../services/uploadQueue";
import { uploadFile, type UploadProgress } from "../../services/uploader";

export interface SendPanelProps {
  token: string;
  api: TransferApi;
  maxConcurrent?: number;
  retryDelaysMs?: readonly number[];
}

const RESUMABLE = new Set<Transfer["status"]>(["waiting", "transferring", "paused"]);

function statusText(progress: UploadProgress): string {
  switch (progress.status) {
    case "queued":
      return messages.uploadQueued;
    case "uploading":
      return `${percent(progress.confirmedBytes, progress.totalBytes)} % · ${formatSpeed(progress.bytesPerSecond)}`;
    case "retrying":
      return messages.uploadRetrying;
    case "verifying":
      return messages.uploadVerifying;
    case "completed":
      return messages.uploadCompleted;
    case "cancelled":
      return messages.uploadCancelled;
    case "failed":
      return messages.uploadFailed(progress.errorCode ?? "UNKNOWN");
  }
}

const barColor: Partial<Record<UploadProgress["status"], string>> = {
  completed: "bg-success",
  failed: "bg-danger",
  retrying: "bg-warning",
};

function ProgressBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      className="mt-2 h-2 overflow-hidden rounded bg-border"
    >
      <div className={`h-full transition-[width] ${color}`} style={{ width: `${value}%` }} />
    </div>
  );
}

function UploadRow({ item }: { item: UploadItem }) {
  const { progress } = item;
  return (
    <li className="rounded-lg border border-border bg-surface-raised p-3" data-status={progress.status}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate font-medium" title={item.name}>
          {item.name}
        </span>
        <span className="shrink-0 text-sm text-text-muted">{formatBytes(progress.totalBytes)}</span>
      </div>
      <ProgressBar
        label={item.name}
        value={percent(progress.confirmedBytes, progress.totalBytes)}
        color={barColor[progress.status] ?? "bg-accent"}
      />
      <p className="mt-1 text-sm text-text-muted">{statusText(progress)}</p>
    </li>
  );
}

interface InterruptedRowProps {
  transfer: Transfer;
  error: string | undefined;
  onFile: (transfer: Transfer, file: File) => void;
  onAbandon: (transfer: Transfer) => void;
}

function InterruptedRow({ transfer, error, onFile, onAbandon }: InterruptedRowProps) {
  const name = findUpload(transfer.id)?.name ?? transfer.filename;
  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) onFile(transfer, file);
  };
  return (
    <li className="rounded-lg border border-warning bg-surface-raised p-3" data-status="interrupted">
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate font-medium" title={name}>
          {name}
        </span>
        <span className="shrink-0 text-sm text-text-muted">{formatBytes(transfer.size)}</span>
      </div>
      <ProgressBar
        label={name}
        value={percent(transfer.received_bytes, transfer.size)}
        color="bg-warning"
      />
      <p className="mt-1 text-sm text-text-muted">
        {messages.interruptedHint(percent(transfer.received_bytes, transfer.size))}
      </p>
      {error && <p className="mt-1 text-sm text-danger">{error}</p>}
      <div className="mt-2 flex flex-wrap gap-2">
        <label className="flex min-h-11 cursor-pointer items-center rounded-lg bg-accent px-4 font-medium text-white focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
          {messages.resumeUpload}
          <input type="file" className="sr-only" onChange={onChange} aria-label={messages.resumeUploadOf(name)} />
        </label>
        <button
          type="button"
          onClick={() => onAbandon(transfer)}
          className="min-h-11 rounded-lg border border-border px-4 text-text-muted"
        >
          {messages.abandonUpload}
        </button>
      </div>
    </li>
  );
}

export function SendPanel({ token, api, maxConcurrent = 2, retryDelaysMs }: SendPanelProps) {
  const queue = useMemo(
    () =>
      new UploadQueue(
        (file, onProgress, resume) =>
          uploadFile(
            file,
            { api, token, onProgress, ...(retryDelaysMs ? { retryDelaysMs } : {}) },
            resume ? { resume } : {},
          ),
        maxConcurrent,
      ),
    [api, token, maxConcurrent, retryDelaysMs],
  );
  const items = useSyncExternalStore(queue.subscribe, queue.getSnapshot);

  // Envois interrompus (rechargement de page, téléphone redémarré…) : proposés à la reprise.
  const [interrupted, setInterrupted] = useState<Transfer[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => {
    let cancelled = false;
    api.list(token).then(
      (all) => {
        if (cancelled) return;
        setInterrupted(all.filter((t) => t.direction === "upload" && RESUMABLE.has(t.status)));
      },
      () => {
        // hors connexion : rien à proposer pour l'instant
      },
    );
    return () => {
      cancelled = true;
    };
  }, [api, token]);

  const inQueue = new Set(items.map((i) => i.progress.transferId).filter(Boolean));
  const toResume = interrupted.filter((t) => !inQueue.has(t.id));

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    if (files.length > 0) queue.add(files);
    event.target.value = ""; // permet de resélectionner le même fichier
  };

  const onResumeFile = (transfer: Transfer, file: File) => {
    const expected = findUpload(transfer.id) ?? { name: transfer.filename, size: transfer.size };
    if (!sameFile(file, expected)) {
      setErrors((prev) => ({ ...prev, [transfer.id]: messages.wrongFile(expected.name) }));
      return;
    }
    setErrors(({ [transfer.id]: _removed, ...rest }) => rest);
    queue.resume(file, transfer);
    setInterrupted((prev) => prev.filter((t) => t.id !== transfer.id));
  };

  const onAbandon = (transfer: Transfer) => {
    api.cancel(token, transfer.id).then(
      () => {
        forgetUpload(transfer.id);
        setInterrupted((prev) => prev.filter((t) => t.id !== transfer.id));
      },
      () => setErrors((prev) => ({ ...prev, [transfer.id]: messages.actionFailed })),
    );
  };

  const busy = items.some((i) => !["completed", "failed", "cancelled"].includes(i.progress.status));

  return (
    <section className="flex flex-col gap-4" aria-labelledby="send-title">
      <h2 id="send-title" className="text-lg font-medium">
        {messages.sendTitle}
      </h2>

      <label className="flex min-h-12 cursor-pointer items-center justify-center rounded-lg bg-accent px-4 font-medium text-white focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
        {messages.chooseFiles}
        <input type="file" multiple className="sr-only" onChange={onChange} />
      </label>

      {busy && <p className="text-sm text-warning">{messages.keepPageOpen}</p>}

      {toResume.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label={messages.interruptedListLabel}>
          {toResume.map((transfer) => (
            <InterruptedRow
              key={transfer.id}
              transfer={transfer}
              error={errors[transfer.id]}
              onFile={onResumeFile}
              onAbandon={onAbandon}
            />
          ))}
        </ul>
      )}

      {items.length === 0 ? (
        toResume.length === 0 && <p className="text-text-muted">{messages.noUploads}</p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label={messages.uploadsListLabel}>
          {items.map((item) => (
            <UploadRow key={item.key} item={item} />
          ))}
        </ul>
      )}
    </section>
  );
}
