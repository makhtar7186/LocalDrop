import { messages } from "../app/messages";
import type { Screen } from "../app/useScreen";

export interface BottomNavProps {
  current: Screen;
  onNavigate: (screen: Screen) => void;
  badges: Partial<Record<Screen, number>>;
}

const ITEMS: ReadonlyArray<{
  screen: Screen;
  label: string;
  icon: string;
  badgeLabel?: (count: number) => string;
}> = [
  { screen: "accueil", label: messages.navHome, icon: "⌂" },
  { screen: "envoyer", label: messages.navSend, icon: "↑", badgeLabel: messages.badgeSend },
  { screen: "recevoir", label: messages.navReceive, icon: "↓", badgeLabel: messages.badgeReceive },
  { screen: "historique", label: messages.navHistory, icon: "≡" },
];

/** Barre de navigation fixe en bas d'écran (zone du pouce), au-dessus de la barre iOS. */
export function BottomNav({ current, onNavigate, badges }: BottomNavProps) {
  return (
    <nav
      aria-label={messages.navLabel}
      className="fixed inset-x-0 bottom-0 z-10 border-t border-border bg-surface-raised pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="mx-auto flex max-w-md">
        {ITEMS.map(({ screen, label, icon, badgeLabel }) => {
          const active = screen === current;
          const badge = badges[screen] ?? 0;
          return (
            <li key={screen} className="flex-1">
              <button
                type="button"
                onClick={() => onNavigate(screen)}
                aria-current={active ? "page" : undefined}
                className={`relative flex min-h-14 w-full flex-col items-center justify-center gap-0.5 text-xs ${
                  active ? "text-accent" : "text-text-muted"
                }`}
              >
                <span aria-hidden="true" className="text-lg leading-none">
                  {icon}
                </span>
                {label}
                {badge > 0 && (
                  <span
                    className="absolute top-1.5 right-1/4 min-w-5 rounded-full bg-warning px-1 text-center text-[11px] font-semibold text-surface"
                    aria-label={badgeLabel ? badgeLabel(badge) : String(badge)}
                  >
                    {badge}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
