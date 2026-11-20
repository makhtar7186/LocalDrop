"""Calcule le montage (src/timeline.json) et compose la musique (public/music.wav).

Lit src/voice.json (produit par voiceover.py). Aucune dépendance réseau.
Usage : .tts-venv/Scripts/python scripts/timeline.py

Le montage est la seule source de vérité du timing : la vidéo (Remotion) et la
musique lisent les mêmes instants, donc changer un texte ou une pause recale tout.
"""

import json
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
SR = 44100

# Pause (s) AVANT chaque réplique : respirations et temps laissés aux transitions.
GAP_BEFORE = {
    "hook": 0.9,  # le hook visuel démarre seul (flash de la photo)
    "detour": 0.5,
    "drive": 0.35,
    "chat": 0.35,
    "loss": 0.45,
    "twist": 1.3,  # rembobinage du trajet, en silence
    "reveal": 0.9,  # la ligne devient le logo
    "pair": 0.6,
    "transfer": 0.5,
    "proof": 0.5,
    "both": 0.7,
    "outro": 0.8,
}
TAIL = 2.6  # logo tenu après la dernière réplique


def build_timeline() -> dict:
    voice = json.loads((ROOT / "src" / "voice.json").read_text(encoding="utf-8"))
    t = 0.0
    lines = {}
    for key, gap in GAP_BEFORE.items():
        t += gap
        dur = voice[key]["dur"]
        lines[key] = {
            "start": round(t, 3),
            "dur": dur,
            "text": voice[key]["text"],
            "words": voice[key]["words"],
        }
        t += dur
    total = t + TAIL
    return {
        "fps": FPS,
        "total": round(total, 3),
        "frames": int(np.ceil(total * FPS)),
        "lines": lines,
    }


# ---------------------------------------------------------------- synthèse


def note(name: str) -> float:
    names = {
        "C": -9,
        "C#": -8,
        "D": -7,
        "D#": -6,
        "E": -5,
        "F": -4,
        "F#": -3,
        "G": -2,
        "G#": -1,
        "A": 0,
        "A#": 1,
        "B": 2,
    }
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave - 4)) / 12)


def env(n: int, a: float, r: float) -> np.ndarray:
    """Enveloppe attaque/relâchement en secondes."""
    e = np.ones(n)
    na, nr = min(int(a * SR), n), min(int(r * SR), n)
    if na:
        e[:na] = np.linspace(0, 1, na) ** 2
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def pad(freqs: list[float], dur: float, bright: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for i, f in enumerate(freqs):
        for detune in (-0.12, 0.0, 0.13):  # léger chorus
            ff = f * 2 ** (detune / 12)
            ph = 2 * np.pi * ff * t + i
            out += np.sin(ph) + bright * 0.35 * np.sin(2 * ph) + bright * 0.12 * np.sin(3 * ph)
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.18 * t)
    return out * lfo / (len(freqs) * 3)


def pluck(f: float, dur: float = 0.6) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 7)


def kick() -> np.ndarray:
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def tick() -> np.ndarray:
    n = int(0.04 * SR)
    rng = np.random.default_rng(7)
    return rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 140) * 0.5


def whoosh_reverse(dur: float) -> np.ndarray:
    n = int(dur * SR)
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(n)
    # filtre passe-bas glissant (moyenne mobile qui raccourcit) : souffle qui monte
    out = np.zeros(n)
    acc = 0.0
    for i in range(n):
        k = 0.02 + 0.5 * (i / n) ** 2
        acc += k * (noise[i] - acc)
        out[i] = acc
    return out * np.linspace(0, 1, n) ** 3 * 1.4


def chime(freqs: list[float], dur: float = 2.4) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * (2.2 + i)) for i, f in enumerate(freqs))
    return out / len(freqs)


def place(track: np.ndarray, clip: np.ndarray, at: float, gain: float) -> None:
    i = int(at * SR)
    if i >= len(track):
        return
    j = min(len(track), i + len(clip))
    track[i:j] += clip[: j - i] * gain


