# Vidéo de présentation LocalDrop

Motion design de 63 s (1920×1080, 30 fps), voix off française et sous-titres incrustés.

**Concept : « Le Détour ».** La photo fait le tour d'Internet (Drive, messageries) pour parcourir
50 cm et arrive abîmée. On rembobine, la ligne se redresse et devient la flèche du logo.
LocalDrop la transfère ensuite bloc par bloc sur le Wi-Fi, avec une empreinte SHA-256 identique.

## Fabriquer la vidéo

```bash
npm install
py -3.12 -m venv .tts-venv && .tts-venv/Scripts/pip install edge-tts mutagen numpy pillow
.tts-venv/Scripts/python scripts/voiceover.py   # voix off -> public/vo/*.mp3 + src/voice.json (mots horodatés)
.tts-venv/Scripts/python scripts/timeline.py    # montage -> src/timeline.json + musique public/music.wav
npm run render                                  # -> out/localdrop-presentation.mp4
# puis gain audio (+8 dB, crête -1 dBFS) : voir la dernière étape de livraison, fichier out/localdrop-presentation-final.mp4
npm run studio                                  # aperçu interactif
node scripts/stills.mjs 4 21.7 47.5             # images clés (contrôle qualité) -> out/stills/
```

## Modifier

- **Texte de la voix off** : `LINES` dans `scripts/voiceover.py`, puis relancer les trois commandes. Le montage, la musique et les animations calées sur les mots se recalent tout seuls. Un mot utilisé par `W("cle", "mot")` dans les scènes doit rester présent.
- **Voix** : `--voice fr-FR-HenriNeural` (ou Denise, Eloise, Vivienne). Débit : `--rate +8%`.
- **Pauses entre les répliques** : `GAP_BEFORE` dans `scripts/timeline.py`.
- **Couleurs, easings, durées** : `src/lib.ts`, la seule source du système de mouvement.
- **Scènes** : `src/scenes/` (Detour, Reveal, Product, Proof, Outro).

## Version du README principal

Le README racine affiche `docs/media/apercu.gif`, un aperçu muet de 12 s à 640 px et 12 images/s qui assemble les extraits 17,2–21,4 s, 29,9–32,6 s, 42,8–46,2 s et 49,2–50,6 s. Il renvoie vers `docs/media/localdrop-presentation.mp4`, la vidéo complète en 720p (CRF 26). Après un nouveau rendu, il faut régénérer ces deux fichiers à partir de `out/localdrop-presentation-final.mp4`, avec le `ffmpeg.exe` de `node_modules/@remotion/compositor-win32-x64-msvc/`. Ce ffmpeg ne propose ni `trim` ni `concat` en filtre : on découpe chaque extrait avec `-ss`/`-t`, on les assemble avec `-f concat`, puis on passe par `palettegen` et `paletteuse`.

La voix off est synthétisée par le service en ligne de Microsoft Edge (`edge-tts`), qui ne reçoit que le texte du script.
