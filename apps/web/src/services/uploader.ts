import { createSHA256, sha256 } from "hash-wasm";

import { ApiError, NetworkError, type TransferApi } from "./api";
import { forgetUpload, rememberUpload } from "./pendingUploads";
import type { Transfer } from "./schemas";

// Envoi d'un fichier par blocs (§9.2) avec reprise (FR-026).
// - Pas de crypto.subtle en HTTP local : hachage avec hash-wasm.
// - Un seul bloc en mémoire à la fois (§5.1).
// - Reprise : seuls les blocs absents côté serveur sont envoyés, mais tout le fichier
//   est relu pour calculer le SHA-256 global vérifié à la finalisation.
// - Serveur redémarré pendant l'envoi : il répond TRANSFER_PAUSED, on reprend tout seul.

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

export interface UploadOptions {
  /** Transfert existant à reprendre (après rechargement de la page). */
  resume?: Transfer;
  /** Annulation demandée par l'utilisateur (FR-025). */
  signal?: AbortSignal;
}

/** Levée quand l'utilisateur annule : l'envoi est annulé aussi sur le PC. */
export class UploadCancelledError extends Error {
  constructor() {
    super("Envoi annulé");
    this.name = "UploadCancelledError";
  }
}

// ~1 min de tentatives : couvre une coupure Wi-Fi ou un redémarrage du PC.
const DEFAULT_RETRY_DELAYS = [500, 1000, 2000, 4000, 8000, 15000, 15000, 15000] as const;
const MAX_RESUMES_PER_CHUNK = 3;

const defaultSleep = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });

export interface UploadableFile {
  readonly name: string;
  readonly size: number;
  readonly lastModified?: number;
  slice(start?: number, end?: number): Blob;
}

/** Réessaie tant que le serveur est injoignable ; les erreurs API sont remontées. */
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

const isPaused = (error: unknown) => error instanceof ApiError && error.code === "TRANSFER_PAUSED";

export async function uploadFile(
  file: UploadableFile,
  deps: UploadDeps,
  options: UploadOptions = {},
): Promise<Transfer> {
  const {
    api,
    token,
    onProgress,
    retryDelaysMs = DEFAULT_RETRY_DELAYS,
    now = () => performance.now(),
    sleep = defaultSleep,
  } = deps;

  const started = now();
  let confirmed = options.resume?.received_bytes ?? 0;
  const initiallyConfirmed = confirmed;
  const report = (status: UploadStatus, extra: Partial<UploadProgress> = {}) => {
    const elapsed = (now() - started) / 1000;
    const sentThisSession = confirmed - initiallyConfirmed;
    onProgress({
      status,
      confirmedBytes: confirmed,
      totalBytes: file.size,
      bytesPerSecond: elapsed > 0 ? Math.max(0, sentThisSession) / elapsed : 0,
      ...(transferId ? { transferId } : {}),
      ...extra,
    });
  };

  let transferId: string | undefined = options.resume?.id;
  const { signal } = options;
  const throwIfCancelled = () => {
    if (signal?.aborted) throw new UploadCancelledError();
  };
  const retry = <T,>(op: () => Promise<T>) =>
    withRetry(
      () => {
        throwIfCancelled();
        return op();
      },
      retryDelaysMs,
      sleep,
      () => report("retrying"),
    );

  try {
    let transfer = options.resume ?? (await retry(() => api.create(token, file.name, file.size)));
    const id = transfer.id;
    transferId = id;
    rememberUpload({
      transferId: id,
      name: file.name,
      size: file.size,
      ...(file.lastModified !== undefined ? { lastModified: file.lastModified } : {}),
    });

    let alreadyReceived = new Set<number>();
    if (options.resume) {
      if (transfer.status === "paused") transfer = await retry(() => api.resume(token, id));
      alreadyReceived = new Set(await retry(() => api.receivedChunks(token, id)));
    }
    report("uploading");

    const fileHasher = await createSHA256();
    fileHasher.init();

    for (let index = 0; index < transfer.total_chunks; index += 1) {
      throwIfCancelled();
      const start = index * transfer.chunk_size;
      const end = Math.min(start + transfer.chunk_size, file.size);
      const bytes = new Uint8Array(await file.slice(start, end).arrayBuffer());
      fileHasher.update(bytes);
      if (alreadyReceived.has(index)) continue; // déjà validé : jamais renvoyé (FR-026)

      const chunkHash = await sha256(bytes);
      for (let resumes = 0; ; resumes += 1) {
        try {
          const ack = await retry(() => api.putChunk(token, id, index, bytes, chunkHash));
          confirmed = ack.received_bytes;
          break;
        } catch (error) {
          // Le PC a redémarré : le transfert est en pause, on le reprend.
          if (!isPaused(error) || resumes >= MAX_RESUMES_PER_CHUNK) throw error;
          await retry(() => api.resume(token, id));
        }
      }
      report("uploading");
    }

    throwIfCancelled();
    report("verifying");
    const done = await retry(() => api.complete(token, id, fileHasher.digest("hex")));
    confirmed = done.received_bytes;
    forgetUpload(id);
    if (done.status === "completed") {
      report("completed");
    } else {
      report("failed", { errorCode: done.error_code ?? "UNKNOWN" });
    }
    return done;
  } catch (error) {
    if (error instanceof UploadCancelledError) {
      if (transferId) {
        const id = transferId;
        // Libère la place sur le PC ; l'annulation reste effective même si le PC est injoignable.
        await api.cancel(token, id).catch(() => undefined);
        forgetUpload(id);
      }
      report("cancelled");
      throw error;
    }
    const errorCode =
      error instanceof ApiError
        ? error.code
        : error instanceof NetworkError
          ? "NETWORK_UNREACHABLE"
          : "UNEXPECTED";
    // Une erreur réseau laisse l'envoi reprenable ; une erreur API est définitive.
    if (transferId && error instanceof ApiError) forgetUpload(transferId);
    report("failed", { errorCode });
    throw error;
  }
}
