import { type ChangeEvent, useMemo, useSyncExternalStore } from "react";

import { formatBytes, formatSpeed, percent } from "../../app/format";
import { messages } from "../../app/messages";
import type { TransferApi } from "../../services/api";
import { type UploadItem, UploadQueue } from "../../services/uploadQueue";
import { uploadFile, type UploadProgress } from "../../services/uploader";

export interface SendPanelProps {
  token: string;
  api: TransferApi;
  maxConcurrent?: number;
  retryDelaysMs?: readonly number[];
}

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

function UploadRow({ item }: { item: UploadItem }) {
  const { progress } = item;
  const value = percent(progress.confirmedBytes, progress.totalBytes);
  return (
    <li className="rounded-lg border border-border bg-surface-raised p-3" data-status={progress.status}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="truncate font-medium" title={item.name}>
          {item.name}
        </span>
        <span className="shrink-0 text-sm text-text-muted">{formatBytes(progress.totalBytes)}</span>
      </div>
      <div
        role="progressbar"
        aria-label={item.name}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        className="mt-2 h-2 overflow-hidden rounded bg-border"
      >
        <div
          className={`h-full transition-[width] ${barColor[progress.status] ?? "bg-accent"}`}
          style={{ width: `${value}%` }}
        />
      </div>
      <p className="mt-1 text-sm text-text-muted">{statusText(progress)}</p>
    </li>
  );
}

export function SendPanel({ token, api, maxConcurrent = 2, retryDelaysMs }: SendPanelProps) {
  const queue = useMemo(
    () =>
      new UploadQueue(
        (file, onProgress) =>
          uploadFile(file, {
            api,
            token,
            onProgress,
            ...(retryDelaysMs ? { retryDelaysMs } : {}),
          }),
        maxConcurrent,
      ),
    [api, token, maxConcurrent, retryDelaysMs],
  );
  const items = useSyncExternalStore(queue.subscribe, queue.getSnapshot);

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    if (files.length > 0) queue.add(files);
    event.target.value = ""; // permet de resélectionner le même fichier
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

      {items.length === 0 ? (
        <p className="text-text-muted">{messages.noUploads}</p>
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
