// Preuve : même taille, même empreinte SHA-256, au pixel près (loupes nettes, cf. la loupe floue du détour).
import React from "react";
import { C, EASE, FONT, S, W, lerp, p } from "../lib";
import { Photo, WINDOWS_CROP } from "../Photo";
import { IconCheck } from "../ui";

const HASH = "9f2c81ab4e07d3c5a1b86f20e9d4c37b51fa08e6c2d9b34710ae5f86c3d2e4d0";
const IN = S("proof") - 0.4;
const OUT = S("both") - 0.6;

const PH_W = 560;
const PH_H = 420;

const Row: React.FC<{ label: string; value: React.ReactNode; hl: number; mono?: boolean }> = ({ label, value, hl, mono }) => (
  <div
    style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 16,
      padding: "10px 14px",
      borderRadius: 10,
      background: `rgba(60,207,142,${0.14 * hl})`,
      boxShadow: `inset 0 0 0 2px rgba(60,207,142,${0.8 * hl})`,
    }}
  >
    <span style={{ width: 120, flexShrink: 0, color: C.muted, fontFamily: FONT.body, fontSize: 22 }}>{label}</span>
    <span style={{ fontFamily: mono ? FONT.mono : FONT.body, fontSize: mono ? 19 : 22, color: C.text, lineHeight: 1.35, wordBreak: "break-all" }}>{value}</span>
    <span style={{ marginLeft: "auto", opacity: hl }}>
      <IconCheck size={28} color={C.success} sw={2.8} progress={hl} />
    </span>
  </div>
);

const Side: React.FC<{ t: number; title: string; delay: number; dir: number }> = ({ t, title, delay, dir }) => {
  const k = p(t, IN + delay, 0.8);
  const out = p(t, OUT, 0.55, EASE.in);
  const sizeHl = p(t, W("proof", "taille") - 0.1, 0.4);
  const hashScan = p(t, W("proof", "empreinte") - 0.15, 0.9, EASE.inOut);
  const pixel = p(t, W("proof", "pixel") - 0.15, 0.5, EASE.stamp);
  const shown = Math.round(hashScan * 64);
  return (
    <div
      style={{
        width: 760,
        padding: 26,
        borderRadius: 26,
        background: C.raised,
        border: `1.5px solid ${C.border}`,
        boxShadow: "0 40px 80px rgba(0,0,0,0.45)",
        opacity: k * (1 - out),
        transform: `translateY(${(1 - k) * 80 + out * 40}px) translateX(${out * dir * 120}px)`,
        position: "relative",
      }}
    >
      <div style={{ fontFamily: FONT.display, fontWeight: 700, fontSize: 30, color: C.text, marginBottom: 18 }}>{title}</div>
      <div style={{ display: "flex", justifyContent: "center", position: "relative" }}>
        <Photo w={PH_W} h={PH_H} radius={10} density={1.6} />
        {/* loupe nette sur les fenêtres */}
        <div
          style={{
            position: "absolute",
            left: 100 + WINDOWS_CROP.x * PH_W - 30,
            top: WINDOWS_CROP.y * PH_H - 90,
            transform: `scale(${pixel})`,
            opacity: Math.min(1, pixel * 2),
            width: 170,
            height: 170,
            borderRadius: 999,
            overflow: "hidden",
            border: `5px solid ${C.success}`,
            boxShadow: "0 20px 40px rgba(0,0,0,0.6)",
          }}
        >
          <Photo w={170} h={170} crop={{ ...WINDOWS_CROP, w: WINDOWS_CROP.h * 0.75, h: WINDOWS_CROP.h }} density={1.4} />
        </div>
      </div>
      <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 4 }}>
        <Row label="Dimensions" value="4032 × 3024" hl={sizeHl} />
        <Row label="Taille" value="4 812 337 octets" hl={sizeHl} />
        <Row
          label="SHA-256"
          mono
          hl={p(t, W("proof", "empreinte") + 0.7, 0.3)}
          value={
            <>
              <span style={{ color: C.success }}>{HASH.slice(0, shown)}</span>
              <span>{HASH.slice(shown)}</span>
            </>
          }
        />
      </div>
    </div>
  );
};

export const Proof: React.FC<{ t: number }> = ({ t }) => {
  if (t < IN - 0.05 || t > OUT + 0.7) return null;
  const eq = p(t, W("proof", "pixel") + 0.1, 0.5, EASE.stamp) * (1 - p(t, OUT, 0.4, EASE.in));
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", top: 110, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 120 }}>
        <Side t={t} title="Sur le téléphone" delay={0} dir={-1} />
        <Side t={t} title="Sur le PC" delay={0.08} dir={1} />
      </div>
      <div
        style={{
          position: "absolute",
          left: 960 - 95,
          top: 400,
          width: 190,
          height: 190,
          borderRadius: 999,
          background: C.success,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          transform: `scale(${eq}) rotate(${lerp(-12, 0, eq)}deg)`,
          boxShadow: "0 0 0 10px rgba(60,207,142,0.25), 0 30px 60px rgba(0,0,0,0.5)",
          color: "#06140d",
          fontFamily: FONT.display,
          fontWeight: 700,
        }}
      >
        <div style={{ fontSize: 80, lineHeight: 1 }}>=</div>
        <div style={{ fontSize: 22 }}>Identique</div>
      </div>
    </div>
  );
};

export const PROOF_WINDOW = { IN, OUT };
