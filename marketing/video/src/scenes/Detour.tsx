// 0 → ~30 s : plan-séquence unique. La photo fait le tour d'Internet pour parcourir 50 cm,
// s'abîme en route, puis tout se rembobine et la ligne se redresse.
import React from "react";
import { C, E, EASE, FONT, LINES, S, W, fmt, lerp, p, routeD, routePoint, win, type Seg } from "../lib";
import { Photo, WINDOWS_CROP } from "../Photo";
import { Chip, IconChat, IconCloud, IconFolder, IconLock, IconUser, Laptop, Phone, PHONE_RATIO, LAPTOP_RATIO } from "../ui";

// ------------------------------------------------------------------ géographie du « monde »
const PHONE = { x: 560, y: 560, w: 280 };
const PC = { x: 1340, y: 540, w: 540 };
const PC_SCREEN_H = PC.w * LAPTOP_RATIO;
const PC_TOP = PC.y - 190;

const NET = { x: 420, y: -310 };
const DRIVE = { x: 980, y: -520 };
const CHAT = { x: 1600, y: -290 };

const PHONE_TOP: [number, number] = [PHONE.x, PHONE.y - (PHONE.w * PHONE_RATIO) / 2 - 8];
const PC_IN: [number, number] = [PC.x, PC_TOP - 6];

const DRIVE_ROUTE: Seg[] = [
  [PHONE_TOP, [540, 60], [330, -150], [NET.x, NET.y]],
  [[NET.x, NET.y], [500, -500], [760, -580], [DRIVE.x, DRIVE.y]],
  [[DRIVE.x, DRIVE.y], [1220, -450], [1380, -60], PC_IN],
];
const CHAT_ROUTE: Seg[] = [
  [PHONE_TOP, [640, -40], [1150, -450], [CHAT.x, CHAT.y]],
  [[CHAT.x, CHAT.y], [1840, -220], [1640, 150], PC_IN],
];

// segment direct (le « vrai » trajet) : bord droit du téléphone → bord gauche du PC
export const DIRECT = { x1: 712, x2: 1028, y: 560 };
export const DIRECT_CAM = { cx: (DIRECT.x1 + DIRECT.x2) / 2, cy: DIRECT.y, s: 1.3 };

// ------------------------------------------------------------------ caméra
type Cam = { cx: number; cy: number; s: number };
const camera = (t: number): Cam => {
  const steps: Array<{ at: number; dur: number; to: Cam }> = [
    { at: W("hook", "PC") - 0.9, dur: 1.5, to: { cx: 950, cy: 520, s: 1.0 } },
    { at: S("detour") + 0.2, dur: 1.9, to: { cx: 990, cy: -40, s: 0.56 } },
    { at: S("loss") - 0.15, dur: 1.0, to: { cx: PC.x, cy: PC_TOP + PC_SCREEN_H / 2 + 10, s: 2.25 } },
    { at: W("loss", "pour") - 0.25, dur: 1.4, to: { cx: 950, cy: 500, s: 0.95 } },
    { at: E("twist") + 0.05, dur: 1.1, to: DIRECT_CAM },
  ];
  let cam: Cam = { cx: PHONE.x, cy: 540, s: 1.85 };
  for (const st of steps) {
    const k = p(t, st.at, st.dur, EASE.inOut);
    if (k <= 0) break;
    // interpolation de l'échelle en log : zoom perçu uniforme
    cam = {
      cx: lerp(cam.cx, st.to.cx, k),
      cy: lerp(cam.cy, st.to.cy, k),
      s: Math.exp(lerp(Math.log(cam.s), Math.log(st.to.s), k)),
    };
  }
  // dérive permanente, très légère
  return { cx: cam.cx + Math.sin(t * 0.35) * 5, cy: cam.cy + Math.cos(t * 0.27) * 4, s: cam.s * (1 + 0.006 * Math.sin(t * 0.5)) };
};

