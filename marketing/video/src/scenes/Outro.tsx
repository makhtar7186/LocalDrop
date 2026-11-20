// Fin : logo, nom, promesse en deux temps, rappel des atouts. Tenu assez longtemps pour être lu.
import React from "react";
import { C, EASE, FONT, S, STAGGER, TOTAL, W, p } from "../lib";
import { Chip, Logo } from "../ui";

const FACTS = ["Wi-Fi local", "Sans compte", "Sans cloud", "Windows · Android · iPhone"];

export const Outro: React.FC<{ t: number }> = ({ t }) => {
  const t0 = S("outro") - 0.35;
  if (t < t0) return null;
  const sq = p(t, t0, 0.6, EASE.stamp);
  const stem = p(t, t0 + 0.25, 0.35);
  const head = p(t, t0 + 0.45, 0.35);
  const base = p(t, t0 + 0.6, 0.3);
  const name = p(t, W("outro", "localdrop") - 0.05, 0.7);
  const l1 = p(t, W("outro", "tes") - 0.1, 0.6);
  const l2 = p(t, W("outro", "intacts") - 0.25, 0.6);
  const end = p(t, TOTAL - 0.7, 0.7, EASE.in);
  return (
    <div style={{ position: "absolute", inset: 0, opacity: 1 - end }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: 190, display: "flex", justifyContent: "center", alignItems: "center", gap: 44 }}>
        <div style={{ filter: "drop-shadow(0 30px 60px rgba(79,140,255,0.45))" }}>
          <Logo size={170} square={sq} stem={stem} head={head} base={base} />
        </div>
        <div style={{ overflow: "hidden", clipPath: `inset(0 ${100 - name * 100}% 0 0)` }}>
          <span style={{ fontFamily: FONT.display, fontWeight: 700, fontSize: 124, letterSpacing: -5, color: C.text }}>
            Local<span style={{ color: C.accent }}>Drop</span>
          </span>
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 470, textAlign: "center", fontFamily: FONT.display, fontWeight: 500, fontSize: 60, lineHeight: 1.25, letterSpacing: -1.5 }}>
        <div style={{ opacity: l1, transform: `translateY(${(1 - l1) * 30}px)`, color: C.text }}>Tes fichiers restent chez toi.</div>
        <div style={{ opacity: l2, transform: `translateY(${(1 - l2) * 30}px)`, color: C.success, fontWeight: 700 }}>Et restent intacts.</div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 720, display: "flex", justifyContent: "center", gap: 18 }}>
        {FACTS.map((f, i) => {
          const k = p(t, W("outro", "intacts") + 0.5 + i * STAGGER * 2, 0.6);
          return (
            <div key={f} style={{ opacity: k, transform: `translateY(${(1 - k) * 20}px)` }}>
              <Chip size={26} color={C.muted}>
                {f}
              </Chip>
            </div>
          );
        })}
      </div>
    </div>
  );
};
