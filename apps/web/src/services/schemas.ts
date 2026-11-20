import * as z from "zod/mini";

// Contrats de l'API v1 : toute réponse est validée avant usage.
// zod/mini : même validation que zod, API fonctionnelle bien plus légère dans le bundle.

const count = () => z.int().check(z.nonnegative());
const positive = () => z.int().check(z.positive());

export const deviceStatusSchema = z.enum([
  "pending",
  "connected",
  "disconnected",
  "rejected",
  "revoked",
]);
export type DeviceStatus = z.infer<typeof deviceStatusSchema>;

export const platformSchema = z.enum(["android", "ios", "windows", "other"]);
export type Platform = z.infer<typeof platformSchema>;

export const joinResponseSchema = z.object({
  device_id: z.string(),
  device_token: z.string().check(z.minLength(1)),
  status: deviceStatusSchema,
});
export type JoinResponse = z.infer<typeof joinResponseSchema>;

export const sessionStatusSchema = z.object({
  device_id: z.string(),
  display_name: z.string(),
  status: deviceStatusSchema,
  server_name: z.string(),
  session_expires_at: z.string(),
});
export type SessionStatus = z.infer<typeof sessionStatusSchema>;

export const errorBodySchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
});

export const transferStatusSchema = z.enum([
  "created",
  "waiting",
  "transferring",
  "paused",
  "verifying",
  "completed",
  "failed",
  "cancelled",
]);
export type TransferStatus = z.infer<typeof transferStatusSchema>;

export const transferSchema = z.object({
  id: z.string(),
  direction: z.enum(["upload", "download"]),
  filename: z.string(),
  safe_filename: z.string(),
  size: count(),
  chunk_size: positive(),
  total_chunks: count(),
  status: transferStatusSchema,
  received_bytes: count(),
  sha256: z.nullable(z.string()),
  error_code: z.nullable(z.string()),
  fully_served: z.boolean(),
  created_at: z.string(),
});
export type Transfer = z.infer<typeof transferSchema>;

export const transferListSchema = z.array(transferSchema);

export const chunkAckSchema = z.object({
  index: count(),
  already_received: z.boolean(),
  received_bytes: count(),
  status: transferStatusSchema,
});
export type ChunkAck = z.infer<typeof chunkAckSchema>;

export const chunkListSchema = z.object({
  transfer_id: z.string(),
  total_chunks: count(),
  received: z.array(count()),
});

export const downloadTicketSchema = z.object({
  url: z.string().check(z.startsWith("/api/v1/transfers/")),
  expires_at: z.string(),
});
export type DownloadTicket = z.infer<typeof downloadTicketSchema>;

export const historyPageSchema = z.object({
  items: z.array(transferSchema),
  total: count(),
  limit: positive(),
  offset: count(),
});
export type HistoryPage = z.infer<typeof historyPageSchema>;
