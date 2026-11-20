import { sha256 } from "hash-wasm";

import { ApiError, NetworkError, type TransferApi } from "../src/services/api";
import type { ChunkAck, Transfer } from "../src/services/schemas";
import { UploadQueue } from "../src/services/uploadQueue";
import { UploadCancelledError, uploadFile, type UploadProgress } from "../src/services/uploader";

const CHUNK = 4;

/** Faux serveur : vérifie réellement taille et SHA-256 de chaque bloc. */
class FakeServer implements TransferApi {
  chunks = new Map<number, Uint8Array>();
  completedWith: string | null = null;
  failNextPuts = 0;
  size = 0;

  private transfer(status: Transfer["status"] = "waiting"): Transfer {
    return {
      id: "t1",
      direction: "upload",
      filename: "f",
      safe_filename: "f",
      size: this.size,
      chunk_size: CHUNK,
      total_chunks: Math.ceil(this.size / CHUNK),
      status,
      received_bytes: [...this.chunks.values()].reduce((n, c) => n + c.length, 0),
      sha256: null,
      error_code: null,
      fully_served: false,
      created_at: "2026-11-20T10:00:00Z",
    };
  }

  create = vi.fn((_token: string, _name: string, size: number) => {
    this.size = size;
    return Promise.resolve(this.transfer());
  });

  putChunk = vi.fn(async (_t: string, _id: string, index: number, data: Uint8Array, hash: string) => {
    if (this.failNextPuts > 0) {
      this.failNextPuts -= 1;
      throw new NetworkError();
    }
    if ((await sha256(data)) !== hash) throw new ApiError(422, "CHUNK_HASH_MISMATCH", "hash");
    this.chunks.set(index, data.slice());
    const ack: ChunkAck = {
      index,
      already_received: false,
      received_bytes: this.transfer().received_bytes,
      status: "transferring",
    };
    return ack;
  });

  receivedChunks = vi.fn(() => Promise.resolve([...this.chunks.keys()]));

  complete = vi.fn(async (_t: string, _id: string, hash: string) => {
    this.completedWith = hash;
    const assembled = new Uint8Array(this.size);
    for (const [index, data] of this.chunks) assembled.set(data, index * CHUNK);
    const ok = (await sha256(assembled)) === hash;
    return { ...this.transfer(ok ? "completed" : "failed"), error_code: ok ? null : "FILE_HASH_MISMATCH" };
  });

  cancel = vi.fn(() => Promise.resolve(this.transfer("cancelled")));

  list = vi.fn(() => Promise.resolve([this.transfer()]));

  paused = false;
  resume = vi.fn(() => {
    this.paused = false;
    return Promise.resolve(this.transfer("transferring"));
  });
}

const bytes = (text: string) => new TextEncoder().encode(text);
const fileOf = (text: string, name = "note.txt") => new File([bytes(text)], name);
const noSleep = () => Promise.resolve();

it("hash-wasm fonctionne sans crypto.subtle (vecteur NIST)", async () => {
  expect(await sha256(bytes("abc"))).toBe(
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  );
});

