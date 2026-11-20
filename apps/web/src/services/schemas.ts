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