// ------------------------------------------------------------------ éléments
const Node: React.FC<{ x: number; y: number; k: number; label: string; sub?: string; icon: React.ReactNode; tint?: string }> = ({
  x,
  y,
  k,
  label,
  sub,
  icon,
  tint = C.muted,
}) => (
  <div
    style={{
      position: "absolute",
      left: x - 110,
      top: y - 110,
      width: 220,
      height: 220,
      transform: `scale(${k * 1.3})`,
      opacity: Math.min(1, k * 1.5),
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
    }}
  >
    <div
      style={{
        width: 170,
        height: 170,
        borderRadius: 999,
        background: "radial-gradient(circle at 35% 30%, #262b36, #14171d)",
        border: `3px solid ${C.border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: tint,
        boxShadow: "0 30px 60px rgba(0,0,0,0.5)",
      }}
    >
      {icon}
    </div>
    <div style={{ position: "absolute", top: 222, whiteSpace: "nowrap", textAlign: "center", fontFamily: FONT.display, fontWeight: 700, fontSize: 46, color: C.text }}>
      {label}
      {sub && <div style={{ fontFamily: FONT.body, fontWeight: 500, fontSize: 32, color: C.muted, marginTop: 6 }}>{sub}</div>}
    </div>
  </div>
);

const Route: React.FC<{ segs: Seg[]; drawn: number; color: string; opacity: number; t: number }> = ({ segs, drawn, color, opacity, t }) => {
  const d = routeD(segs);
  if (drawn <= 0.001) return null;
  const packets = [0, 1, 2, 3, 4, 5].map((i) => (drawn - ((t * 0.18 + i / 6) % 1) * drawn));
  return (
    <g opacity={opacity}>
      <path d={d} pathLength={1} stroke={color} strokeOpacity={0.18} strokeWidth={26} fill="none" strokeLinecap="round" strokeDasharray={`${drawn} 2`} />
      <path d={d} pathLength={1} stroke={color} strokeWidth={7} fill="none" strokeLinecap="round" strokeDasharray={`${drawn} 2`} />
      {packets.map((u, i) => {
        const [x, y] = routePoint(segs, u);
        return <circle key={i} cx={x} cy={y} r={9} fill="#fff" opacity={0.8} />;
      })}
    </g>
  );
};

const Card: React.FC<{ x: number; y: number; q: number; label: string; labelColor: string; squash?: number; opacity?: number }> = ({
  x,
  y,
  q,
  label,
  labelColor,
  squash = 0,
  opacity = 1,
}) => (
  <div
    style={{
      position: "absolute",
      left: x - 120,
      top: y - 90,
      opacity,
      transform: `scale(${1 + squash * 0.25}, ${1 - squash * 0.35}) rotate(${squash * -6}deg)`,
    }}
  >
    <div style={{ padding: 8, background: "#fff", borderRadius: 10, boxShadow: "0 24px 50px rgba(0,0,0,0.6)" }}>
      <Photo w={224} h={168} quality={q} density={1.5} />
    </div>
    <Chip size={30} color={labelColor} style={{ position: "absolute", left: "50%", top: -64, transform: "translateX(-50%)", fontFamily: FONT.mono }}>
      {label}
    </Chip>
  </div>
);

const Magnifier: React.FC<{ x: number; y: number; k: number; q: number; size: number; color: string; label: string }> = ({ x, y, k, q, size, color, label }) => (
  <div style={{ position: "absolute", left: x - size / 2, top: y - size / 2, transform: `scale(${k})`, opacity: Math.min(1, k * 2) }}>
    <div style={{ width: size, height: size, borderRadius: 999, overflow: "hidden", border: `5px solid ${color}`, boxShadow: `0 20px 50px rgba(0,0,0,0.6)` }}>
      <Photo w={size} h={size} quality={q} crop={{ ...WINDOWS_CROP, w: WINDOWS_CROP.h * 0.75, h: WINDOWS_CROP.h }} density={1.4} />
    </div>
    <div
      style={{
        position: "absolute",
        left: size / 2,
        top: size + 12,
        transform: "translateX(-50%)",
        whiteSpace: "nowrap",
        fontFamily: FONT.display,
        fontWeight: 700,
        fontSize: 30,
        color,
        background: "rgba(10,12,16,0.85)",
        padding: "6px 16px",
        borderRadius: 12,
      }}
    >
      {label}
    </div>
  </div>
);

// ------------------------------------------------------------------ scène
export const Detour: React.FC<{ t: number }> = ({ t }) => {
  const cam = camera(t);

  // --- apparition des nœuds (« tu fais un détour »)
  const nodeIn = (i: number) => p(t, W("detour", "detour") - 0.1 + i * 0.18, 0.7, EASE.stamp);
  const rewind = p(t, E("loss") + 0.15, 1.05, EASE.inOut);
  const nodeK = (i: number) => nodeIn(i) * (1 - rewind);

  // --- trajet Drive
  const upStart = W("drive", "part") - 0.15;
  const upU = p(t, upStart, 1.7, EASE.inOut) * (2 / 3);
  const downU = p(t, W("drive", "redescend") - 0.25, 1.15, EASE.inOut) * (1 / 3);
  const driveU = upU + downU;
  const driveArrived = driveU > 0.995;
  const lockK = p(t, W("drive", "compte") - 0.05, 0.5, EASE.stamp) * (1 - rewind);

  // --- trajet messagerie
  const chatUp = p(t, W("chat", "telegram") - 0.1, 1.6, EASE.inOut) * 0.5;
  const chatDown = p(t, W("chat", "compress") - 0.35, 1.0, EASE.inOut) * 0.5;
  const chatU = chatUp + chatDown;
  const crush = p(t, W("chat", "image") - 0.15, 0.9, EASE.inOut);
  const squash = Math.sin(Math.min(1, crush) * Math.PI) * 1.0;
  const chatQ = lerp(1, 0.2, crush);
  const kb = lerp(4.8 * 1024, 312, crush);
  const sizeLabel = kb > 1024 ? `${fmt(kb / 1024)} Mo` : `${Math.round(kb)} Ko`;
  const chatArrived = chatU > 0.995;

  // --- PC : dernier fichier reçu
  const pcPhoto = chatArrived ? "chat" : driveArrived ? "drive" : null;
  const pcIn = chatArrived ? p(t, W("chat", "compress") + 0.6, 0.5) : p(t, W("drive", "redescend") + 0.9, 0.5);
  const pcOut = 1 - rewind;

  // --- perte de détails, puis « 50 cm »
  const magK = win(t, W("loss", "details") - 0.2, W("loss", "pour") - 0.4, 0.55, 0.35);
  const routesDim = lerp(1, 0.35, p(t, W("loss", "pour") - 0.2, 0.8));
  const dimK = p(t, W("loss", "cinquante") - 0.15, 0.7) * (1 - p(t, S("twist") - 0.1, 0.4, EASE.in));

  // --- twist : ton réseau
  const netK = p(t, S("twist") + 0.1, 1.3, EASE.inOut) * (1 - p(t, E("twist") + 0.15, 0.4, EASE.in));
  const direct = p(t, E("twist") + 0.1, 0.65, EASE.inOut);

  // le PC affiche une « invite » au début
  const idle = 1 - p(t, W("drive", "redescend") + 0.8, 0.3);

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          transformOrigin: "0 0",
          transform: `translate(960px,540px) scale(${cam.s}) translate(${-cam.cx}px,${-cam.cy}px)`,
        }}
      >
        {/* sol / halo sous les appareils */}
        <div
          style={{
            position: "absolute",
            left: 200,
            top: 300,
            width: 1500,
            height: 700,
            background: "radial-gradient(ellipse at center, rgba(79,140,255,0.10), rgba(0,0,0,0) 65%)",
          }}
        />

        {/* « ton réseau » */}
        <svg style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }} width={1} height={1}>
          <rect
            x={360}
            y={215}
            width={1320}
            height={700}
            rx={70}
            fill={`rgba(79,140,255,${0.06 * netK})`}
            stroke={C.accent}
            strokeWidth={4}
            strokeDasharray="18 16"
            pathLength={1000}
            strokeDashoffset={-t * 30}
            opacity={netK}
          />
        </svg>
        {netK > 0 && (
          <Chip size={34} color={C.accent} style={{ position: "absolute", left: 1020 - 180, top: 190, opacity: netK, borderColor: C.accent }}>
            <svg width={34} height={34} viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth={2} strokeLinecap="round">
              <circle cx="12" cy="19" r="1.3" fill={C.accent} />
              <path d="M8.5 15.5a5 5 0 0 1 7 0M5.5 12.3a9.3 9.3 0 0 1 13 0M2.5 9a13.6 13.6 0 0 1 19 0" />
            </svg>
            Ton réseau Wi-Fi
          </Chip>
        )}

        {/* trajets */}
        <svg
          style={{ position: "absolute", left: -1200, top: -1400 }}
          width={4400}
          height={3000}
          viewBox="-1200 -1400 4400 3000"
        >
          <Route segs={DRIVE_ROUTE} drawn={driveU * (1 - rewind)} color={C.warning} opacity={routesDim} t={t} />
          <Route segs={CHAT_ROUTE} drawn={chatU * (1 - rewind)} color={C.danger} opacity={routesDim} t={t} />
          {/* le trajet direct */}
          <line
            x1={DIRECT.x1}
            y1={DIRECT.y}
            x2={lerp(DIRECT.x1, DIRECT.x2, direct)}
            y2={DIRECT.y}
            stroke={C.accent}
            strokeWidth={6}
            strokeLinecap="round"
            opacity={direct > 0 ? 1 : 0}
            style={{ filter: "drop-shadow(0 0 12px rgba(79,140,255,0.9))" }}
          />
        </svg>

        {/* nœuds */}
        <Node x={NET.x} y={NET.y} k={nodeK(0)} label="Internet" icon={<IconCloud size={96} color={C.muted} />} />
        <Node x={DRIVE.x} y={DRIVE.y} k={nodeK(1)} label="Drive" sub="dans le cloud" icon={<IconFolder size={88} color={C.warning} />} />
        <Node x={CHAT.x} y={CHAT.y} k={nodeK(2)} label="Messagerie" sub="Telegram · WhatsApp Web" icon={<IconChat size={88} color={C.danger} />} />
        {/* compte requis */}
        <div
          style={{
            position: "absolute",
            left: DRIVE.x + 70,
            top: DRIVE.y - 150,
            transform: `scale(${lockK})`,
            transformOrigin: "left bottom",
          }}
        >
          <Chip size={34} color={C.warning}>
            <IconLock size={34} color={C.warning} />
            Compte requis
            <IconUser size={34} color={C.warning} />
          </Chip>
        </div>

        {/* PC */}
        <div style={{ position: "absolute", left: PC.x - (PC.w * 1.16) / 2, top: PC_TOP }}>
          <Laptop w={PC.w}>
            <div style={{ position: "absolute", inset: 0, background: "radial-gradient(circle at 30% 20%, #1c2540, #0d0f14 70%)" }} />
            <div
              style={{
                position: "absolute",
                left: 30,
                top: 26,
                right: 30,
                bottom: 26,
                borderRadius: 10,
                background: C.raised,
                border: `1.5px solid ${C.border}`,
                opacity: idle,
                display: "flex",
                flexDirection: "column",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderBottom: `1.5px solid ${C.border}`, color: C.muted, fontFamily: FONT.body, fontSize: 20 }}>
                <IconFolder size={22} color={C.warning} /> Téléchargements
              </div>
              <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontFamily: FONT.body, fontSize: 20 }}>
                Ce dossier est vide.
              </div>
            </div>
            {pcPhoto && (
              <div style={{ position: "absolute", inset: 0, opacity: pcIn * pcOut }}>
                <Photo w={PC.w} h={PC_SCREEN_H} quality={pcPhoto === "chat" ? chatQ : 1} density={2} />
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    bottom: 0,
                    padding: "10px 16px",
                    background: "rgba(10,12,16,0.82)",
                    fontFamily: FONT.mono,
                    fontSize: 17,
                    color: pcPhoto === "chat" ? C.danger : C.text,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span>photo.jpg</span>
                  <span>{pcPhoto === "chat" ? "1280 × 960 · 312 Ko" : "via Drive · 4,8 Mo"}</span>
                </div>
              </div>
            )}
          </Laptop>
        </div>

        {/* téléphone */}
        <div style={{ position: "absolute", left: PHONE.x - PHONE.w / 2, top: PHONE.y - (PHONE.w * PHONE_RATIO) / 2 }}>
          <Phone w={PHONE.w}>
            <div style={{ position: "absolute", inset: 0, background: "#000" }} />
            <div style={{ position: "absolute", top: 58, left: 20, fontFamily: FONT.body, fontWeight: 700, fontSize: 24, color: C.text }}>Photos</div>
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 120,
                transform: `scale(${lerp(1.18, 1, p(t, 0, 0.9))})`,
              }}
            >
              <Photo w={PHONE.w - 20} h={((PHONE.w - 20) * 3) / 4} density={3} />
            </div>
            <Chip
              size={17}
              style={{
                position: "absolute",
                left: "50%",
                top: 350,
                transform: `translateX(-50%) translateY(${(1 - p(t, W("hook", "parfaite") - 0.1, 0.6)) * 20}px)`,
                opacity: p(t, W("hook", "parfaite") - 0.1, 0.6),
                fontFamily: FONT.mono,
              }}
            >
              4032 × 3024 · 4,8 Mo
            </Chip>
            {/* flash de prise de vue */}
            <div style={{ position: "absolute", inset: 0, background: "#fff", opacity: 1 - p(t, 0.05, 0.5) }} />
          </Phone>
        </div>

        {/* cartes en voyage */}
        {driveU > 0 && !driveArrived && rewind === 0 && (() => {
          const [x, y] = routePoint(DRIVE_ROUTE, driveU);
          return <Card x={x} y={y} q={1} label="4,8 Mo" labelColor={C.text} />;
        })()}
        {chatU > 0 && !chatArrived && rewind === 0 && (() => {
          const [x, y] = routePoint(CHAT_ROUTE, chatU);
          return <Card x={x} y={y} q={chatQ} label={sizeLabel} labelColor={crush > 0.05 ? C.danger : C.text} squash={squash} />;
        })()}

        {/* loupe sur les fenêtres de la ville */}
        <Magnifier x={PC.x + 120} y={PC_TOP + 120} k={magK} q={0.34} size={150} color={C.danger} label="Détails perdus" />

        {/* 50 cm */}
        <div style={{ position: "absolute", left: PHONE.x, top: 150, width: PC.x - PHONE.x, opacity: dimK }}>
          <svg width={PC.x - PHONE.x} height={40} style={{ overflow: "visible" }}>
            <line x1={0} y1={20} x2={(PC.x - PHONE.x) * dimK} y2={20} stroke={C.text} strokeWidth={4} />
            <line x1={0} y1={0} x2={0} y2={40} stroke={C.text} strokeWidth={4} />
            <line x1={(PC.x - PHONE.x) * dimK} y1={0} x2={(PC.x - PHONE.x) * dimK} y2={40} stroke={C.text} strokeWidth={4} />
          </svg>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: -84,
              textAlign: "center",
              fontFamily: FONT.display,
              fontWeight: 700,
              fontSize: 64,
              color: C.text,
              transform: `scale(${lerp(0.7, 1, dimK)})`,
            }}
          >
            50 cm
          </div>
        </div>
      </div>

      {/* rembobinage : lignes de balayage + indicateur */}
      {rewind > 0 && rewind < 1 && (
        <>
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0 2px, transparent 2px 6px)",
              transform: `translateY(${(t * 900) % 6}px)`,
            }}
          />
          <div style={{ position: "absolute", right: 90, top: 70, fontFamily: FONT.display, fontWeight: 700, fontSize: 54, color: C.text, opacity: 0.85 }}>
            ◀◀
          </div>
        </>
      )}

      <TwistTitle t={t} />
    </div>
  );
};

/** « Et si ton fichier ne quittait jamais ton réseau ? » : mot à mot, calé sur la voix. */
const TwistTitle: React.FC<{ t: number }> = ({ t }) => {
  const line = LINES.twist;
  const out = 1 - p(t, E("twist") + 0.2, 0.45, EASE.in);
  if (t < line.start - 0.2 || out <= 0) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 92,
        display: "flex",
        justifyContent: "center",
        flexWrap: "wrap",
        gap: "0 22px",
        fontFamily: FONT.display,
        fontWeight: 700,
        fontSize: 56,
        letterSpacing: -1,
        opacity: out,
      }}
    >
      {line.words.map((w, i) => {
        const k = p(t, line.start + w.t - 0.05, 0.45);
        const last = i === line.words.length - 1;
        return (
          <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingBottom: 8 }}>
            <span
              style={{
                display: "inline-block",
                transform: `translateY(${(1 - k) * 90}%)`,
                color: last ? C.accent : C.text,
              }}
            >
              {w.w}
              {last ? " ?" : ""}
            </span>
          </span>
        );
      })}
    </div>
  );
};
