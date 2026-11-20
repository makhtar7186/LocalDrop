// Démo produit : appairage, transfert bloc par bloc, sens inverse. Téléphone à gauche, PC à
// droite (même orientation que le détour), interfaces fidèles aux vrais libellés de l'app.
import React from "react";
import { C, E, EASE, FONT, S, W, lerp, p, win } from "../lib";
import { Photo } from "../Photo";
import {
  Chip,
  IconApp,
  IconCheck,
  IconCloud,
  IconDoc,
  IconUser,
  IconWifi,
  IconX,
  Laptop,
  Logo,
  MobileHeader,
  Phone,
  QR,
  Spinner,
} from "../ui";

// ------------------------------------------------------------------ dimensions fixes
const PW = 300; // téléphone
const PSCR = { x: PW * 0.035, y: PW * 0.035, w: PW * 0.93 }; // écran dans le téléphone
const LW = 900; // écran du PC
const LH = LW * 0.625;
const LSCR = { x: (LW * 1.16 - (LW + LW * 0.044)) / 2 + LW * 0.022, y: LW * 0.022 };

// ------------------------------------------------------------------ instants
const T = {
  enter: S("pair") - 0.55,
  scanAim: W("pair", "scannes") - 0.25,
  scanOK: W("pair", "telephone") + 0.15,
  get click() {
    return this.scanOK + 0.75;
  },
  get connected() {
    return this.click + 0.15;
  },
  toTransfer: S("transfer") - 0.65,
  tiles: W("transfer", "directement"),
  verify: W("transfer", "verifie"),
  toProof: S("proof") - 0.5,
  toBoth: S("both") - 0.55,
  doc: W("both", "pc"),
  toOutro: S("outro") - 0.45,
};
const TILE_COLS = 4;
const TILE_ROWS = 3;
const TILE_N = TILE_COLS * TILE_ROWS;
const TILE_GAP = 0.19;
const TILE_DUR = 0.7;
const tileStart = (i: number) => T.tiles + i * TILE_GAP;

// ------------------------------------------------------------------ mise en page (keyframes)
type Box = { x: number; y: number; s: number; o: number };
type Layout = { phone: Box; pc: Box };
const L0: Layout = { phone: { x: 190, y: 225, s: 1, o: 1 }, pc: { x: 660, y: 200, s: 1, o: 1 } };
const L1: Layout = { phone: { x: 240, y: 250, s: 0.94, o: 1 }, pc: { x: 780, y: 232, s: 0.9, o: 1 } };
const LOUT: Layout = { phone: { x: -420, y: 260, s: 0.9, o: 0 }, pc: { x: 2050, y: 232, s: 0.9, o: 0 } };
const LDOWN: Layout = { phone: { x: 240, y: 420, s: 0.94, o: 0 }, pc: { x: 780, y: 400, s: 0.9, o: 0 } };

const mixBox = (a: Box, b: Box, k: number): Box => ({ x: lerp(a.x, b.x, k), y: lerp(a.y, b.y, k), s: lerp(a.s, b.s, k), o: lerp(a.o, b.o, k) });
const mixLayout = (a: Layout, b: Layout, k: number): Layout => ({ phone: mixBox(a.phone, b.phone, k), pc: mixBox(a.pc, b.pc, k) });

const layoutAt = (t: number): Layout => {
  const enter = p(t, T.enter, 0.9);
  let l: Layout = {
    phone: { ...L0.phone, x: L0.phone.x - 220 * (1 - enter), o: enter },
    pc: { ...L0.pc, y: L0.pc.y + 120 * (1 - enter), o: enter },
  };
  l = mixLayout(l, L1, p(t, T.toTransfer, 0.9, EASE.inOut));
  l = mixLayout(l, LOUT, p(t, T.toProof, 0.8, EASE.inOut));
  l = mixLayout(l, L1, p(t, T.toBoth, 0.9, EASE.inOut));
  l = mixLayout(l, LDOWN, p(t, T.toOutro, 0.6, EASE.in));
  return l;
};

/** Centre de l'icône de la barre de titre de l'app : le logo de la révélation y atterrit. */
export const LOGO_TARGET = { x: L0.pc.x + LSCR.x + 25, y: L0.pc.y + LSCR.y + 17, size: 22 };

