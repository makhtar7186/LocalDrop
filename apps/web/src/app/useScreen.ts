import { useCallback, useEffect, useState } from "react";

// Navigation par hash (§14.3) : « #/envoyer »… Le bouton Retour du téléphone fonctionne
// et le serveur statique reste trivial. Le fragment d'appairage (#/join?…) est consommé
// avant le rendu (main.tsx) et n'arrive jamais ici.

export const SCREENS = ["accueil", "envoyer", "recevoir", "historique"] as const;
export type Screen = (typeof SCREENS)[number];

export function screenFromHash(hash: string): Screen {
  const name = hash.replace(/^#\/?/, "").split(/[?/]/, 1)[0] ?? "";
  return (SCREENS as readonly string[]).includes(name) ? (name as Screen) : "accueil";
}

export function useScreen(): [Screen, (screen: Screen) => void] {
  const [screen, setScreen] = useState<Screen>(() => screenFromHash(window.location.hash));

  useEffect(() => {
    const onHashChange = () => setScreen(screenFromHash(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = useCallback((next: Screen) => {
    const hash = next === "accueil" ? "#/" : `#/${next}`;
    if (window.location.hash !== hash) window.location.hash = hash; // entrée d'historique
    setScreen(next);
  }, []);

  return [screen, navigate];
}
