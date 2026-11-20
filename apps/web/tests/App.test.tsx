import { render, screen } from "@testing-library/react";

import { App } from "../src/app/App";

describe("App", () => {
  it("affiche le nom et l'avertissement réseau de confiance", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "LocalDrop" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/réseau de confiance/);
  });
});
