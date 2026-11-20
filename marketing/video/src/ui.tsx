import React from "react";
import { C, FONT, mulberry32 } from "./lib";

// ------------------------------------------------------------------ appareils
export const PHONE_RATIO = 2.05;

export const Phone: React.FC<{ w?: number; children?: React.ReactNode; style?: React.CSSProperties; glow?: number }> = ({
  w = 300,
  children,
  style,
  glow = 0,
}) => {
  const h = w * PHONE_RATIO;
  return (
    <div
      style={{
        width: w,
        height: h,
        borderRadius: w * 0.16,
        background: "linear-gradient(145deg,#2b303b,#12151b)",
        padding: w * 0.035,
        boxSizing: "border-box",
        boxShadow: `0 40px 80px rgba(0,0,0,0.55), 0 0 0 1.5px #3a404d inset, 0 0 ${60 * glow}px ${18 * glow}px rgba(79,140,255,${0.45 * glow})`,
        position: "relative",
        ...style,
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          borderRadius: w * 0.13,
          background: C.surface,
          overflow: "hidden",
          position: "relative",
        }}
      >
        {children}
        <div
          style={{
            position: "absolute",
            top: w * 0.03,
            left: "50%",
            width: w * 0.28,
            height: w * 0.075,
            marginLeft: -w * 0.14,
            borderRadius: 99,
            background: "#000",
          }}
        />
      </div>
    </div>
  );
};

export const LAPTOP_RATIO = 0.625;

export const Laptop: React.FC<{ w?: number; children?: React.ReactNode; style?: React.CSSProperties; glow?: number }> = ({
  w = 560,
  children,
  style,
  glow = 0,
}) => {
  const h = w * LAPTOP_RATIO;
  const bezel = w * 0.022;
  return (
    <div style={{ width: w * 1.16, position: "relative", ...style }}>
      <div
        style={{
          margin: "0 auto",
          width: w + bezel * 2,
          height: h + bezel * 2,
          padding: bezel,
          boxSizing: "border-box",
          borderRadius: `${w * 0.03}px ${w * 0.03}px 6px 6px`,
          background: "linear-gradient(160deg,#2b303b,#14171d)",
          boxShadow: `0 0 0 1.5px #3a404d inset, 0 0 ${80 * glow}px ${20 * glow}px rgba(79,140,255,${0.4 * glow})`,
        }}
      >
        <div style={{ width: w, height: h, background: "#0d0f14", overflow: "hidden", position: "relative", borderRadius: 4 }}>
          {children}
        </div>
      </div>
      <div
        style={{
          height: w * 0.045,
          background: "linear-gradient(180deg,#3a404d,#1b1f27)",
          borderRadius: `2px 2px ${w * 0.04}px ${w * 0.04}px`,
          boxShadow: "0 30px 60px rgba(0,0,0,0.6)",
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: 0,
            width: w * 0.16,
            marginLeft: -w * 0.08,
            height: w * 0.012,
            background: "#12151b",
            borderRadius: "0 0 8px 8px",
          }}
        />
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ logo (même dessin que l'icône de l'app)
export const Logo: React.FC<{
  size: number;
  square?: number;
  stem?: number;
  head?: number;
  base?: number;
  style?: React.CSSProperties;
}> = ({ size, square = 1, stem = 1, head = 1, base = 1, style }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" style={{ overflow: "visible", ...style }}>
    <defs>
      <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#6aa0ff" />
        <stop offset="1" stopColor="#3a74f0" />
      </linearGradient>
    </defs>
    <rect
      x={16 - 16 * square}
      y={16 - 16 * square}
      width={32 * square}
      height={32 * square}
      rx={8 * square}
      fill="url(#lg)"
      opacity={Math.min(1, square * 2)}
    />
    <g stroke="#fff" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" fill="none">
      <line x1={16} y1={7} x2={16} y2={7 + 13 * stem} opacity={stem > 0 ? 1 : 0} />
      <polyline points="10,14 16,20 22,14" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - head} opacity={head > 0 ? 1 : 0} />
      <line x1={16 - 7 * base} y1={25} x2={16 + 7 * base} y2={25} opacity={base > 0 ? 1 : 0} />
    </g>
  </svg>
);

// ------------------------------------------------------------------ QR Code décoratif (motif déterministe)
const QR_N = 29;
const qrCells = (() => {
  const r = mulberry32(8765);
  const cells: boolean[][] = [];
  for (let y = 0; y < QR_N; y++) {
    cells.push([]);
    for (let x = 0; x < QR_N; x++) cells[y].push(r() < 0.48);
  }
  const finder = (ox: number, oy: number) => {
    for (let y = -1; y <= 7; y++)
      for (let x = -1; x <= 7; x++) {
        const X = ox + x;
        const Y = oy + y;
        if (X < 0 || Y < 0 || X >= QR_N || Y >= QR_N) continue;
        const edge = x === 0 || x === 6 || y === 0 || y === 6;
        const core = x >= 2 && x <= 4 && y >= 2 && y <= 4;
        cells[Y][X] = x >= 0 && x <= 6 && y >= 0 && y <= 6 && (edge || core);
      }
  };
  finder(0, 0);
  finder(QR_N - 7, 0);
  finder(0, QR_N - 7);
  return cells;
})();

export const QR: React.FC<{ size: number; reveal?: number; style?: React.CSSProperties }> = ({ size, reveal = 1, style }) => {
  const cell = size / (QR_N + 4);
  return (
    <svg width={size} height={size} style={{ background: "#fff", borderRadius: size * 0.05, ...style }}>
      {qrCells.flatMap((row, y) =>
        row.map((on, x) =>
          on && (x + y) / (QR_N * 2) <= reveal ? (
            <rect key={`${x}-${y}`} x={(x + 2) * cell} y={(y + 2) * cell} width={cell + 0.3} height={cell + 0.3} fill="#0f1115" />
          ) : null,
        ),
      )}
    </svg>
  );
};

// ------------------------------------------------------------------ icônes (traits, 24×24)
const I: React.FC<{ size: number; color?: string; sw?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  size,
  color = "currentColor",
  sw = 1.8,
  children,
  style,
}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" style={style}>
    {children}
  </svg>
);

