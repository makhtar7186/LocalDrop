"""Génère la voix off (un MP3 par réplique) et src/voice.json (durées en secondes).

Usage : .tts-venv/Scripts/python scripts/voiceover.py [--voice fr-FR-RemyMultilingualNeural]
Modifier le texte ici, relancer, puis re-rendre : le montage se recale tout seul.
"""

import argparse
import asyncio
import json
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "vo"

LINES = {
    "hook": (
        "Tu viens de prendre la photo parfaite. "
        "Elle est sur ton téléphone… et tu la veux sur ton PC."
    ),
    "detour": "Alors, comme tout le monde, tu fais un détour.",
    "drive": "Drive : il faut un compte, le fichier part sur Internet… puis il redescend.",
    "chat": "Telegram, WhatsApp Web : c'est plus rapide, mais ton image arrive compressée.",
    "loss": "Les détails disparaissent. Pour un fichier qui était à cinquante centimètres de toi.",
    "twist": "Et si ton fichier ne quittait jamais ton réseau ?",
    "reveal": "Voici LocalDrop.",
    "pair": (
        "Tu le lances sur ton PC, tu scannes le QR code avec ton téléphone. "
        "Pas d'application à installer, pas de compte, pas de cloud."
    ),
    "transfer": (
        "Le fichier passe directement par ton Wi-Fi, bloc par bloc, et il est vérifié à l'arrivée."
    ),
    "proof": "Même taille. Même empreinte. Au pixel près.",
    "both": "Et ça marche dans les deux sens : du PC vers le téléphone aussi.",
    "outro": "LocalDrop. Tes fichiers restent chez toi… et restent intacts.",
}


async def main(voice: str, rate: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    durations = {}
    for key, text in LINES.items():
        path = OUT / f"{key}.mp3"
        words = []
        with path.open("wb") as audio:
            async for chunk in edge_tts.Communicate(
                text, voice, rate=rate, boundary="WordBoundary"
            ).stream():
                if chunk["type"] == "audio":
                    audio.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    words.append(
                        {
                            "w": chunk["text"],
                            "t": round(chunk["offset"] / 1e7, 3),
                            "d": round(chunk["duration"] / 1e7, 3),
                        }
                    )
        durations[key] = {"dur": round(MP3(path).info.length, 3), "text": text, "words": words}
        print(f"{key:9s} {durations[key]['dur']:6.2f} s")
    (ROOT / "src" / "voice.json").write_text(
        json.dumps(durations, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"total {sum(v['dur'] for v in durations.values()):.1f} s")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--voice", default="fr-FR-RemyMultilingualNeural")
    p.add_argument("--rate", default="+4%")
    a = p.parse_args()
    asyncio.run(main(a.voice, a.rate))
