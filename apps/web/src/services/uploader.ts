import { createSHA256, sha256 } from "hash-wasm";

import { ApiError, NetworkError, type TransferApi } from "./api";
import type { Transfer } from "./schemas";

// Envoi d'un fichier par blocs (§9.2). Pas de crypto.subtle en HTTP local :
// hachage avec hash-wasm. Un seul bloc en mémoire à la fois (§5.1).

export type UploadStatus =
  | "queued"
  | "uploading"
  | "retrying"
  | "verifying"
  | "completed"
  | "failed"
  | "cancelled";

export interface UploadProgress {
  status: UploadStatus;
  /** Octets confirmés par le serveur (jamais les octets simplement envoyés). */
  confirmedBytes: number;
  totalBytes: number;
  bytesPerSecond: number;
  transferId?: string;
  errorCode?: string;
}

export interface UploadDeps {
  api: TransferApi;
  token: string;
  onProgress: (progress: UploadProgress) => void;
  /** Délais successifs entre deux tentatives quand le PC est injoignable. */
  retryDelaysMs?: readonly number[];
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
}

const DEFAULT_RETRY_DELAYS = [500, 1000, 2000, 4000, 8000, 15000] as const;

const defaultSleep = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });

export interface UploadableFile {
  readonly name: string;
  readonly size: number;
  slice(start?: number, end?: number): Blob;
}

/** Réessaie une opération tant que le serveur est injoignable ; les erreurs API sont finales. */
async function withRetry<T>(
  operation: () => Promise<T>,
  delays: readonly number[],
  sleep: (ms: number) => Promise<void>,
  onRetry: () => void,
): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      const delay = delays[attempt];
      if (!(error instanceof NetworkError) || delay === undefined) throw error;
      onRetry();
      await sleep(delay);
    }
  }
}

export async function uploadFile(file: UploadableFile, deps: UploadDeps): Promise<Transfer> {
  const {
    api,
    token,
    onProgress,
    retryDelaysMs = DEFAULT_RETRY_DELAYS,
    now = () => performance.now(),
    sleep = defaultSleep,
  } = deps;

  const started = now();
  const report = (status: UploadStatus, confirmedBytes: number, extra: Partial<UploadProgress> = {}) => {
    const elapsed = (now() - started) / 1000;
    onProgress({
      status,
      confirmedBytes,
      totalBytes: file.size,
      bytesPerSecond: elapsed > 0 ? confirmedBytes / elapsed : 0,
      ...extra,
    });
  };

  let transferId: string | undefined;
  try {
    const retry = <T,>(op: () => Promise<T>, confirmed: number) =>
      withRetry(op, retryDelaysMs, sleep, () =>
        report("retrying", confirmed, transferId ? { transferId } : {}),
      );

    const transfer = await retry(() => api.create(token, file.name, file.size), 0);
    transferId = transfer.id;
    report("uploading", 0, { transferId });

    const fileHasher = await createSHA256();
    fileHasher.init();
    let confirmed = 0;

    for (let index = 0; index < transfer.total_chunks; index += 1) {
      const start = index * transfer.chunk_size;
      const end = Math.min(start + transfer.chunk_size, file.size);
      const bytes = new Uint8Array(await file.slice(start, end).arrayBuffer());
      fileHasher.update(bytes);
      const chunkHash = await sha256(bytes);

      const ack = await retry(
        () => api.putChunk(token, transfer.id, index, bytes, chunkHash),
        confirmed,
      );
      confirmed = ack.received_bytes;
      report("uploading", confirmed, { transferId });
    }

    report("verifying", confirmed, { transferId });
    const done = await retry(
      () => api.complete(token, transfer.id, fileHasher.digest("hex")),
      confirmed,
    );
    if (done.status === "completed") {
      report("completed", done.received_bytes, { transferId });
    } else {
      report("failed", done.received_bytes, {
        transferId,
        errorCode: done.error_code ?? "UNKNOWN",
      });
    }
    return done;
  } catch (error) {
    const errorCode =
      error instanceof ApiError
        ? error.code
        : error instanceof NetworkError
          ? "NETWORK_UNREACHABLE"
          : "UNEXPECTED";
    report("failed", 0, { ...(transferId ? { transferId } : {}), errorCode });
    throw error;
  }
}
