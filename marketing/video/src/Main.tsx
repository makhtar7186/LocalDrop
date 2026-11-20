import React from "react";
import { AbsoluteFill, Html5Audio, Sequence, staticFile, useCurrentFrame } from "remotion";
import { Captions } from "./Captions";
import { C, E, FPS, LINES, type LineKey, S, p } from "./lib";
import { Detour } from "./scenes/Detour";
import { Outro } from "./scenes/Outro";
import { Product } from "./scenes/Product";
import { Proof } from "./scenes/Proof";
import { HANDOFF, Reveal } from "./scenes/Reveal";

const voiceActive = (t: number) => Object.values(LINES).some((l) => t >= l.start - 0.1 && t <= l.start + l.dur + 0.1);

export const Main: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const detourO = 1 - p(t, HANDOFF, 0.3);
  // fond : légèrement plus chaud pendant le problème, plus froid ensuite
  const warm = 1 - p(t, S("twist"), 2.5);
  return (
    <AbsoluteFill style={{ background: C.bg, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at 50% 40%, rgba(${Math.round(60 + 40 * warm)},${Math.round(50 - 10 * warm)},${Math.round(90 - 40 * warm)},0.55), ${C.bg} 70%)`,
        }}
      />
      {detourO > 0 && (
        <AbsoluteFill style={{ opacity: detourO }}>
          <Detour t={t} />
        </AbsoluteFill>
      )}
      <Reveal t={t} />
      <Product t={t} />
      <Proof t={t} />
      <Outro t={t} />
      <Captions t={t} />

      {/* vignette + grain */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)", pointerEvents: "none" }} />
      <AbsoluteFill
        style={{
          backgroundImage: `url(${staticFile("grain.png")})`,
          backgroundPosition: `${(frame * 73) % 256}px ${(frame * 151) % 256}px`,
          opacity: 0.06,
          mixBlendMode: "overlay",
        }}
      />

      {/* son */}
      <Html5Audio src={staticFile("music.wav")} volume={(f) => (voiceActive(f / FPS) ? 0.42 : 0.7)} />
      {(Object.keys(LINES) as LineKey[]).map((k) => (
        <Sequence key={k} from={Math.round(S(k) * FPS)} durationInFrames={Math.ceil((E(k) - S(k)) * FPS) + 6} layout="none">
          <Html5Audio src={staticFile(`vo/${k}.mp3`)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