type IP = { size: number; color?: string; sw?: number; style?: React.CSSProperties };
export const IconCloud = (p: IP) => (
  <I {...p}>
    <path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.1 9.5 4.3 4.3 0 0 0 7 18z" />
  </I>
);
export const IconFolder = (p: IP) => (
  <I {...p}>
    <path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z" />
  </I>
);
export const IconChat = (p: IP) => (
  <I {...p}>
    <path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.1A8 8 0 1 1 20 12z" />
  </I>
);
export const IconLock = (p: IP) => (
  <I {...p}>
    <rect x="5" y="11" width="14" height="9" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </I>
);
export const IconCheck = (p: IP & { progress?: number }) => (
  <I {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - (p.progress ?? 1)} />
  </I>
);
export const IconWifi = (p: IP & { level?: number }) => {
  const l = p.level ?? 3;
  return (
    <I {...p}>
      <circle cx="12" cy="19" r="1.3" fill={p.color ?? "currentColor"} />
      {l >= 1 && <path d="M8.5 15.5a5 5 0 0 1 7 0" />}
      {l >= 2 && <path d="M5.5 12.3a9.3 9.3 0 0 1 13 0" />}
      {l >= 3 && <path d="M2.5 9a13.6 13.6 0 0 1 19 0" />}
    </I>
  );
};
export const IconDoc = (p: IP) => (
  <I {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h4" />
  </I>
);
export const IconX = (p: IP) => (
  <I {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </I>
);
export const IconClock = (p: IP) => (
  <I {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </I>
);
export const IconApp = (p: IP) => (
  <I {...p}>
    <rect x="4" y="4" width="7" height="7" rx="1.5" />
    <rect x="13" y="4" width="7" height="7" rx="1.5" />
    <rect x="4" y="13" width="7" height="7" rx="1.5" />
    <rect x="13" y="13" width="7" height="7" rx="1.5" />
  </I>
);
export const IconUser = (p: IP) => (
  <I {...p}>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M5 20a7 7 0 0 1 14 0" />
  </I>
);

// ------------------------------------------------------------------ petits éléments
export const Chip: React.FC<{ children: React.ReactNode; color?: string; bg?: string; size?: number; style?: React.CSSProperties }> = ({
  children,
  color = C.text,
  bg = "rgba(24,27,34,0.92)",
  size = 22,
  style,
}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: size * 0.4,
      padding: `${size * 0.35}px ${size * 0.7}px`,
      borderRadius: 999,
      background: bg,
      border: `1.5px solid ${C.border}`,
      color,
      fontFamily: FONT.body,
      fontWeight: 500,
      fontSize: size,
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </div>
);

export const Spinner: React.FC<{ size: number; t: number; color?: string }> = ({ size, t, color = C.accent }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{ transform: `rotate(${t * 360 * 1.3}deg)` }}>
    <circle cx="12" cy="12" r="9" stroke={C.border} strokeWidth="3" fill="none" />
    <path d="M12 3a9 9 0 0 1 9 9" stroke={color} strokeWidth="3" fill="none" strokeLinecap="round" />
  </svg>
);

/** Barre de statut + en-tête de la page mobile LocalDrop. */
export const MobileHeader: React.FC<{ w: number }> = ({ w }) => (
  <div style={{ padding: `${w * 0.15}px ${w * 0.07}px ${w * 0.04}px`, display: "flex", alignItems: "center", gap: w * 0.03 }}>
    <Logo size={w * 0.08} />
    <div style={{ fontFamily: FONT.display, fontWeight: 700, fontSize: w * 0.06, color: C.text }}>LocalDrop</div>
  </div>
);