// ------------------------------------------------------------------ PC : application desktop
const NAV = ["Tableau de bord", "Transferts", "Historique", "Paramètres"];

const Desktop: React.FC<{ t: number }> = ({ t }) => {
  const view = t < T.toTransfer + 0.4 ? "dash" : t < T.toBoth + 0.4 ? "transfers" : "send";
  const active = view === "dash" ? 0 : 1;
  return (
    <div style={{ position: "absolute", inset: 0, background: C.surface, fontFamily: FONT.body, color: C.text }}>
      <div style={{ height: 34, display: "flex", alignItems: "center", gap: 8, padding: "0 14px", background: "#0b0d11", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ width: 22, height: 22, opacity: t > S("pair") - 0.1 ? 1 : 0 }}>
          <Logo size={22} />
        </div>
        <span style={{ fontSize: 15, color: C.muted }}>LocalDrop</span>
        <span style={{ marginLeft: "auto", color: C.muted, letterSpacing: 14, fontSize: 14 }}>— ▢ ✕</span>
      </div>
      <div style={{ display: "flex", height: LH - 34 }}>
        <div style={{ width: 190, borderRight: `1px solid ${C.border}`, padding: "18px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
          {NAV.map((n, i) => (
            <div
              key={n}
              style={{
                padding: "10px 12px",
                borderRadius: 8,
                fontSize: 17,
                background: i === active ? "rgba(79,140,255,0.16)" : "transparent",
                color: i === active ? C.text : C.muted,
              }}
            >
              {n}
            </div>
          ))}
        </div>
        <div style={{ flex: 1, padding: 24, position: "relative" }}>
          {view === "dash" && <Dashboard t={t} />}
          {view === "transfers" && <Receiving t={t} />}
          {view === "send" && <SendToPhone t={t} />}
        </div>
      </div>
    </div>
  );
};

const Card: React.FC<{ title: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ title, children, style }) => (
  <div style={{ background: C.raised, border: `1px solid ${C.border}`, borderRadius: 14, padding: 18, ...style }}>
    <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 12 }}>{title}</div>
    {children}
  </div>
);

const Button: React.FC<{ children: React.ReactNode; primary?: boolean; press?: number; style?: React.CSSProperties }> = ({ children, primary, press = 0, style }) => (
  <div
    style={{
      padding: "9px 18px",
      borderRadius: 9,
      fontSize: 16,
      fontWeight: 700,
      background: primary ? C.accent : "transparent",
      border: primary ? "none" : `1px solid ${C.border}`,
      color: primary ? "#fff" : C.muted,
      transform: `scale(${1 - 0.08 * press})`,
      ...style,
    }}
  >
    {children}
  </div>
);

