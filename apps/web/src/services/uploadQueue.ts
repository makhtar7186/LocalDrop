import type { Transfer } from "./schemas";
import type { UploadableFile, UploadProgress } from "./uploader";

// File d'envois hors de React (consommée via useSyncExternalStore) :
// au plus `maxConcurrent` fichiers en cours (§9.1 : 2 transferts simultanés).

export interface UploadItem {
  key: number;
  name: string;
  progress: UploadProgress;
}

export type RunUpload = (
  file: UploadableFile,
  onProgress: (progress: UploadProgress) => void,
  resume: Transfer | undefined,
  signal: AbortSignal,
) => Promise<unknown>;

interface Job {
  key: number;
  file: UploadableFile;
  resume?: Transfer;
  controller: AbortController;
}

export class UploadQueue {
  private items: UploadItem[] = [];
  private readonly pending: Job[] = [];
  private readonly listeners = new Set<() => void>();
  private readonly controllers = new Map<number, AbortController>();
  private active = 0;
  private nextKey = 1;

  constructor(
    private readonly run: RunUpload,
    private readonly maxConcurrent = 2,
  ) {}

  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  readonly getSnapshot = (): readonly UploadItem[] => this.items;

  add(files: Iterable<UploadableFile>): void {
    for (const file of files) {
      this.enqueue({ key: this.nextKey++, file, controller: new AbortController() });
    }
    this.emit();
    this.pump();
  }

  /** Reprend un transfert existant avec le fichier resélectionné (FR-026). */
  resume(file: UploadableFile, transfer: Transfer): void {
    this.enqueue({
      key: this.nextKey++,
      file,
      resume: transfer,
      controller: new AbortController(),
    });
    this.emit();
    this.pump();
  }

  /** Annule un envoi (FR-025) : retiré de la file s'il n'a pas commencé, sinon interrompu. */
  cancel(key: number): void {
    const waiting = this.pending.findIndex((job) => job.key === key);
    if (waiting >= 0) {
      this.pending.splice(waiting, 1);
      this.controllers.delete(key);
      const item = this.items.find((i) => i.key === key);
      if (item) this.update(key, { ...item.progress, status: "cancelled" });
      return;
    }
    this.controllers.get(key)?.abort();
  }

  private enqueue(job: Job): void {
    this.pending.push(job);
    this.controllers.set(job.key, job.controller);
    this.items = [
      ...this.items,
      {
        key: job.key,
        name: job.file.name,
        progress: {
          status: "queued",
          confirmedBytes: job.resume?.received_bytes ?? 0,
          totalBytes: job.file.size,
          bytesPerSecond: 0,
          ...(job.resume ? { transferId: job.resume.id } : {}),
        },
      },
    ];
  }

  private pump(): void {
    while (this.active < this.maxConcurrent) {
      const next = this.pending.shift();
      if (!next) return;
      this.active += 1;
      this.run(
        next.file,
        (progress) => this.update(next.key, progress),
        next.resume,
        next.controller.signal,
      )
        .catch(() => {
          // l'état « failed » a déjà été publié par l'uploader
        })
        .finally(() => {
          this.controllers.delete(next.key);
          this.active -= 1;
          this.pump();
        });
    }
  }

  private update(key: number, progress: UploadProgress): void {
    this.items = this.items.map((item) => (item.key === key ? { ...item, progress } : item));
    this.emit();
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }
}
