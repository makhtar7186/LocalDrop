import type { z } from "zod";

import {
  errorBodySchema,
  joinResponseSchema,
  type JoinResponse,
  type Platform,
  sessionStatusSchema,
  type SessionStatus,
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
  schema: z.ZodType<T>,
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
        ...(rest.body ? { "Content-Type": "application/json" } : {}),
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
