import { useEffect, useState } from "react";

import type { RealtimeConnection, RealtimeEvent } from "../services/realtime";

/**
 * Compteur incrémenté à chaque événement pertinent (et à chaque reconnexion) :
 * l'utiliser comme dépendance d'un effet pour relire l'état par REST sans attendre.
 */
export function useRealtimeNudge(
  realtime: RealtimeConnection | undefined,
  isRelevant: (event: RealtimeEvent) => boolean,
): number {
  const [nudge, setNudge] = useState(0);

  useEffect(() => {
    if (!realtime) return;
    const bump = () => setNudge((n) => n + 1);
    return realtime.subscribe({
      onReady: bump,
      onUnauthorized: bump,
      onEvent: (event) => {
        if (isRelevant(event)) bump();
      },
    });
  }, [realtime, isRelevant]);

  return nudge;
}
