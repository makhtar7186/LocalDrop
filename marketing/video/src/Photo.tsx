// « La photo parfaite » : coucher de soleil sur la mer, baobab, pirogue, ville aux fenêtres
// minuscules (le détail fin qui révèle la compression). Dessinée une fois, déterministe.
import React, { useLayoutEffect, useRef } from "react";
import { mulberry32 } from "./lib";

export const PHOTO_W = 1600;
export const PHOTO_H = 1200;

let master: HTMLCanvasElement | null = null;

const drawMaster = (): HTMLCanvasElement => {
  const W = PHOTO_W;
  const H = PHOTO_H;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d")!;
  const r = mulberry32(42);
  const horizon = H * 0.64;

  // ciel
  const sky = g.createLinearGradient(0, 0, 0, horizon);
  sky.addColorStop(0, "#0a1636");
  sky.addColorStop(0.32, "#27306e");
  sky.addColorStop(0.58, "#9b4777");
  sky.addColorStop(0.8, "#f07f4c");
  sky.addColorStop(1, "#ffc875");
  g.fillStyle = sky;
  g.fillRect(0, 0, W, horizon);

  // étoiles
  for (let i = 0; i < 260; i++) {
    const y = r() * horizon * 0.42;
    g.globalAlpha = (1 - y / (horizon * 0.42)) * (0.3 + r() * 0.7);
    g.fillStyle = "#fff";
    const s = r() < 0.08 ? 2.4 : 1.2;
    g.fillRect(r() * W, y, s, s);
  }
  g.globalAlpha = 1;

  // soleil + halo
  const sx = W * 0.64;
  const sy = horizon - 40;
  const halo = g.createRadialGradient(sx, sy, 10, sx, sy, 520);
  halo.addColorStop(0, "rgba(255,226,160,0.95)");
  halo.addColorStop(0.18, "rgba(255,170,90,0.55)");
  halo.addColorStop(1, "rgba(255,120,80,0)");
  g.fillStyle = halo;
  g.fillRect(0, 0, W, horizon);
  g.fillStyle = "#fff1c9";
  g.beginPath();
  g.arc(sx, sy, 78, 0, Math.PI * 2);
  g.fill();

  // nuages fins (bandes)
  for (let i = 0; i < 14; i++) {
    const y = horizon * (0.42 + r() * 0.42);
    const x = r() * W;
    const w = 180 + r() * 420;
    g.fillStyle = `rgba(${120 + r() * 60},${50 + r() * 40},${100 + r() * 40},${0.25 + r() * 0.3})`;
    g.beginPath();
    g.ellipse(x, y, w / 2, 4 + r() * 7, 0, 0, Math.PI * 2);
    g.fill();
  }

  // collines lointaines
  g.fillStyle = "#5b2c5c";
  g.beginPath();
  g.moveTo(0, horizon);
  for (let x = 0; x <= W; x += 8) {
    g.lineTo(x, horizon - 40 - 30 * Math.sin(x / 210) - 22 * Math.sin(x / 67 + 1) * (x < W * 0.45 ? 1 : 0.3));
  }
  g.lineTo(W, horizon);
  g.fill();

  // ville : tours sombres + fenêtres de 3 px
  let x = W * 0.36;
  while (x < W * 1.02) {
    const bw = 28 + r() * 60;
    const bh = 50 + r() * r() * 230;
    g.fillStyle = r() < 0.5 ? "#16112a" : "#1d1532";
    g.fillRect(x, horizon - bh, bw, bh);
    for (let wy = horizon - bh + 8; wy < horizon - 8; wy += 9) {
      for (let wx = x + 5; wx < x + bw - 6; wx += 8) {
        if (r() < 0.38) {
          g.fillStyle = r() < 0.75 ? "#ffd78a" : "#9fd3ff";
          g.fillRect(wx, wy, 3, 4);
        }
      }
    }
    if (r() < 0.2) {
      g.fillStyle = "#ff5a5a";
      g.fillRect(x + bw / 2 - 1.5, horizon - bh - 14, 3, 14);
    }
    x += bw + 2 + r() * 10;
  }

  // mer
  const sea = g.createLinearGradient(0, horizon, 0, H);
  sea.addColorStop(0, "#5a2c55");
  sea.addColorStop(0.35, "#2b1c44");
  sea.addColorStop(1, "#0b0d24");
  g.fillStyle = sea;
  g.fillRect(0, horizon, W, H - horizon);
  // reflets du soleil
  for (let i = 0; i < 180; i++) {
    const yy = horizon + 6 + Math.pow(r(), 1.6) * (H - horizon - 10);
    const spread = 40 + (yy - horizon) * 0.7;
    const xx = sx + (r() - 0.5) * spread * 2;
    g.fillStyle = `rgba(255,${190 + r() * 50},${120 + r() * 60},${0.35 + r() * 0.5})`;
    g.fillRect(xx, yy, 10 + r() * 40, 2 + r() * 2);
  }
  // reflets des fenêtres
  for (let i = 0; i < 220; i++) {
    g.fillStyle = `rgba(255,215,140,${0.15 + r() * 0.3})`;
    g.fillRect(W * 0.36 + r() * W * 0.64, horizon + 4 + r() * 60, 2 + r() * 6, 1.5);
  }

  // pirogue + pêcheur
  const px = W * 0.42;
  const py = H * 0.8;
  g.fillStyle = "#0a0a16";
  g.beginPath();
  g.moveTo(px - 130, py - 14);
  g.quadraticCurveTo(px, py + 26, px + 140, py - 18);
  g.lineTo(px + 120, py - 4);
  g.quadraticCurveTo(px, py + 14, px - 112, py);
  g.closePath();
  g.fill();
  g.fillRect(px + 18, py - 62, 9, 50);
  g.beginPath();
  g.arc(px + 22, py - 70, 10, 0, Math.PI * 2);
  g.fill();
  g.strokeStyle = "#0a0a16";
  g.lineWidth = 4;
  g.beginPath();
  g.moveTo(px + 24, py - 50);
  g.lineTo(px - 40, py + 30);
  g.stroke();

  // rive au premier plan + baobab
  g.fillStyle = "#07060d";
  g.beginPath();
  g.moveTo(0, H * 0.74);
  g.quadraticCurveTo(W * 0.18, H * 0.7, W * 0.34, H);
  g.lineTo(0, H);
  g.fill();
  const bx = W * 0.15;
  const by = H * 0.73;
  g.beginPath();
  g.moveTo(bx - 58, by + 10);
  g.bezierCurveTo(bx - 40, by - 120, bx - 46, by - 230, bx - 30, by - 300);
  g.lineTo(bx + 34, by - 300);
  g.bezierCurveTo(bx + 46, by - 230, bx + 42, by - 120, bx + 64, by + 10);
  g.fill();
  const branch = (x0: number, y0: number, ang: number, len: number, w: number, depth: number) => {
    const x1 = x0 + Math.cos(ang) * len;
    const y1 = y0 + Math.sin(ang) * len;
    g.lineWidth = w;
    g.lineCap = "round";
    g.beginPath();
    g.moveTo(x0, y0);
    g.lineTo(x1, y1);
    g.stroke();
    if (depth > 0) {
      const n = 2 + Math.floor(r() * 2);
      for (let i = 0; i < n; i++) {
        branch(x1, y1, ang + (r() - 0.5) * 1.3, len * (0.55 + r() * 0.2), w * 0.6, depth - 1);
      }
    }
  };
  g.strokeStyle = "#07060d";
  for (let i = 0; i < 6; i++) {
    branch(bx + (i - 2.5) * 10, by - 290, -Math.PI / 2 + (i - 2.5) * 0.36, 70 + r() * 40, 18, 3);
  }

  // oiseaux
  g.strokeStyle = "#1a1030";
  g.lineWidth = 3;
  for (let i = 0; i < 7; i++) {
    const ox = W * 0.48 + r() * 300;
    const oy = H * 0.2 + r() * 160;
    const s = 8 + r() * 8;
    g.beginPath();
    g.moveTo(ox - s, oy - s * 0.4);
    g.quadraticCurveTo(ox - s * 0.4, oy - s * 0.6, ox, oy);
    g.quadraticCurveTo(ox + s * 0.4, oy - s * 0.6, ox + s, oy - s * 0.4);
    g.stroke();
  }
  return c;
};

