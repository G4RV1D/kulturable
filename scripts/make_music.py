"""Compose une musique d'ambiance originale (libre de droits, car générée ici).

Nappe douce et mystérieuse : accords lents, basse tenue, quelques notes de cloche.
Usage : python scripts/make_music.py   ->  music/ambiance-01.m4a (environ 2 min 30, en boucle)
"""
import pathlib
import subprocess
import wave

import imageio_ffmpeg
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SR = 44100
CHORD_SEC = 8.0
rng = np.random.default_rng(1518)  # graine fixe : la musique est toujours la même


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# Ré mineur, Si bémol, Fa, Do, puis La mineur, Si bémol, Ré mineur, Do
PROGRESSION = [
    [50, 57, 62, 65, 69], [46, 58, 62, 65, 70], [41, 57, 60, 65, 69], [48, 55, 60, 64, 67],
    [45, 57, 60, 64, 69], [46, 58, 62, 65, 70], [50, 57, 62, 65, 69], [48, 55, 60, 64, 67],
]
SCALE = [62, 64, 65, 67, 69, 70, 72, 74, 76, 77]  # notes de cloche (ré mineur)


def envelope(n, attack, release):
    env = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    env[:a] = np.linspace(0, 1, a) ** 2
    env[-r:] *= np.linspace(1, 0, r) ** 2
    return env


def pad(notes, seconds):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for i, note in enumerate(notes):
        f = midi(note)
        vol = 0.5 if i == 0 else 0.22
        for detune, pan in ((-0.004, 0.25), (0.004, 0.75)):  # léger désaccord = son chaud
            ph = rng.uniform(0, 2 * np.pi)
            w = np.sin(2 * np.pi * f * (1 + detune) * t + ph)
            w += 0.18 * np.sin(2 * np.pi * 2 * f * (1 + detune) * t + ph)  # harmonique douce
            trem = 1 + 0.08 * np.sin(2 * np.pi * rng.uniform(0.08, 0.2) * t)
            out[:, 0] += vol * w * trem * (1 - pan)
            out[:, 1] += vol * w * trem * pan
    return out * envelope(n, 2.5, 3.0)[:, None]


def bell(note, seconds=4.0):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = midi(note + 12)
    w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2.76 * f * t) + 0.12 * np.sin(2 * np.pi * 5.4 * f * t)
    return w * np.exp(-t * 1.6) * envelope(n, 0.005, 0.5)


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = np.zeros(x.shape[1])
    for i in range(len(x)):  # filtre du premier ordre, appliqué deux fois plus bas
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def compose(loops=2):
    chords = PROGRESSION * loops
    total = int((len(chords) * CHORD_SEC + 4) * SR)
    mix = np.zeros((total, 2))
    for k, notes in enumerate(chords):
        start = int(k * CHORD_SEC * SR)
        seg = pad(notes, CHORD_SEC + 3.0)  # chevauchement pour des enchaînements doux
        mix[start:start + len(seg)] += seg
        for _ in range(rng.integers(1, 3)):  # une ou deux notes de cloche par accord
            at = start + int(rng.uniform(0.5, CHORD_SEC - 1) * SR)
            b = bell(int(rng.choice(SCALE)))
            pan = rng.uniform(0.2, 0.8)
            end = min(at + len(b), total)
            mix[at:end, 0] += 0.10 * b[:end - at] * (1 - pan)
            mix[at:end, 1] += 0.10 * b[:end - at] * pan
    mix = lowpass(mix, 1800)
    # écho léger pour l'espace
    d = int(0.37 * SR)
    mix[d:] += 0.3 * mix[:-d]
    mix *= envelope(total, 3.0, 4.0)[:, None]
    mix /= np.abs(mix).max() / 0.8
    return mix


def main():
    out_dir = ROOT / "music"
    out_dir.mkdir(exist_ok=True)
    wav_path = out_dir / "_ambiance-01.wav"
    pcm = (compose() * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    out = out_dir / "ambiance-01.m4a"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav_path),
                    "-c:a", "aac", "-b:a", "160k", str(out)], check=True)
    wav_path.unlink()
    print(f"OK : {out}")


if __name__ == "__main__":
    main()
