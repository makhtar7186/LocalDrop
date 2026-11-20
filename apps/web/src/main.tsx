import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { consumeJoinFragment } from "./features/pairing/joinLink";
import "./styles/index.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Élément #root introuvable");
}

// Lu une seule fois, hors de React : le secret est effacé de l'URL avant tout rendu.
const joinParams = consumeJoinFragment();

createRoot(root).render(
  <StrictMode>
    <App joinParams={joinParams} />
  </StrictMode>,
);
