// Système de mouvement, timeline et thème : la seule source des durées, easings et couleurs.
import { Easing, interpolate } from "remotion";
import { loadFont as loadDisplay } from "@remotion/google-fonts/Unbounded";
import { loadFont as loadBody } from "@remotion/google-fonts/DMSans";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import timeline from "./timeline.json";

// ------------------------------------------------------------------ polices
export const FONT = {
  display: loadDisplay("normal", { weights: ["500", "700"], subsets: ["latin", "latin-ext"] }).fontFamily,
  body: loadBody("normal", { weights: ["400", "500", "700"], subsets: ["latin", "latin-ext"] }).fontFamily,
  mono: loadMono("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily,
};

// ------------------------------------------------------------------ couleurs (thème de l'app)
export const C = {
  bg: "#0b0d12",
  surface: "#0f1115",
  raised: "#181b22",
  border: "#2a2f3a",
  text: "#e6e8ec",
  muted: "#9aa3b2",
  accent: "#4f8cff",
  success: "#3ccf8e",
  warning: "#f5b84a",
  danger: "#ff6b6b",
};

// ------------------------------------------------------------------ easings : une seule famille (expo)
export const EASE = {
  out: Easing.bezier(0.16, 1, 0.3, 1),
  in: Easing.bezier(0.7, 0, 0.84, 0),
  inOut: Easing.bezier(0.83, 0, 0.17, 1),
  // léger dépassement, réservé aux « tampons » (une seule famille d'usage)
  stamp: Easing.bezier(0.34, 1.56, 0.64, 1),
};

export const DUR = { micro: 0.22, enter: 0.6, scene: 0.9 };
export const STAGGER = 0.06;

/** Progression 0..1 entre `start` et `start + dur` (secondes), bornée. */
export const p = (t: number, start: number, dur: number, ease = EASE.out) =>
  interpolate(t, [start, start + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

/** Fenêtre d'apparition/disparition : 0 → 1 (entrée) puis → 0 (sortie). */
export const win = (t: number, inAt: number, outAt: number, din = DUR.enter, dout = 0.4) =>
  p(t, inAt, din) * (1 - p(t, outAt, dout, EASE.in));

// ------------------------------------------------------------------ timeline (voix off)
type Word = { w: string; t: number; d: number };
type Line = { start: number; dur: number; text: string; words: Word[] };
export type LineKey = keyof typeof timeline.lines;

export const FPS = timeline.fps;
export const TOTAL = timeline.total;
export const FRAMES = timeline.frames;
export const LINES = timeline.lines as Record<LineKey, Line>;

export const S = (k: LineKey) => LINES[k].start;
export const E = (k: LineKey) => LINES[k].start + LINES[k].dur;

/** Instant absolu (s) où le mot commençant par `prefix` est prononcé dans la réplique `k`. */
export const W = (k: LineKey, prefix: string, occurrence = 0) => {
  const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const hits = LINES[k].words.filter((w) => norm(w.w).startsWith(norm(prefix)));
  const hit = hits[occurrence];
  if (!hit) throw new Error(`Mot introuvable : « ${prefix} » dans ${k}`);
  return LINES[k].start + hit.t;
};

// ------------------------------------------------------------------ PRNG déterministe
export const mulberry32 = (seed: number) => () => {
  seed |= 0;
  seed = (seed + 0x6d2b79f5) | 0;
  let r = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
  return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
};

// ------------------------------------------------------------------ courbes de Bézier (trajets)
export type Pt = [number, number];
export type Seg = [Pt, Pt, Pt, Pt];

export const bez = ([a, b, c, d]: Seg, u: number): Pt => {
  const v = 1 - u;
  return [
    v * v * v * a[0] + 3 * v * v * u * b[0] + 3 * v * u * u * c[0] + u * u * u * d[0],
    v * v * v * a[1] + 3 * v * v * u * b[1] + 3 * v * u * u * c[1] + u * u * u * d[1],
  ];
};

export const routeD = (segs: Seg[]) =>
  `M${segs[0][0].join(",")} ` + segs.map((s) => `C${s[1].join(",")} ${s[2].join(",")} ${s[3].join(",")}`).join(" ");

/** Point à la fraction u (0..1) du trajet, segments à poids égal. */
export const routePoint = (segs: Seg[], u: number): Pt => {
  const x = Math.min(0.99999, Math.max(0, u)) * segs.length;
  const i = Math.floor(x);
  return bez(segs[i], x - i);
};

export const fmt = (n: number, digits = 1) => n.toFixed(digits).replace(".", ",");
