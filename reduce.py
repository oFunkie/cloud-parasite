"""
Réduit un GIF (dimensions, couleurs, nombre de frames) jusqu'à ce que sa
taille encodée en base64 tienne dans un nombre de chunks/cookies cible.
"""

import base64
from PIL import Image, ImageSequence

# --- Paramètres à ajuster ---
INPUT_PATH = "run.gif"
OUTPUT_PATH = "run_compress.gif"
CHUNK_SIZE = 2900          # doit correspondre à celui utilisé dans app.py
TARGET_MAX_CHUNKS = 15     # nombre de cookies max souhaité (15-20 recommandé)
MAX_ATTEMPTS = 25


def resize_gif(input_path, output_path, scale, colors, max_frames=None):
    img = Image.open(input_path)
    frames = []
    durations = []

    for frame in ImageSequence.Iterator(img):
        frame = frame.convert("RGB")
        new_size = (max(1, int(frame.width * scale)), max(1, int(frame.height * scale)))
        frame = frame.resize(new_size, Image.LANCZOS)
        frame = frame.convert("P", palette=Image.ADAPTIVE, colors=colors)
        frames.append(frame)
        durations.append(img.info.get("duration", 100))

    if max_frames:
        # on garde un échantillon régulier plutôt que juste le début, pour
        # conserver un semblant d'animation complète
        step = max(1, len(frames) // max_frames)
        frames = frames[::step][:max_frames]
        durations = durations[::step][:max_frames]

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )


def get_base64_size(path):
    with open(path, "rb") as f:
        return len(base64.b64encode(f.read()))


def main():
    target_base64_size = TARGET_MAX_CHUNKS * CHUNK_SIZE

    scale = 1.0
    colors = 128
    max_frames = None

    original_size = get_base64_size(INPUT_PATH)
    print(f"Taille base64 originale : {original_size} caractères")
    print(f"Objectif : <= {target_base64_size} caractères ({TARGET_MAX_CHUNKS} chunks max)\n")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        resize_gif(INPUT_PATH, OUTPUT_PATH, scale=scale, colors=colors, max_frames=max_frames)
        size = get_base64_size(OUTPUT_PATH)
        chunks_needed = -(-size // CHUNK_SIZE)  # arrondi vers le haut

        print(
            f"Essai {attempt}: scale={scale:.2f}, colors={colors}, "
            f"max_frames={max_frames} -> {size} caractères ({chunks_needed} chunks)"
        )

        if size <= target_base64_size:
            print(f"\n✅ Objectif atteint : {OUTPUT_PATH} ({chunks_needed} chunks)")
            return

        # Réduit progressivement : d'abord les couleurs, puis la taille,
        # puis le nombre de frames si nécessaire
        if colors > 16:
            colors = max(16, int(colors * 0.75))
        elif scale > 0.15:
            scale *= 0.8
        else:
            img = Image.open(INPUT_PATH)
            total_frames = sum(1 for _ in ImageSequence.Iterator(img))
            max_frames = max(2, (max_frames or total_frames) - 2)

    print("\n⚠️ Objectif non atteint après le nombre d'essais max. "
          "Réduis TARGET_MAX_CHUNKS ou accepte une image plus dégradée.")


if __name__ == "__main__":
    main()