const Dashboard: React.FC<{ t: number }> = ({ t }) => {
  const pulse = win(t, W("pair", "pc") - 0.1, T.scanOK, 0.4, 0.4);
  const newDev = p(t, T.scanOK + 0.1, 0.45, EASE.stamp);
  const press = win(t, T.click - 0.06, T.click + 0.06, 0.08, 0.15);
  const ok = t >= T.connected;
  // curseur
  const cur = p(t, T.scanOK + 0.25, 0.5, EASE.inOut);
  const cx = lerp(560, 405, cur);
  const cy = lerp(470, 212, cur);
  const curO = win(t, T.scanOK + 0.15, T.connected + 0.8, 0.2, 0.3);
  return (
    <>
      <div style={{ fontSize: 26, fontWeight: 700, marginBottom: 18 }}>Tableau de bord</div>
      <div style={{ display: "flex", gap: 18 }}>
        <Card title="QR Code d'appairage" style={{ width: 290 }}>
          <div style={{ display: "flex", justifyContent: "center", transform: `scale(${1 + 0.05 * pulse})`, filter: `drop-shadow(0 0 ${22 * pulse}px rgba(79,140,255,0.9))` }}>
            <QR size={200} reveal={p(t, T.enter + 0.3, 0.8) * 1.05} />
          </div>
          <div style={{ fontSize: 13.5, color: C.muted, marginTop: 12, lineHeight: 1.35 }}>Scannez ce QR Code avec l'appareil photo du téléphone.</div>
          <div style={{ fontFamily: FONT.mono, fontSize: 13, marginTop: 10, color: C.accent }}>http://192.168.1.14:8765</div>
        </Card>
        <Card title="Appareils" style={{ flex: 1 }}>
          {t < T.scanOK + 0.1 && <div style={{ color: C.muted, fontSize: 15 }}>Aucun téléphone ne s'est encore connecté</div>}
          {t >= T.scanOK + 0.1 && (
            <div
              style={{
                transform: `scale(${newDev})`,
                transformOrigin: "left top",
                border: `1px solid ${ok ? C.border : C.warning}`,
                borderRadius: 12,
                padding: 14,
                background: ok ? "transparent" : "rgba(245,184,74,0.08)",
              }}
            >
              {!ok && <div style={{ fontSize: 13, fontWeight: 700, color: C.warning, marginBottom: 6 }}>Nouvel appareil</div>}
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <IconUser size={22} color={C.muted} />
                <span style={{ fontSize: 17 }}>Téléphone Android</span>
                {ok && (
                  <span style={{ marginLeft: "auto", color: C.success, fontWeight: 700, fontSize: 15, display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 9, background: C.success }} /> Connecté
                  </span>
                )}
              </div>
              {!ok && (
                <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                  <Button primary press={press}>
                    Autoriser
                  </Button>
                  <Button>Refuser</Button>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
      {curO > 0 && (
        <svg width={30} height={30} viewBox="0 0 24 24" style={{ position: "absolute", left: cx, top: cy, opacity: curO, filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.6))" }}>
          <path d="M4 2l15 9.5-6.6 1.4L9 20z" fill="#fff" stroke="#000" strokeWidth={1.2} />
        </svg>
      )}
      {press > 0 && (
        <div
          style={{
            position: "absolute",
            left: 405 - 30,
            top: 212 - 30,
            width: 60,
            height: 60,
            borderRadius: 60,
            border: `3px solid ${C.accent}`,
            opacity: 1 - p(t, T.click, 0.4),
            transform: `scale(${0.4 + p(t, T.click, 0.4)})`,
          }}
        />
      )}
    </>
  );
};

// zone d'arrivée des blocs (coordonnées dans l'écran du PC)
const DEST = { x: 190 + 24, y: 34 + 64, w: 440, h: 330 };

const Receiving: React.FC<{ t: number }> = ({ t }) => {
  const landed = Array.from({ length: TILE_N }, (_, i) => t >= tileStart(i) + TILE_DUR).filter(Boolean).length;
  const verified = p(t, T.verify - 0.1, 0.5);
  const pct = Math.round((landed / TILE_N) * 100);
  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 14 }}>
        <div style={{ fontSize: 26, fontWeight: 700 }}>Transferts</div>
        <div style={{ fontSize: 15, color: C.muted }}>Réception · photo.jpg</div>
      </div>
      <div style={{ position: "absolute", left: DEST.x - 190, top: DEST.y - 34, width: DEST.w, height: DEST.h }}>
        <div style={{ position: "absolute", inset: 0, border: `1.5px dashed ${C.border}`, borderRadius: 6 }} />
        {Array.from({ length: TILE_N }, (_, i) => {
          if (t < tileStart(i) + TILE_DUR) return null;
          const col = i % TILE_COLS;
          const row = Math.floor(i / TILE_COLS);
          const tw = DEST.w / TILE_COLS;
          const th = DEST.h / TILE_ROWS;
          const flash = 1 - p(t, tileStart(i) + TILE_DUR, 0.5);
          return (
            <div key={i} style={{ position: "absolute", left: col * tw, top: row * th }}>
              <Photo w={tw} h={th} crop={{ x: col / TILE_COLS, y: row / TILE_ROWS, w: 1 / TILE_COLS, h: 1 / TILE_ROWS }} density={1.6} />
              <div style={{ position: "absolute", inset: 0, boxShadow: `inset 0 0 0 2px rgba(60,207,142,${flash})` }} />
            </div>
          );
        })}
        {verified > 0 && (
          <div
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              transform: `translate(-50%,-50%) scale(${lerp(0.6, 1, verified)})`,
              opacity: verified,
              background: "rgba(15,17,21,0.88)",
              border: `2px solid ${C.success}`,
              borderRadius: 16,
              padding: "14px 22px",
              display: "flex",
              alignItems: "center",
              gap: 12,
              color: C.success,
              fontSize: 22,
              fontWeight: 700,
            }}
          >
            <IconCheck size={34} color={C.success} sw={2.6} progress={p(t, T.verify, 0.5)} /> Intégrité vérifiée
          </div>
        )}
      </div>
      <div style={{ position: "absolute", right: 24, top: 82, width: 170, fontSize: 14, color: C.muted, lineHeight: 1.9 }}>
        <div>Progression</div>
        <div style={{ height: 8, borderRadius: 8, background: C.border, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: verified > 0 ? C.success : C.accent }} />
        </div>
        <div style={{ fontFamily: FONT.mono, color: C.text, fontSize: 22, marginTop: 6 }}>{pct} %</div>
        <div style={{ fontFamily: FONT.mono }}>
          bloc {Math.min(TILE_N, landed)} / {TILE_N}
        </div>
        <div style={{ fontFamily: FONT.mono, color: landed ? C.success : C.muted }}>SHA-256 ✓</div>
      </div>
    </>
  );
};

