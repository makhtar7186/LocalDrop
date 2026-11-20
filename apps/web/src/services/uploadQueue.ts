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
) => Promise<unknown>;

export class UploadQueue {
  private items: UploadItem[] = [];
  private readonly pending: Array<{ key: number; file: UploadableFile }> = [];
  private readonly listeners = new Set<() => void>();
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
      const key = this.nextKey++;
      this.pending.push({ key, file });
      this.items = [
        ...this.items,
        {
          key,
          name: file.name,
          progress: { status: "queued", confirmedBytes: 0, totalBytes: file.size, bytesPerSecond: 0 },
        },
      ];
    }
    this.emit();
    this.pump();
  }

  private pump(): void {
    while (this.active < this.maxConcurrent) {
      const next = this.pending.shift();
      if (!next) return;
      this.active += 1;
      this.run(next.file, (progress) => this.update(next.key, progress))
        .catch(() => {
          // l'état « failed » a déjà été publié par l'uploader
        })
        .finally(() => {
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
