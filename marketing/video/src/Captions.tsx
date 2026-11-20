// Sous-titres incrustés, mot prononcé mis en avant (vidéo compréhensible sans le son).
import React from "react";
import { C, FONT, LINES, type LineKey, p } from "./lib";

// répliques déjà affichées à l'écran en grand : pas de doublon
const HIDDEN: LineKey[] = ["twist", "reveal", "outro"];

export const Captions: React.FC<{ t: number }> = ({ t }) => {
  const entry = (Object.entries(LINES) as Array<[LineKey, (typeof LINES)[LineKey]]>).find(
    ([, l]) => t >= l.start - 0.15 && t <= l.start + l.dur + 0.25,
  );
  if (!entry || HIDDEN.includes(entry[0])) return null;
  const [, line] = entry;
  const k = p(t, line.start - 0.15, 0.25) * (1 - p(t, line.start + line.dur + 0.05, 0.2));
  // découpe du texte d'origine (ponctuation incluse) calée sur les mots horodatés
  const tokens = line.text.split(/\s+/);
  let wi = 0;
  const timed = tokens.map((tok) => {
    const clean = tok.replace(/[.,:;!?…«»]/g, "");
    if (!clean) return { tok, at: -1 };
    const w = line.words[wi];
    if (w && clean.toLowerCase().startsWith(w.w.toLowerCase().slice(0, 2))) {
      wi++;
      return { tok, at: line.start + w.t };
    }
    return { tok, at: -1 };
  });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 56, display: "flex", justifyContent: "center", opacity: k }}>
      <div
        style={{
          maxWidth: 1500,
          padding: "14px 30px",
          borderRadius: 18,
          background: "rgba(8,10,14,0.72)",
          backdropFilter: "blur(6px)",
          textAlign: "center",
          fontFamily: FONT.body,
          fontWeight: 500,
          fontSize: 40,
          lineHeight: 1.3,
        }}
      >
        {timed.map(({ tok, at }, i) => {
          const spoken = at < 0 ? true : t >= at;
          return (
            <span key={i} style={{ color: spoken ? C.text : "rgba(230,232,236,0.4)" }}>
              {tok}
              {i < timed.length - 1 ? " " : ""}
            </span>
          );
        })}
      </div>
    </div>
  );
};