const SendToPhone: React.FC<{ t: number }> = ({ t }) => {
  const docGone = t > T.doc - 0.1;
  const done = t > T.doc + 1.25;
  return (
    <>
      <div style={{ fontSize: 26, fontWeight: 700, marginBottom: 14 }}>Transferts</div>
      <div
        style={{
          height: 200,
          border: `2px dashed ${C.accent}`,
          borderRadius: 14,
          background: "rgba(79,140,255,0.07)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 12,
          color: C.muted,
          fontSize: 16,
        }}
      >
        <div style={{ opacity: docGone ? 0.25 : 1 }}>
          <IconDoc size={64} color={C.accent} sw={1.5} />
        </div>
        Glissez des fichiers ici pour les envoyer au téléphone
      </div>
      <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 12, padding: 14, border: `1px solid ${C.border}`, borderRadius: 12, fontSize: 16 }}>
        <IconDoc size={22} color={C.muted} />
        Rapport.pdf
        <span style={{ color: C.muted }}>PC → téléphone</span>
        <span style={{ marginLeft: "auto", color: done ? C.success : C.warning, fontWeight: 700 }}>{done ? "Terminé ✓" : "Proposé au téléphone"}</span>
      </div>
    </>
  );
};

// ------------------------------------------------------------------ téléphone : page mobile
// zone photo (source des blocs) dans l'écran du téléphone
const SRC = { x: 16, y: 150, w: PSCR.w - 32, h: ((PSCR.w - 32) * 3) / 4 };

const Mobile: React.FC<{ t: number }> = ({ t }) => {
  const sw = PSCR.w;
  if (t < T.scanOK) {
    const aim = p(t, T.scanAim, 0.5);
    const sweep = ((t - T.scanAim) / 0.9) % 1;
    return (
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 40% 30%, #2a2f3c, #07080b 75%)" }}>
        <div style={{ position: "absolute", left: 30, top: 140, width: 220, height: 160, background: "rgba(80,90,120,0.25)", filter: "blur(18px)", borderRadius: 30 }} />
        <div style={{ position: "absolute", left: (sw - 180) / 2, top: 180, opacity: aim, transform: `perspective(400px) rotateY(${lerp(18, 6, aim)}deg) scale(${lerp(0.7, 1, aim)})` }}>
          <QR size={180} />
        </div>
        <svg width={220} height={220} style={{ position: "absolute", left: (sw - 220) / 2, top: 160 }} fill="none" stroke="#fff" strokeWidth={5} strokeLinecap="round">
          <path d="M4 50V4h46M170 4h46v46M216 170v46h-46M50 216H4v-46" />
        </svg>
        {aim > 0 && <div style={{ position: "absolute", left: (sw - 200) / 2, top: 170 + 200 * sweep, width: 200, height: 3, background: C.accent, boxShadow: `0 0 14px ${C.accent}` }} />}
        <div style={{ position: "absolute", bottom: 70, width: "100%", textAlign: "center", color: "#fff", fontFamily: FONT.body, fontSize: 17 }}>Visez le QR Code</div>
      </div>
    );
  }
  const flash = 1 - p(t, T.scanOK, 0.35);
  const ok = t >= T.connected;
  const view = t < T.toTransfer + 0.4 ? "home" : t < T.toBoth + 0.4 ? "send" : "receive";
  return (
    <div style={{ position: "absolute", inset: 0, background: C.surface, fontFamily: FONT.body, color: C.text }}>
      <MobileHeader w={sw} />
      <div style={{ padding: "0 16px" }}>
        {view === "home" && (
          <>
            <div style={{ color: C.muted, fontSize: 14, marginBottom: 16 }}>Scanner, connecter, transférer.</div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: 14,
                borderRadius: 14,
                background: C.raised,
                border: `1px solid ${ok ? C.success : C.border}`,
                fontSize: 16,
                fontWeight: 500,
              }}
            >
              {ok ? <span style={{ width: 10, height: 10, borderRadius: 10, background: C.success }} /> : <Spinner size={20} t={t} />}
              {ok ? "Connecté" : "En attente d'autorisation"}
            </div>
            <div style={{ marginTop: 16, padding: 16, borderRadius: 14, background: C.raised, border: `1px solid ${C.border}`, opacity: ok ? 1 : 0.35 }}>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>Envoyer vers le PC</div>
              <div style={{ padding: "11px 0", textAlign: "center", borderRadius: 10, background: C.accent, color: "#fff", fontWeight: 700, fontSize: 15 }}>Choisir des fichiers</div>
            </div>
          </>
        )}
        {view === "send" && <MobileSend t={t} />}
        {view === "receive" && <MobileReceive t={t} />}
      </div>
      <div style={{ position: "absolute", inset: 0, background: "#fff", opacity: flash }} />
    </div>
  );
};

