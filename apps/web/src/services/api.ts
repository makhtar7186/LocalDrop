import type * as z from "zod/mini";

import {
  type ChunkAck,
  chunkAckSchema,
  chunkListSchema,
  type DownloadTicket,
  downloadTicketSchema,
  errorBodySchema,
  type HistoryPage,
  historyPageSchema,
  joinResponseSchema,
  type JoinResponse,
  type Platform,
  sessionStatusSchema,
  type SessionStatus,
  type Transfer,
  transferListSchema,
  transferSchema,
} from "./schemas";

const API_BASE = "/api/v1";

/** Erreur renvoyée par le serveur (format { error: { code, message } }). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Serveur injoignable (Wi-Fi coupé, PC éteint, page en arrière-plan…). */
export class NetworkError extends Error {
  constructor() {
    super("Serveur injoignable");
    this.name = "NetworkError";
  }
}

async function request<T>(
  schema: z.ZodMiniType<T>,
  path: string,
  init: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, ...rest } = init;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: {
        Accept: "application/json",
        ...(typeof rest.body === "string" ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch {
    throw new NetworkError();
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = errorBodySchema.safeParse(body);
    throw parsed.success
      ? new ApiError(response.status, parsed.data.error.code, parsed.data.error.message)
      : new ApiError(response.status, "HTTP_ERROR", `Erreur ${response.status}`);
  }
  return schema.parse(body);
}

export interface JoinInput {
  sessionId: string;
  secret: string;
  displayName: string;
  platform: Platform;
}

export interface PairingApi {
  join(input: JoinInput): Promise<JoinResponse>;
  status(token: string): Promise<SessionStatus>;
}

export const pairingApi: PairingApi = {
  join: (input) =>
    request(joinResponseSchema, "/sessions/join", {
      method: "POST",
      body: JSON.stringify({
        session_id: input.sessionId,
        secret: input.secret,
        display_name: input.displayName,
        platform: input.platform,
      }),
    }),
  status: (token) => request(sessionStatusSchema, "/sessions/status", { token }),
};

export interface TransferApi {
  create(token: string, filename: string, size: number): Promise<Transfer>;
  putChunk(
    token: string,
    transferId: string,
    index: number,
    data: Uint8Array<ArrayBuffer>,
    sha256: string,
  ): Promise<ChunkAck>;
  receivedChunks(token: string, transferId: string): Promise<number[]>;
  complete(token: string, transferId: string, sha256: string): Promise<Transfer>;
  cancel(token: string, transferId: string): Promise<Transfer>;
  /** Transferts de l'appareil (pour proposer la reprise des envois interrompus). */
  list(token: string): Promise<Transfer[]>;
  resume(token: string, transferId: string): Promise<Transfer>;
}

const enc = encodeURIComponent;

export const transferApi: TransferApi = {
  create: (token, filename, size) =>
    request(transferSchema, "/transfers", {
      method: "POST",
      token,
      body: JSON.stringify({ filename, size }),
    }),
  putChunk: (token, transferId, index, data, sha256) =>
    request(chunkAckSchema, `/transfers/${enc(transferId)}/chunks/${index}`, {
      method: "PUT",
      token,
      body: data,
      headers: { "Content-Type": "application/octet-stream", "X-Chunk-SHA256": sha256 },
    }),
  receivedChunks: async (token, transferId) => {
    const result = await request(chunkListSchema, `/transfers/${enc(transferId)}/chunks`, {
      token,
    });
    return result.received;
  },
  complete: (token, transferId, sha256) =>
    request(transferSchema, `/transfers/${enc(transferId)}/complete`, {
      method: "POST",
      token,
      body: JSON.stringify({ sha256 }),
    }),
  cancel: (token, transferId) =>
    request(transferSchema, `/transfers/${enc(transferId)}/cancel`, { method: "POST", token }),
  list: (token) => request(transferListSchema, "/transfers", { token }),
  resume: (token, transferId) =>
    request(transferSchema, `/transfers/${enc(transferId)}/resume`, { method: "POST", token }),
};

export interface ReceiveApi {
  list(token: string): Promise<Transfer[]>;
  ticket(token: string, transferId: string): Promise<DownloadTicket>;
  confirm(token: string, transferId: string): Promise<Transfer>;
  cancel(token: string, transferId: string): Promise<Transfer>;
}

export const receiveApi: ReceiveApi = {
  list: (token) => request(transferListSchema, "/transfers", { token }),
  ticket: (token, transferId) =>
    request(downloadTicketSchema, `/transfers/${enc(transferId)}/download-ticket`, {
      method: "POST",
      token,
    }),
  confirm: (token, transferId) =>
    request(transferSchema, `/transfers/${enc(transferId)}/confirm`, { method: "POST", token }),
  cancel: (token, transferId) =>
    request(transferSchema, `/transfers/${enc(transferId)}/cancel`, { method: "POST", token }),
};

export interface HistoryFilters {
  direction?: "upload" | "download";
  q?: string;
  limit?: number;
  offset?: number;
}

export interface HistoryApi {
  list(token: string, filters: HistoryFilters): Promise<HistoryPage>;
}

export const historyApi: HistoryApi = {
  list: (token, filters) => {
    const params = new URLSearchParams();
    if (filters.direction) params.set("direction", filters.direction);
    if (filters.q) params.set("q", filters.q);
    params.set("limit", String(filters.limit ?? 20));
    params.set("offset", String(filters.offset ?? 0));
    return request(historyPageSchema, `/history?${params.toString()}`, { token });
  },
};
