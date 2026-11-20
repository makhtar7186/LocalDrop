import { render, screen } from "@testing-library/react";

import { App } from "../src/app/App";
import type { PairingApi } from "../src/services/api";
import { FakeRealtime } from "./fakes";

const idleApi: PairingApi = {
  join: () => Promise.reject(new Error("non utilisé")),
  status: () => Promise.reject(new Error("non utilisé")),
};

describe("App", () => {
  it("affiche le nom et l'avertissement réseau de confiance", () => {
    window.localStorage.clear();
    render(<App realtime={new FakeRealtime()} pairing={{ api: idleApi }} />);
    expect(screen.getByRole("heading", { name: "LocalDrop" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/réseau de confiance/);
  });
});
