"""Compose une musique d'ambiance originale (libre de droits, car générée ici).

Nappe douce et mystérieuse : accords lents, basse tenue, quelques notes de cloche.
Usage :
  python scripts/make_music.py ambiance   ->  music/ambiance-01.m4a (calme, pour l'accroche)
  python scripts/make_music.py rythme     ->  music/rythme-01.m4a   (rythmé, pour l'explication)
"""
import pathlib
import subprocess
import sys
import wave

import imageio_ffmpeg
import numpy as np
from scipy.signal import butter, lfilter

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


# ---------- morceau rythmé ----------

BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT


def place(mix, sig, at, gain=1.0, pan=0.5):
    i = int(at * SR)
    if i >= len(mix):
        return
    end = min(i + len(sig), len(mix))
    mix[i:end, 0] += gain * sig[:end - i] * (1 - pan) * 2 * 0.5
    mix[i:end, 1] += gain * sig[:end - i] * pan * 2 * 0.5


def kick():
    t = np.arange(int(0.35 * SR)) / SR
    f = 50 + 70 * np.exp(-t * 25)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def band(x, lo, hi):
    b, a = butter(2, [lo / (SR / 2), hi / (SR / 2)], btype="band")
    return lfilter(b, a, x)


def snap():
    t = np.arange(int(0.18 * SR)) / SR
    return band(rng.standard_normal(len(t)), 900, 4000) * np.exp(-t * 28)


def hat(open_=False):
    t = np.arange(int((0.12 if open_ else 0.04) * SR)) / SR
    b, a = butter(2, 7000 / (SR / 2), btype="high")
    return lfilter(b, a, rng.standard_normal(len(t))) * np.exp(-t * (25 if open_ else 90))


def pluck(note, length=0.5, bright=0.35):
    t = np.arange(int(length * SR)) / SR
    f = midi(note)
    w = np.sin(2 * np.pi * f * t) + bright * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
    return w * np.exp(-t * 7) * envelope(len(t), 0.004, 0.05)


def bass(note, length):
    t = np.arange(int(length * SR)) / SR
    f = midi(note)
    w = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    return w * np.exp(-t * 3) * envelope(len(t), 0.005, 0.06)


def compose_rhythm(loops=3):
    chords = PROGRESSION * loops
    bars_per_chord = 2
    total = int((len(chords) * bars_per_chord * BAR + 3) * SR)
    mix = np.zeros((total, 2))
    for k, notes in enumerate(chords):
        c0 = k * bars_per_chord * BAR
        # nappe discrète, pour lier le tout
        p = pad(notes, bars_per_chord * BAR + 1.0) * 0.35
        i = int(c0 * SR)
        mix[i:i + len(p)] += p[: total - i]
        root = notes[0] - 12 if notes[0] >= 48 else notes[0]
        arp = [notes[1] + 12, notes[2] + 12, notes[3] + 12, notes[4] + 12, notes[3] + 12, notes[2] + 12, notes[4] + 12, notes[3] + 12]
        for bar in range(bars_per_chord):
            b0 = c0 + bar * BAR
            first_section = k < 2  # entrée progressive : batterie légère au début
            for beat in range(4):
                t0 = b0 + beat * BEAT
                if beat in (0, 2):
                    place(mix, kick(), t0, 0.9)
                if beat in (1, 3) and not first_section:
                    place(mix, snap(), t0, 0.35, 0.55)
                for half in (0, 1):
                    place(mix, hat(open_=(half == 1 and beat == 3)), t0 + half * BEAT / 2, 0.12 if half else 0.07, 0.65)
            for step in range(8):  # basse en croches
                n = root + (12 if step in (3, 7) else 0)
                place(mix, bass(n, BEAT / 2 * 0.95), b0 + step * BEAT / 2, 0.55, 0.5)
            for step, n in enumerate(arp):  # arpège en croches
                place(mix, pluck(n), b0 + step * BEAT / 2, 0.22, 0.3 if step % 2 else 0.7)
    d = int(BEAT * 0.75 * SR)  # écho calé sur le tempo
    mix[d:] += 0.22 * mix[:-d]
    mix *= envelope(total, 1.5, 3.0)[:, None]
    mix /= np.abs(mix).max() / 0.8
    return mix


def save(mix, name):
    out_dir = ROOT / "music"
    out_dir.mkdir(exist_ok=True)
    wav_path = out_dir / f"_{name}.wav"
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    out = out_dir / f"{name}.m4a"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(wav_path),
                    "-c:a", "aac", "-b:a", "160k", str(out)], check=True)
    wav_path.unlink()
    print(f"OK : {out}")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "ambiance"
    if which == "ambiance":
        save(compose(), "ambiance-01")
    elif which == "rythme":
        save(compose_rhythm(), "rythme-01")
    else:
        sys.exit("usage : make_music.py [ambiance|rythme]")


if __name__ == "__main__":
    main()
