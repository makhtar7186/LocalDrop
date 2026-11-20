import { z } from "zod";

// Contrats de l'API v1 : toute réponse est validée avant usage.

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
  device_token: z.string().min(1),
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
  size: z.number().int().nonnegative(),
  chunk_size: z.number().int().positive(),
  total_chunks: z.number().int().nonnegative(),
  status: transferStatusSchema,
  received_bytes: z.number().int().nonnegative(),
  sha256: z.string().nullable(),
  error_code: z.string().nullable(),
  fully_served: z.boolean(),
  created_at: z.string(),
});
export type Transfer = z.infer<typeof transferSchema>;

export const chunkAckSchema = z.object({
  index: z.number().int().nonnegative(),
  already_received: z.boolean(),
  received_bytes: z.number().int().nonnegative(),
  status: transferStatusSchema,
});
export type ChunkAck = z.infer<typeof chunkAckSchema>;

export const chunkListSchema = z.object({
  transfer_id: z.string(),
  total_chunks: z.number().int().nonnegative(),
  received: z.array(z.number().int().nonnegative()),
});

export const downloadTicketSchema = z.object({
  url: z.string().startsWith("/api/v1/transfers/"),
  expires_at: z.string(),
});
export type DownloadTicket = z.infer<typeof downloadTicketSchema>;

export const historyPageSchema = z.object({
  items: z.array(transferSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});
export type HistoryPage = z.infer<typeof historyPageSchema>;