export const getMaster = () => (master ??= drawMaster());

/** Zone des fenêtres de la ville (pour les loupes). */
export const WINDOWS_CROP = { x: 0.62, y: 0.5, w: 0.13, h: 0.1 };

type Crop = { x: number; y: number; w: number; h: number };

/**
 * quality 1 = original ; plus bas = sous-échantillonnage + postérisation (compression destructrice).
 * crop = sous-rectangle (fractions 0..1) de la photo.
 */
export const Photo: React.FC<{
  w: number;
  h: number;
  quality?: number;
  crop?: Crop;
  radius?: number;
  density?: number;
  style?: React.CSSProperties;
}> = ({ w, h, quality = 1, crop = { x: 0, y: 0, w: 1, h: 1 }, radius = 0, density = 2, style }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const q = Math.round(Math.max(0, Math.min(1, quality)) * 100) / 100;
  useLayoutEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const m = getMaster();
    const sx = crop.x * PHOTO_W;
    const sy = crop.y * PHOTO_H;
    const sw = crop.w * PHOTO_W;
    const sh = crop.h * PHOTO_H;
    ctx.clearRect(0, 0, cv.width, cv.height);
    if (q >= 0.99) {
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(m, sx, sy, sw, sh, 0, 0, cv.width, cv.height);
      return;
    }
    // la résolution effective chute avec q (sur la photo entière, pas sur le recadrage)
    const fullW = Math.max(40, Math.round(PHOTO_W * Math.pow(q, 1.7)));
    const k = fullW / PHOTO_W;
    const tw = Math.max(2, Math.round(sw * k));
    const th = Math.max(2, Math.round(sh * k));
    const small = document.createElement("canvas");
    small.width = tw;
    small.height = th;
    const sctx = small.getContext("2d")!;
    sctx.imageSmoothingEnabled = true;
    sctx.drawImage(m, sx, sy, sw, sh, 0, 0, tw, th);
    // postérisation + léger lissage chromatique : bandes de couleur typiques
    const levels = Math.round(6 + 250 * Math.pow(q, 2));
    const img = sctx.getImageData(0, 0, tw, th);
    const d = img.data;
    const step = 255 / (levels - 1);
    for (let i = 0; i < d.length; i += 4) {
      d[i] = Math.round(d[i] / step) * step;
      d[i + 1] = Math.round(d[i + 1] / step) * step;
      d[i + 2] = Math.round(d[i + 2] / step) * step;
    }
    sctx.putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = q > 0.6;
    ctx.drawImage(small, 0, 0, cv.width, cv.height);
  }, [q, crop.x, crop.y, crop.w, crop.h, w, h, density]);

  return (
    <canvas
      ref={ref}
      width={Math.round(w * density)}
      height={Math.round(h * density)}
      style={{ width: w, height: h, borderRadius: radius, display: "block", ...style }}
    />
  );
};
