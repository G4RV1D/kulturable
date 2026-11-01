"""Quatre propositions de signature musicale « mystère » pour Kulturable (compositions originales).

Chaque proposition : une mélodie de 5 à 7 notes, jouée deux fois (la 2e fois avec une fin différente),
sur une nappe grave et sombre. Durée : environ 9 secondes.
  music/mystere-1.m4a  Boîte à musique   (ré mineur harmonique, le do# donne le côté inquiétant)
  music/mystere-2.m4a  Piano grave        (le demi-ton si♭-la, tension de film à suspense)
  music/mystere-3.m4a  Synthé pulsé       (mode phrygien, le fa au-dessus du mi)
  music/mystere-4.m4a  Cloches            (gamme par tons, sans repère, comme un rêve)
  music/mystere-propositions.m4a : les quatre à la suite, séparées par un court silence.
"""
import sys

import numpy as np
from scipy.signal import butter, lfilter

sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.as_posix())
from make_music import SR, envelope, midi, place, save  # noqa: E402

rng = np.random.default_rng(79)


def music_box(note, length):
    n = int((length + 1.5) * SR)
    t = np.arange(n) / SR
    f = midi(note)
    w = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 5.1 * f * t) * np.exp(-t * 18) + 0.2 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    return w * np.exp(-t * 2.6) * envelope(n, 0.002, 0.3)


def piano(note, length):
    n = int((length + 2.0) * SR)
    t = np.arange(n) / SR
    f = midi(note)
    w = np.zeros(n)
    for h in range(1, 9):
        fh = f * h * np.sqrt(1 + 0.0004 * h * h)  # légère inharmonicité des cordes
        w += (0.6 ** (h - 1)) * np.sin(2 * np.pi * fh * t) * np.exp(-t * (1.2 + 0.5 * h))
    hammer = lfilter(*butter(2, 2500 / (SR / 2)), rng.standard_normal(n)) * np.exp(-t * 60) * 0.05
    return (w + hammer) * envelope(n, 0.002, 0.6)


def synth(note, length):
    n = int((length + 0.4) * SR)
    t = np.arange(n) / SR
    f = midi(note)
    w = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, 12))  # dent de scie douce
    b, a = butter(2, min(0.99, (600 + 1800 * np.exp(-3 * length)) / (SR / 2)))
    w = lfilter(b, a, w)
    return w * envelope(n, 0.01, 0.35) * 0.7


def bell(note, length):
    n = int((length + 3.0) * SR)
    t = np.arange(n) / SR
    f = midi(note)
    w = np.zeros(n)
    for r, a, d in ((0.5, 0.3, 1.0), (1, 1, 1.4), (1.19, 0.5, 2.2), (1.5, 0.35, 2.6), (2.0, 0.4, 3.0), (2.74, 0.25, 4.0), (3.76, 0.15, 5.0)):
        w += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d)
    return w * envelope(n, 0.002, 0.8) * 0.6


def drone(root, seconds):
    """Nappe grave : la tonique et la quinte, plus un souffle de vent filtré."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    w = np.zeros(n)
    for nt, a in ((root, 1.0), (root + 7, 0.5), (root + 12, 0.3)):
        f = midi(nt)
        w += a * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t + 0.6 * np.sin(2 * np.pi * 0.2 * t)))
    wind = lfilter(*butter(2, [300 / (SR / 2), 900 / (SR / 2)], btype="band"), rng.standard_normal(n))
    wind *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t)
    return (w * 0.18 + wind * 0.08) * envelope(n, 1.5, 2.0)


def piece(inst, phrase1, phrase2, root, beat, gain=0.55, echo=0.3):
    """Joue la phrase 1 puis la phrase 2 sur la nappe. Phrases : liste de (note, début en temps, durée en temps)."""
    length = (max(s + d for _, s, d in phrase1) + max(s + d for _, s, d in phrase2)) * beat + 3.5
    mix = np.zeros((int(length * SR), 2))
    dr = drone(root, length)
    mix[: len(dr), 0] += dr
    mix[: len(dr), 1] += dr
    t0 = 0.6
    for phrase in (phrase1, phrase2):
        for note, s, d in phrase:
            place(mix, inst(note, d * beat), t0 + s * beat, gain, 0.5 + rng.uniform(-0.12, 0.12))
        t0 += max(s + d for _, s, d in phrase) * beat
    dl = int(beat * 0.75 * SR)
    mix[dl:] += echo * mix[:-dl] * np.array([0.7, 1.0])
    mix *= envelope(len(mix), 0.3, 1.8)[:, None]
    return mix / np.abs(mix).max() * 0.85


PROPOSALS = {
    # 1. Boîte à musique : ré-la-fa-mi | ré-do#-ré   (puis réponse qui monte)
    "mystere-1": (music_box,
                  [(74, 0, 1), (81, 1, 1), (77, 2, 0.5), (76, 2.5, 0.5), (74, 3, 0.5), (73, 3.5, 0.5), (74, 4, 2)],
                  [(74, 0, 1), (81, 1, 1), (77, 2, 0.5), (79, 2.5, 0.5), (81, 3, 0.5), (82, 3.5, 0.5), (81, 4, 2.5)],
                  38, 0.42),
    # 2. Piano grave : ré-fa-la-si♭… la  (le demi-ton si♭-la, deux fois, puis la chute)
    "mystere-2": (piano,
                  [(50, 0, 0.5), (53, 0.5, 0.5), (57, 1, 0.5), (58, 1.5, 1.5), (57, 3, 1)],
                  [(50, 0, 0.5), (53, 0.5, 0.5), (57, 1, 0.5), (58, 1.5, 1.0), (61, 2.5, 0.5), (62, 3, 2.5)],
                  38, 0.5),
    # 3. Synthé pulsé : mi-mi-fa-mi | si-do-si  (mode phrygien)
    "mystere-3": (synth,
                  [(64, 0, 0.5), (64, 0.5, 0.5), (65, 1, 0.5), (64, 1.5, 1), (71, 2.5, 0.5), (72, 3, 0.5), (71, 3.5, 1.5)],
                  [(64, 0, 0.5), (64, 0.5, 0.5), (65, 1, 0.5), (64, 1.5, 1), (72, 2.5, 0.5), (71, 3, 0.5), (65, 3.5, 0.5), (64, 4, 2)],
                  40, 0.36),
    # 4. Cloches, gamme par tons : do-ré-mi-fa#… mi-do
    "mystere-4": (bell,
                  [(72, 0, 0.5), (74, 0.5, 0.5), (76, 1, 0.5), (78, 1.5, 1.5), (76, 3, 0.5), (72, 3.5, 1.5)],
                  [(72, 0, 0.5), (74, 0.5, 0.5), (76, 1, 0.5), (78, 1.5, 1.0), (80, 2.5, 0.5), (78, 3, 2.5)],
                  36, 0.5),
}

if __name__ == "__main__":
    parts = []
    for name, (inst, p1, p2, root, beat) in PROPOSALS.items():
        m = piece(inst, p1, p2, root, beat)
        save(m, name)
        parts.append(m)
        parts.append(np.zeros((int(1.2 * SR), 2)))
    save(np.concatenate(parts), "mystere-propositions")
