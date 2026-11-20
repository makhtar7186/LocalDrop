import { Component, type ErrorInfo, type ReactNode } from "react";

import { messages } from "./messages";

interface State {
  failed: boolean;
}

/** Une erreur de rendu inattendue affiche un écran de secours, jamais une page blanche. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  override state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Erreur d'interface", error, info.componentStack);
  }

  override render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <main role="alert" className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 px-4">
        <h1 className="text-xl font-semibold">{messages.crashTitle}</h1>
        <p className="text-text-muted">{messages.crashText}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="min-h-12 rounded-lg bg-accent px-4 font-medium text-white"
        >
          {messages.crashReload}
        </button>
      </main>
    );
  }
}
