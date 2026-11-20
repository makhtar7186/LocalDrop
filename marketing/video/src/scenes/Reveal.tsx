// Raccord graphique : le trajet direct (ligne horizontale) pivote et devient la flèche du logo.
import React from "react";
import { C, EASE, FONT, S, W, lerp, p } from "../lib";
import { Logo } from "../ui";
import { DIRECT, DIRECT_CAM } from "./Detour";
import { LOGO_TARGET } from "./Product";

export const HANDOFF = S("reveal") + 0.1; // la scène du détour cède la place ici

const SIZE = 230;
const UNIT = SIZE / 32;

export const Reveal: React.FC<{ t: number }> = ({ t }) => {
  if (t < HANDOFF - 0.05 || t > S("pair") + 0.6) return null;
  const morph = p(t, HANDOFF, 0.6, EASE.inOut);
  const sq = p(t, HANDOFF + 0.32, 0.6, EASE.stamp);
  const head = p(t, HANDOFF + 0.5, 0.35);
  const base = p(t, HANDOFF + 0.62, 0.35);
  const word = p(t, W("reveal", "localdrop") - 0.1, 0.8);
  const slide = p(t, W("reveal", "localdrop") - 0.2, 0.9, EASE.inOut);
  // envol vers l'icône de la barre de titre de l'application
  const fly = p(t, S("pair") - 0.55, 0.85, EASE.inOut);

  const cx0 = 960;
  const cx1 = 420;
  const lx = lerp(lerp(cx0, cx1, slide), LOGO_TARGET.x, fly);
  const ly = lerp(540, LOGO_TARGET.y, fly);
  const ls = lerp(1, LOGO_TARGET.size / SIZE, fly);

  // ligne : longueur et angle du trajet direct → tige de la flèche (y 7→20 dans le logo)
  const len0 = (DIRECT.x2 - DIRECT.x1) * DIRECT_CAM.s;
  const len1 = 13 * UNIT;
  const lineLen = lerp(len0, len1, morph);
  const angle = lerp(0, 90, morph);
  const lineCy = lerp(540, 540 + (13.5 - 16) * UNIT, morph);

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {morph < 1 && (
        <div
          style={{
            position: "absolute",
            left: 960 - lineLen / 2,
            top: lineCy - 3,
            width: lineLen,
            height: 6,
            borderRadius: 3,
            background: morph > 0.6 ? "#fff" : C.accent,
            boxShadow: "0 0 18px rgba(79,140,255,0.9)",
            transform: `rotate(${angle}deg)`,
          }}
        />
      )}
      <div
        style={{
          position: "absolute",
          left: lx - SIZE / 2,
          top: ly - SIZE / 2,
          transform: `scale(${ls})`,
          filter: `drop-shadow(0 30px 60px rgba(79,140,255,${0.35 * (1 - fly)}))`,
        }}
      >
        <Logo size={SIZE} square={sq} stem={morph >= 1 ? 1 : 0} head={head} base={base} />
      </div>
      <div
        style={{
          position: "absolute",
          left: cx1 + SIZE / 2 + 50,
          top: 540 - 95,
          height: 190,
          display: "flex",
          alignItems: "center",
          overflow: "hidden",
          opacity: 1 - p(t, S("pair") - 0.6, 0.35, EASE.in),
          clipPath: `inset(0 ${100 - word * 100}% 0 0)`,
        }}
      >
        <span style={{ fontFamily: FONT.display, fontWeight: 700, fontSize: 150, letterSpacing: -6, color: C.text, transform: `translateX(${(1 - word) * -60}px)` }}>
          Local<span style={{ color: C.accent }}>Drop</span>
        </span>
      </div>
    </div>
  );
};
