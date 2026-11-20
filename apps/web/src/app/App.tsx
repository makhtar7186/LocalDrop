import { messages } from "./messages";

export function App() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col gap-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold">{messages.appName}</h1>
        <p className="text-text-muted">{messages.tagline}</p>
      </header>

      <p className="rounded-lg border border-border bg-surface-raised p-4">{messages.notPaired}</p>

      <p role="note" className="mt-auto text-sm text-warning">
        {messages.trustedNetworkWarning}
      </p>
    </main>
  );
}