def build_music(tl: dict) -> np.ndarray:
    lines = tl["lines"]
    total = tl["total"]
    track = np.zeros(int(total * SR) + SR)

    # Partie 1 : le détour. La mineur, sourd, tic-tac d'attente à 96 BPM.
    p1_end = lines["twist"]["start"] - 1.2
    chords1 = [["A2", "C3", "E3"], ["F2", "A2", "C3"], ["D2", "F2", "A2"], ["E2", "G#2", "B2"]]
    beat1 = 60 / 96
    bar = beat1 * 4
    t = 0.0
    i = 0
    while t < p1_end:
        d = min(bar * 1.15, p1_end - t + 0.6)
        clip = pad([note(n) for n in chords1[i % 4]], d, bright=0.25) * env(int(d * SR), 0.4, 0.5)
        place(track, clip, t, 0.22)
        t += bar
        i += 1
    b = 0.0
    while b < p1_end:
        place(track, tick(), b, 0.10 if round(b / beat1) % 2 else 0.16)
        b += beat1
    # le trajet s'enlise : battement sourd qui accélère à la fin de « loss »
    place(track, whoosh_reverse(1.25), lines["twist"]["start"] - 1.25, 0.32)

    # Partie 2 : LocalDrop. Do majeur, lumineux, 100 BPM.
    p2 = lines["reveal"]["start"] - 0.25
    beat2 = 60 / 100
    bar2 = beat2 * 4
    chords2 = [
        ["C3", "E3", "G3", "B3"],
        ["A2", "C3", "E3", "G3"],
        ["F2", "A2", "C3", "E3"],
        ["G2", "B2", "D3", "F3"],
    ]
    arp = {
        0: ["C5", "E5", "G5", "B5"],
        1: ["A4", "C5", "E5", "G5"],
        2: ["F4", "A4", "C5", "E5"],
        3: ["G4", "B4", "D5", "F5"],
    }
    end_music = total - 0.2
    t = p2
    i = 0
    outro = lines["outro"]["start"]
    while t < end_music:
        d = min(bar2 * 1.1, end_music - t)
        if d <= 0.3:
            break
        chord = chords2[i % 4] if t < outro else ["C3", "E3", "G3", "C4"]
        clip = pad([note(n) for n in chord], d, bright=0.6) * env(int(d * SR), 0.25, 0.6)
        place(track, clip, t, 0.20)
        if lines["pair"]["start"] - 0.3 < t < outro:
            for k in range(8):  # croches
                nt = arp[i % 4][k % 4]
                place(track, pluck(note(nt)), t + k * beat2 / 2, 0.07)
        if lines["transfer"]["start"] - 0.5 < t < outro:
            for k in range(4):
                place(track, kick(), t + k * beat2, 0.30)
        t += bar2
        i += 1
    # accent : apparition du logo, preuve d'intégrité, logo final
    place(track, chime([note("C6"), note("G6"), note("E6")]), lines["reveal"]["start"] - 0.1, 0.20)
    place(track, chime([note("E6"), note("B6")]), lines["proof"]["start"] + 2.3, 0.16)
    place(track, chime([note("C5"), note("G5"), note("C6"), note("E6")], 3.5), outro - 0.05, 0.20)

    # fondus de début/fin et normalisation douce
    fade = env(len(track), 0.8, 2.5)
    track *= fade
    peak = np.max(np.abs(track)) or 1.0
    return np.tanh(track / peak * 1.1) * 0.55


def write_wav(path: Path, data: np.ndarray) -> None:
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    tl = build_timeline()
    (ROOT / "src" / "timeline.json").write_text(
        json.dumps(tl, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_wav(ROOT / "public" / "music.wav", build_music(tl))
    for k, v in tl["lines"].items():
        print(f"{k:9s} {v['start']:6.2f} -> {v['start'] + v['dur']:6.2f}")
    print(f"total {tl['total']:.2f} s ({tl['frames']} images)")
