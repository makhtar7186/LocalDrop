import React from "react";
import { Composition } from "remotion";
import { FPS, FRAMES } from "./lib";
import { Main } from "./Main";

export const Root: React.FC = () => (
  <Composition id="LocalDrop" component={Main} durationInFrames={FRAMES} fps={FPS} width={1920} height={1080} />
);
