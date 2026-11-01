"""Signature musicale officielle de Kulturable : la mélodie « boîte à musique » (proposition 1), enrichie.

Mélodie inchangée : ré-la-fa-mi-ré-do#-ré, puis ré-la-fa-sol-la-si♭-la.
Profondeur ajoutée : accords de cordes (ré m, si♭, la, ré m), violoncelle grave, coup sourd au début,
deuxième voix une octave plus bas sur la réponse, réverbération de grande salle.

  music/signature-kulturable.m4a : version courte (~11 s), pour ouvrir ou fermer une vidéo
  music/theme-mystere.m4a       : version longue (~47 s), pour le fond des Reels et TikTok
"""
import sys

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter

sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.as_posix())
from make_music import SR, envelope, midi, place, save  # noqa: E402
from make_mystery import music_box  # noqa: E402

rng = np.random.default_rng(1887)
BEAT = 0.42

PHRASE_A = [(74, 0, 1), (81, 1, 1), (77, 2, 0.5), (76, 2.5, 0.5), (74, 3, 0.5), (73, 3.5, 0.5), (74, 4, 2)]
PHRASE_B = [(74, 0, 1), (81, 1, 1), (77, 2, 0.5), (79, 2.5, 0.5), (81, 3, 0.5), (82, 3.5, 0.5), (81, 4, 2.5)]
LEN_A, LEN_B = 6.0, 6.5  # en temps
# accords sous chaque phrase : (début en temps, notes, basse)
CHORDS_A = [(0, [62, 65, 69], 38), (2, [58, 62, 65], 34), (3, [57, 61, 64], 33), (4, [62, 65, 69], 38)]
CHORDS_B = [(0, [62, 65, 69], 38), (2, [55, 58, 62], 31), (3, [58, 62, 65], 34), (4, [57, 61, 64], 33)]


def strings(notes, seconds):
    """Cordes : plusieurs dents de scie légèrement désaccordées, adoucies, montée lente."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for nt in notes:
        f = midi(nt)
        for det, pan in ((-0.006, 0.2), (0.0, 0.5), (0.006, 0.8)):
            ph = rng.uniform(0, 2 * np.pi)
            w = sum(np.sin(2 * np.pi * f * (1 + det) * h * t + ph * h) / h for h in range(1, 8))
            vib = 1 + 0.02 * np.sin(2 * np.pi * 5.2 * t + ph)
            out[:, 0] += w * vib * (1 - pan)
            out[:, 1] += w * vib * pan
    b, a = butter(2, 1400 / (SR / 2))
    out = lfilter(b, a, out, axis=0)
    return out / (len(notes) * 3) * envelope(n, 0.6, 0.9)[:, None]


def cello(note, seconds):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = midi(note)
    w = sum((0.7 ** (h - 1)) * np.sin(2 * np.pi * f * h * t + 0.04 * h * np.sin(2 * np.pi * 5 * t)) for h in range(1, 10))
    b, a = butter(2, 900 / (SR / 2))
    return lfilter(b, a, w) * envelope(n, 0.25, 0.7) * 0.5


def boom():
    t = np.arange(int(2.5 * SR)) / SR
    f = 38 + 30 * np.exp(-t * 6)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    noise = lfilter(*butter(2, 200 / (SR / 2)), rng.standard_normal(len(t))) * np.exp(-t * 4) * 0.4
    return (s + noise) * envelope(len(t), 0.003, 0.8)


def reverb(mix, seconds=3.2, wet=0.35):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 3.0 / seconds * 2.3)[:, None]
    ir = lfilter(*butter(1, 5000 / (SR / 2)), ir, axis=0)
    ir[: int(0.02 * SR)] = 0  # petit délai avant la réverbération
    out = np.stack([fftconvolve(mix[:, c], ir[:, c])[: len(mix)] for c in range(2)], axis=1)
    out /= np.abs(out).max() + 1e-9
    return mix * (1 - wet) + out * wet * np.abs(mix).max()


def phrase(mix, notes, chords, t0, length, second_voice=False, strings_gain=0.55):
    for start, ch, bass in chords:
        end = next((s for s, _, _ in chords if s > start), length)
        dur = (end - start) * BEAT + 0.5
        place_st(mix, strings(ch, dur), t0 + start * BEAT, strings_gain)
        place(mix, cello(bass, dur), t0 + start * BEAT, 0.55, 0.45)
    for note, s, d in notes:
        place(mix, music_box(note, d * BEAT), t0 + s * BEAT, 0.6, 0.5 + rng.uniform(-0.1, 0.1))
        if second_voice:
            place(mix, music_box(note - 12, d * BEAT) * 0.8, t0 + s * BEAT + 0.012, 0.35, 0.35)


def place_st(mix, sig, at, gain):
    i = int(at * SR)
    end = min(i + len(sig), len(mix))
    mix[i:end] += gain * sig[: end - i]


def build(sections):
    total_beats = sum(LEN_A if s[0] == "A" else LEN_B for s in sections)
    length = total_beats * BEAT + 4.5
    mix = np.zeros((int(length * SR), 2))
    place(mix, boom(), 0.25, 0.7)
    t0 = 0.6
    for name, voice, sg in sections:
        notes, chords, ln = (PHRASE_A, CHORDS_A, LEN_A) if name == "A" else (PHRASE_B, CHORDS_B, LEN_B)
        phrase(mix, notes, chords, t0, ln, second_voice=voice, strings_gain=sg)
        t0 += ln * BEAT
    # accord final tenu (ré mineur grave) sous la dernière note
    place_st(mix, strings([50, 57, 62, 65], 4.0), t0 - 0.2, 0.5)
    place(mix, cello(38, 4.0), t0 - 0.2, 0.5)
    mix = reverb(mix)
    mix *= envelope(len(mix), 0.2, 2.2)[:, None]
    return mix / np.abs(mix).max() * 0.85


if __name__ == "__main__":
    save(build([("A", False, 0.4), ("B", True, 0.55)]), "signature-kulturable")
    long_form = [("A", False, 0.3), ("B", False, 0.45), ("A", True, 0.5), ("B", True, 0.6)] * 4
    save(build(long_form), "theme-mystere")