describe("uploadFile", () => {
  it("FR-021 : découpe en blocs, hache chaque bloc et le fichier entier", async () => {
    const server = new FakeServer();
    const updates: UploadProgress[] = [];
    const done = await uploadFile(fileOf("bonjour le PC"), {
      api: server,
      token: "tok",
      onProgress: (p) => updates.push(p),
      sleep: noSleep,
    });

    expect(done.status).toBe("completed");
    expect(server.putChunk).toHaveBeenCalledTimes(4); // 13 octets / 4
    expect([...server.chunks.values()].map((c) => c.length)).toEqual([4, 4, 4, 1]);
    expect(server.completedWith).toBe(await sha256(bytes("bonjour le PC")));

    // Progression = octets confirmés par le serveur, croissante, puis vérification.
    const uploading = updates.filter((u) => u.status === "uploading").map((u) => u.confirmedBytes);
    expect(uploading).toEqual([0, 4, 8, 12, 13]);
    expect(updates.at(-2)?.status).toBe("verifying");
    expect(updates.at(-1)).toMatchObject({ status: "completed", confirmedBytes: 13, totalBytes: 13 });
  });

  it("fichier vide : finalisation directe", async () => {
    const server = new FakeServer();
    const done = await uploadFile(fileOf(""), { api: server, token: "t", onProgress: () => {} });
    expect(server.putChunk).not.toHaveBeenCalled();
    expect(done.status).toBe("completed");
  });

  it("FR-026 : réessaie quand le PC est injoignable, sans renvoyer les blocs confirmés", async () => {
    const server = new FakeServer();
    const statuses: string[] = [];
    const original = server.putChunk.getMockImplementation();
    if (!original) throw new Error("implémentation manquante");
    let calls = 0;
    server.putChunk.mockImplementation(async (...args) => {
      calls += 1;
      if (calls === 2 || calls === 3) throw new NetworkError(); // coupure sur le 2e bloc
      return original(...args);
    });

    const done = await uploadFile(fileOf("12345678"), {
      api: server,
      token: "t",
      onProgress: (p) => statuses.push(p.status),
      sleep: noSleep,
    });

    expect(done.status).toBe("completed");
    expect(statuses).toContain("retrying");
    const indexes = server.putChunk.mock.calls.map((call) => call[2]);
    expect(indexes).toEqual([0, 1, 1, 1]); // le bloc 0 n'est jamais renvoyé
  });

  it("abandonne après épuisement des tentatives", async () => {
    const server = new FakeServer();
    server.failNextPuts = 10;
    const updates: UploadProgress[] = [];
    await expect(
      uploadFile(fileOf("abcd"), {
        api: server,
        token: "t",
        onProgress: (p) => updates.push(p),
        retryDelaysMs: [1, 1],
        sleep: noSleep,
      }),
    ).rejects.toBeInstanceOf(NetworkError);
    expect(updates.at(-1)).toMatchObject({ status: "failed", errorCode: "NETWORK_UNREACHABLE" });
  });

  it("une erreur API est finale et signalée avec son code", async () => {
    const server = new FakeServer();
    server.create.mockRejectedValueOnce(new ApiError(507, "INSUFFICIENT_DISK_SPACE", "plein"));
    const updates: UploadProgress[] = [];
    await expect(
      uploadFile(fileOf("abcd"), { api: server, token: "t", onProgress: (p) => updates.push(p) }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(updates.at(-1)).toMatchObject({ status: "failed", errorCode: "INSUFFICIENT_DISK_SPACE" });
  });
});

describe("UploadQueue", () => {
  it("limite le nombre d'envois simultanés", async () => {
    let running = 0;
    let maxRunning = 0;
    const releases: Array<() => void> = [];
    const queue = new UploadQueue(
      () =>
        new Promise<void>((resolve) => {
          running += 1;
          maxRunning = Math.max(maxRunning, running);
          releases.push(() => {
            running -= 1;
            resolve();
          });
        }),
      2,
    );

    queue.add([fileOf("a", "1"), fileOf("b", "2"), fileOf("c", "3")]);
    expect(queue.getSnapshot().map((i) => i.name)).toEqual(["1", "2", "3"]);
    expect(running).toBe(2);

    releases.shift()?.();
    await vi.waitFor(() => expect(releases).toHaveLength(2));
    releases.forEach((release) => release());
    expect(maxRunning).toBe(2);
  });
});

describe("reprise (FR-026)", () => {
  beforeEach(() => window.localStorage.clear());

  it("n'envoie que les blocs manquants mais hache tout le fichier", async () => {
    const server = new FakeServer();
    const content = "abcdefghij"; // blocs : abcd | efgh | ij
    server.size = content.length;
    server.chunks.set(0, bytes("abcd"));
    server.chunks.set(2, bytes("ij"));
    const existing: Transfer = {
      id: "t1",
      direction: "upload",
      filename: "f",
      safe_filename: "f",
      size: 10,
      chunk_size: CHUNK,
      total_chunks: 3,
      status: "paused",
      received_bytes: 6,
      sha256: null,
      error_code: null,
      fully_served: false,
      created_at: "2026-11-20T10:00:00Z",
    };
    const updates: UploadProgress[] = [];

    const done = await uploadFile(
      fileOf(content),
      { api: server, token: "t", onProgress: (p) => updates.push(p), sleep: noSleep },
      { resume: existing },
    );

    expect(server.create).not.toHaveBeenCalled();
    expect(server.resume).toHaveBeenCalledTimes(1); // le transfert était en pause
    expect(server.putChunk.mock.calls.map((c) => c[2])).toEqual([1]);
    expect(server.completedWith).toBe(await sha256(bytes(content)));
    expect(done.status).toBe("completed");
    expect(updates[0]?.confirmedBytes).toBe(6); // la progression repart de l'acquis
  });

  it("reprend tout seul quand le PC a redémarré (TRANSFER_PAUSED)", async () => {
    const server = new FakeServer();
    const original = server.putChunk.getMockImplementation();
    if (!original) throw new Error("implémentation manquante");
    let calls = 0;
    server.putChunk.mockImplementation(async (...args) => {
      calls += 1;
      if (calls === 2) throw new ApiError(409, "TRANSFER_PAUSED", "pause");
      return original(...args);
    });

    const done = await uploadFile(fileOf("12345678"), {
      api: server,
      token: "t",
      onProgress: () => {},
      sleep: noSleep,
    });
    expect(done.status).toBe("completed");
    expect(server.resume).toHaveBeenCalledTimes(1);
    expect(server.putChunk.mock.calls.map((c) => c[2])).toEqual([0, 1, 1]);
  });

  it("mémorise l'envoi en cours puis l'oublie une fois terminé", async () => {
    const server = new FakeServer();
    let remembered: string | null = null;
    await uploadFile(fileOf("abcd", "notes.txt"), {
      api: server,
      token: "t",
      onProgress: (p) => {
        if (p.status === "uploading") remembered = window.localStorage.getItem("localdrop.uploads");
      },
      sleep: noSleep,
    });
    expect(remembered).toContain("notes.txt");
    expect(window.localStorage.getItem("localdrop.uploads")).toBe("{}");
  });

  it("garde l'envoi reprenable après une coupure réseau définitive", async () => {
    const server = new FakeServer();
    server.failNextPuts = 10;
    await expect(
      uploadFile(fileOf("abcd", "long.mp4"), {
        api: server,
        token: "t",
        onProgress: () => {},
        retryDelaysMs: [1],
        sleep: noSleep,
      }),
    ).rejects.toBeInstanceOf(NetworkError);
    expect(window.localStorage.getItem("localdrop.uploads")).toContain("long.mp4");
  });
});

describe("annulation (FR-025)", () => {
  beforeEach(() => window.localStorage.clear());

  it("interrompt l'envoi entre deux blocs et l'annule sur le PC", async () => {
    const server = new FakeServer();
    const controller = new AbortController();
    const statuses: string[] = [];
    server.putChunk.mockImplementationOnce(async (_t, _id, index, data) => {
      controller.abort(); // l'utilisateur annule pendant l'envoi du premier bloc
      return { index, already_received: false, received_bytes: data.length, status: "transferring" as const };
    });

    await expect(
      uploadFile(
        fileOf("0123456789ab"),
        { api: server, token: "t", onProgress: (p) => statuses.push(p.status), sleep: noSleep },
        { signal: controller.signal },
      ),
    ).rejects.toBeInstanceOf(UploadCancelledError);

    expect(server.putChunk).toHaveBeenCalledTimes(1); // plus aucun bloc après l'annulation
    expect(server.complete).not.toHaveBeenCalled();
    expect(server.cancel).toHaveBeenCalledTimes(1);
    expect(statuses.at(-1)).toBe("cancelled");
    expect(window.localStorage.getItem("localdrop.uploads")).toBe("{}");
  });

  it("une annulation pendant une coupure réseau arrête les réessais", async () => {
    const server = new FakeServer();
    server.failNextPuts = 100;
    const controller = new AbortController();
    let sleeps = 0;
    await expect(
      uploadFile(
        fileOf("abcd"),
        {
          api: server,
          token: "t",
          onProgress: () => {},
          sleep: () => {
            sleeps += 1;
            if (sleeps === 2) controller.abort();
            return Promise.resolve();
          },
        },
        { signal: controller.signal },
      ),
    ).rejects.toBeInstanceOf(UploadCancelledError);
    expect(sleeps).toBe(2);
  });

  it("annuler un envoi encore en file d'attente ne le démarre jamais", async () => {
    const started: string[] = [];
    const releases: Array<() => void> = [];
    const queue = new UploadQueue((file) => {
      started.push(file.name);
      return new Promise<void>((resolve) => releases.push(resolve));
    }, 1);
    queue.add([fileOf("a", "1"), fileOf("b", "2")]);
    const second = queue.getSnapshot()[1];
    if (!second) throw new Error("élément manquant");

    queue.cancel(second.key);
    expect(queue.getSnapshot()[1]?.progress.status).toBe("cancelled");
    releases.shift()?.();
    await vi.waitFor(() => expect(started).toEqual(["1"]));
  });
});