const MobileSend: React.FC<{ t: number }> = ({ t }) => {
  const landed = Array.from({ length: TILE_N }, (_, i) => t >= tileStart(i) + TILE_DUR).filter(Boolean).length;
  const status =
    t > T.verify + 0.45 ? "Reçu sur le PC ✓" : t > T.verify - 0.25 ? "Vérification de l'intégrité…" : landed ? `Envoi… ${Math.round((landed / TILE_N) * 100)} %` : "En attente…";
  const done = t > T.verify + 0.45;
  return (
    <>
      <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>Envoyer vers le PC</div>
      <div style={{ position: "absolute", left: SRC.x, top: SRC.y, width: SRC.w, height: SRC.h, border: `1.5px dashed ${C.border}`, borderRadius: 4 }}>
        {Array.from({ length: TILE_N }, (_, i) => {
          if (t >= tileStart(i)) return null;
          const col = i % TILE_COLS;
          const row = Math.floor(i / TILE_COLS);
          const tw = SRC.w / TILE_COLS;
          const th = SRC.h / TILE_ROWS;
          return (
            <div key={i} style={{ position: "absolute", left: col * tw, top: row * th }}>
              <Photo w={tw} h={th} crop={{ x: col / TILE_COLS, y: row / TILE_ROWS, w: 1 / TILE_COLS, h: 1 / TILE_ROWS }} density={2} />
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", left: 16, right: 16, top: SRC.y + SRC.h + 22, padding: 14, borderRadius: 14, background: C.raised, border: `1px solid ${done ? C.success : C.border}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15 }}>
          <span>photo.jpg</span>
          <span style={{ color: C.muted }}>4,8 Mo</span>
        </div>
        <div style={{ height: 6, borderRadius: 6, background: C.border, margin: "10px 0", overflow: "hidden" }}>
          <div style={{ width: `${(landed / TILE_N) * 100}%`, height: "100%", background: done ? C.success : C.accent }} />
        </div>
        <div style={{ fontSize: 14, color: done ? C.success : C.muted, fontWeight: done ? 700 : 400 }}>{status}</div>
      </div>
    </>
  );
};

const MobileReceive: React.FC<{ t: number }> = ({ t }) => {
  const arrived = t > T.doc + 0.85;
  const k = p(t, T.doc + 0.85, 0.5);
  const done = t > T.doc + 1.25;
  return (
    <>
      <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 12 }}>Fichiers proposés par le PC</div>
      <div
        style={{
          padding: 14,
          borderRadius: 14,
          background: C.raised,
          border: `1px solid ${done ? C.success : C.border}`,
          opacity: arrived ? 1 : 0,
          transform: `translateY(${(1 - k) * 20}px)`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 15 }}>
          <IconDoc size={24} color={C.accent} />
          <span>Rapport.pdf</span>
          <span style={{ marginLeft: "auto", color: C.muted }}>2,1 Mo</span>
        </div>
        <div
          style={{
            marginTop: 12,
            padding: "9px 0",
            textAlign: "center",
            borderRadius: 10,
            background: done ? "transparent" : C.accent,
            border: done ? `1px solid ${C.success}` : "none",
            color: done ? C.success : "#fff",
            fontWeight: 700,
            fontSize: 15,
          }}
        >
          {done ? "Reçu ✓" : "Télécharger"}
        </div>
      </div>
      {!arrived && <div style={{ color: C.muted, fontSize: 14 }}>Recherche des fichiers proposés par le PC…</div>}
    </>
  );
};

// ------------------------------------------------------------------ « pas d'app, pas de compte, pas de cloud »
const NOPE: Array<{ word: [string, number]; label: string; icon: React.ReactNode }> = [
  { word: ["pas", 0], label: "Pas d'application", icon: <IconApp size={34} color={C.muted} /> },
  { word: ["pas", 1], label: "Pas de compte", icon: <IconUser size={34} color={C.muted} /> },
  { word: ["pas", 2], label: "Pas de cloud", icon: <IconCloud size={34} color={C.muted} /> },
];

const NoChips: React.FC<{ t: number }> = ({ t }) => {
  const out = p(t, T.toTransfer, 0.4, EASE.in);
  return (
    <div style={{ position: "absolute", top: 76, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 22, opacity: 1 - out }}>
      {NOPE.map((n, i) => {
        const at = W("pair", n.word[0], n.word[1]) - 0.05;
        const k = p(t, at, 0.5, EASE.stamp);
        const strike = p(t, at + 0.2, 0.35);
        return (
          <div key={i} style={{ transform: `scale(${k})`, opacity: Math.min(1, k * 2) }}>
            <Chip size={34} style={{ padding: "14px 28px", position: "relative" }}>
              <span style={{ position: "relative", display: "inline-flex" }}>
                {n.icon}
                <IconX size={34} color={C.danger} sw={2.6} style={{ position: "absolute", left: 0, top: 0, opacity: strike, transform: `scale(${lerp(1.6, 1, strike)})` }} />
              </span>
              {n.label}
            </Chip>
          </div>
        );
      })}
    </div>
  );
};

// ------------------------------------------------------------------ scène
export const Product: React.FC<{ t: number }> = ({ t }) => {
  if (t < T.enter - 0.05 || t > E("outro")) return null;
  const l = layoutAt(t);
  const scanTilt = win(t, T.scanAim, T.scanOK + 0.1, 0.5, 0.5);
  const drift = { x: Math.sin(t * 0.4) * 4, y: Math.cos(t * 0.3) * 3 };

  // blocs en vol (coordonnées écran)
  const tiles = Array.from({ length: TILE_N }, (_, i) => {
    const k = p(t, tileStart(i), TILE_DUR, EASE.inOut);
    if (k <= 0 || k >= 1) return null;
    const col = i % TILE_COLS;
    const row = Math.floor(i / TILE_COLS);
    const sx = l.phone.x + (PSCR.x + SRC.x + (col * SRC.w) / TILE_COLS) * l.phone.s;
    const sy = l.phone.y + (PSCR.y + SRC.y + (row * SRC.h) / TILE_ROWS) * l.phone.s;
    const ssz = (SRC.w / TILE_COLS) * l.phone.s;
    const dx = l.pc.x + (LSCR.x + DEST.x + (col * DEST.w) / TILE_COLS) * l.pc.s;
    const dy = l.pc.y + (LSCR.y + DEST.y + (row * DEST.h) / TILE_ROWS) * l.pc.s;
    const dsz = (DEST.w / TILE_COLS) * l.pc.s;
    const x = lerp(sx, dx, k);
    const y = lerp(sy, dy, k) - Math.sin(Math.PI * k) * 100;
    const s = lerp(ssz, dsz, k) / dsz;
    const tw = dsz;
    const th = (DEST.h / TILE_ROWS) * l.pc.s;
    return (
      <div
        key={i}
        style={{
          position: "absolute",
          left: x,
          top: y,
          transformOrigin: "0 0",
          transform: `scale(${s}) rotate(${Math.sin(Math.PI * k) * (col - 1.5) * 4}deg)`,
          boxShadow: `0 12px 30px rgba(0,0,0,0.5), 0 0 0 2px ${C.accent}`,
        }}
      >
        <Photo w={tw} h={th} crop={{ x: col / TILE_COLS, y: row / TILE_ROWS, w: 1 / TILE_COLS, h: 1 / TILE_ROWS }} density={1.6} />
      </div>
    );
  });

  // document PC → téléphone
  const dk = p(t, T.doc - 0.1, 0.95, EASE.inOut);
  const docFrom = { x: l.pc.x + (LSCR.x + 214 + 24 + 330) * l.pc.s, y: l.pc.y + (LSCR.y + 34 + 24 + 60 + 40) * l.pc.s };
  const docTo = { x: l.phone.x + (PSCR.x + 40) * l.phone.s, y: l.phone.y + (PSCR.y + 150) * l.phone.s };

  // flux Wi-Fi entre les deux appareils
  const wifiK = win(t, T.toTransfer + 0.3, T.toProof, 0.6, 0.3) + win(t, T.toBoth + 0.4, T.toOutro, 0.6, 0.3);
  const wifiX = (l.phone.x + PW * l.phone.s + l.pc.x + LSCR.x * l.pc.s) / 2;
  const both = win(t, W("both", "deux") - 0.2, T.toOutro, 0.6, 0.3);

  return (
    <div style={{ position: "absolute", inset: 0, transform: `translate(${drift.x}px,${drift.y}px)` }}>
      {/* halo */}
      <div style={{ position: "absolute", left: 120, top: 180, width: 1700, height: 800, background: "radial-gradient(ellipse at center, rgba(79,140,255,0.12), rgba(0,0,0,0) 62%)", opacity: l.pc.o }} />

      <div style={{ position: "absolute", left: l.pc.x, top: l.pc.y, transformOrigin: "0 0", transform: `scale(${l.pc.s})`, opacity: l.pc.o }}>
        <Laptop w={LW} glow={win(t, T.verify - 0.1, T.toProof, 0.4, 0.4) * 0.8}>
          <Desktop t={t} />
        </Laptop>
      </div>

      <div
        style={{
          position: "absolute",
          left: l.phone.x,
          top: l.phone.y,
          transformOrigin: "0 0",
          transform: `scale(${l.phone.s}) translateX(${scanTilt * 60}px) rotate(${scanTilt * 4}deg)`,
          opacity: l.phone.o,
        }}
      >
        <Phone w={PW} glow={win(t, T.scanOK, T.connected + 0.5, 0.2, 0.5)}>
          <Mobile t={t} />
        </Phone>
      </div>

      {wifiK > 0 && (
        <div style={{ position: "absolute", left: wifiX - 50, top: 300, opacity: Math.min(1, wifiK), display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <IconWifi size={100} color={C.accent} sw={2} level={1 + (Math.floor(t * 4) % 3)} />
          <div style={{ fontFamily: FONT.body, fontWeight: 700, fontSize: 22, color: C.accent, whiteSpace: "nowrap" }}>Wi-Fi local</div>
        </div>
      )}

      {both > 0 && (
        <div style={{ position: "absolute", left: wifiX - 300, top: 170, width: 600, whiteSpace: "nowrap", textAlign: "center", opacity: both, fontFamily: FONT.display, fontWeight: 700, fontSize: 40, color: C.text }}>
          ⇄ <span style={{ fontSize: 30 }}>dans les deux sens</span>
        </div>
      )}

      {tiles}

      {dk > 0 && dk < 1 && (
        <div
          style={{
            position: "absolute",
            left: lerp(docFrom.x, docTo.x, dk),
            top: lerp(docFrom.y, docTo.y, dk) - Math.sin(Math.PI * dk) * 160,
            transform: `rotate(${Math.sin(Math.PI * dk) * -10}deg)`,
            padding: 14,
            borderRadius: 14,
            background: C.raised,
            border: `2px solid ${C.accent}`,
            boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            gap: 10,
            fontFamily: FONT.body,
            fontWeight: 700,
            color: C.text,
            fontSize: 20,
          }}
        >
          <IconDoc size={36} color={C.accent} /> Rapport.pdf
        </div>
      )}

      {t < T.toTransfer + 0.5 && <NoChips t={t} />}    </div>
  );
};

export const PRODUCT_T = T;
