import { messages } from "../../app/messages";
import type { Screen } from "../../app/useScreen";

export interface HomeScreenProps {
  serverName: string;
  sendActivity: number;
  receiveWaiting: number;
  onNavigate: (screen: Screen) => void;
}

/** Accueil (§14.3) : nom du PC, état de connexion, actions Envoyer et Recevoir. */
export function HomeScreen({ serverName, sendActivity, receiveWaiting, onNavigate }: HomeScreenProps) {
  return (
    <section className="flex flex-col gap-4" aria-labelledby="accueil-title">
      <h2 id="accueil-title" tabIndex={-1} className="sr-only">
        {messages.homeTitle}
      </h2>
      <p className="text-text-muted">{messages.homeConnectedTo(serverName)}</p>

      <button
        type="button"
        onClick={() => onNavigate("envoyer")}
        className="flex min-h-20 flex-col items-start justify-center rounded-xl bg-accent px-5 text-left text-white"
      >
        <span className="text-lg font-semibold">↑ {messages.homeSendAction}</span>
        {sendActivity > 0 && (
          <span className="text-sm opacity-90">{messages.homeSendActive(sendActivity)}</span>
        )}
      </button>

      <button
        type="button"
        onClick={() => onNavigate("recevoir")}
        className={`flex min-h-20 flex-col items-start justify-center rounded-xl border px-5 text-left ${
          receiveWaiting > 0 ? "border-warning" : "border-border"
        } bg-surface-raised`}
      >
        <span className="text-lg font-semibold">↓ {messages.homeReceiveAction}</span>
        {receiveWaiting > 0 && (
          <span className="text-sm text-warning">{messages.homeReceiveWaiting(receiveWaiting)}</span>
        )}
      </button>
    </section>
  );
}
