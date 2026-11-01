"""Thème musical de Kulturable : une mélodie courte et reconnaissable, en composition originale.

- music/jingle-kulturable.m4a : la signature (environ 4 s), à mettre à la fin de chaque Reel ;
- music/theme-kulturable.m4a  : le thème complet (environ 40 s), qui reprend la signature en boucle, pour le fond des Reels.

La signature : ré-fa-la (on monte), puis do-la-RÉ (on retombe sur la note la plus haute, tenue).
Six notes, faciles à fredonner, toujours sur le même rythme.
"""
import sys

import numpy as np

sys.path.insert(0, __import__("pathlib").Path(__file__).resolve().parent.as_posix())
import make_music as mm  # noqa: E402
from make_music import SR, envelope, midi, place, save  # noqa: E402

BPM = 104
BEAT = 60 / BPM
BAR = 4 * BEAT

# (note MIDI, début en temps, durée en temps) — ré mineur
MOTIF = [(74, 0.0, 0.5), (77, 0.5, 0.5), (81, 1.0, 1.0), (84, 2.0, 0.5), (81, 2.5, 0.5), (86, 3.0, 2.5)]
# réponse (2e mesure de chaque phrase)
ANSWER_A = [(84, 0.0, 0.5), (82, 0.5, 0.5), (81, 1.0, 0.5), (77, 1.5, 0.5), (79, 2.0, 1.0), (81, 3.0, 1.0)]
ANSWER_B = [(84, 0.0, 0.5), (82, 0.5, 0.5), (81, 1.0, 0.5), (79, 1.5, 0.5), (77, 2.0, 0.5), (76, 2.5, 0.5), (74, 3.0, 1.0)]
# ré m | si♭ | fa | do | ré m | si♭ | sol m | la
CHORDS = [(50, [62, 65, 69]), (46, [62, 65, 70]), (41, [60, 65, 69]), (48, [60, 64, 67]),
          (50, [62, 65, 69]), (46, [62, 65, 70]), (43, [62, 67, 70]), (45, [61, 64, 69])]


def lead(note, length):
    """Son de la mélodie : clochette chaude (type marimba/glockenspiel), bien audible même bas."""
    n = int((length + 0.6) * SR)
    t = np.arange(n) / SR
    f = midi(note)
    w = (np.sin(2 * np.pi * f * t) + 0.45 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
         + 0.25 * np.sin(2 * np.pi * 3.99 * f * t) * np.exp(-t * 12))
    decay = np.exp(-t * (2.2 if length > 1 else 4.0))
    return w * decay * envelope(n, 0.003, 0.25)


def brass(notes, length):
    """Accord tenu, chaud, pour soutenir la signature."""
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for nt in notes:
        f = midi(nt)
        for h, a in ((1, 1), (2, 0.4), (3, 0.2), (4, 0.1)):
            out += a * np.sin(2 * np.pi * f * h * t + 0.15 * h * np.sin(2 * np.pi * 5 * t))  # vibrato léger et constant
    return out / len(notes) * envelope(n, 0.08, 0.6)


def put_phrase(mix, phrase, t0, gain=0.55):
    for note, start, dur in phrase:
        place(mix, mm.pluck(note - 12, 0.25, 0.2), t0 + start * BEAT, gain * 0.25, 0.4)  # doublure grave
        place(mix, lead(note, dur * BEAT), t0 + start * BEAT, gain, 0.55)


def jingle():
    """La signature seule : motif + accord final."""
    total = int((5 * BEAT + 2.2) * SR)
    mix = np.zeros((total, 2))
    put_phrase(mix, MOTIF, 0.15, 0.7)
    place(mix, brass([62, 69, 74, 77], 3.0 * BEAT + 1.2), 0.15 + 3 * BEAT, 0.35)  # ré mineur tenu sous la dernière note
    place(mix, mm.kick(), 0.15 + 3 * BEAT, 0.8)
    d = int(BEAT * 0.75 * SR)
    mix[d:] += 0.25 * mix[:-d]
    mix *= envelope(total, 0.01, 1.2)[:, None]
    return mix / np.abs(mix).max() * 0.85


def theme(rounds=2):
    """Thème complet : 8 mesures (motif, réponse A, motif, réponse B) répétées, avec batterie et basse."""
    bars = len(CHORDS) * rounds
    total = int((bars * BAR + 3) * SR)
    mix = np.zeros((total, 2))
    for b in range(bars):
        b0 = b * BAR
        root, notes = CHORDS[b % len(CHORDS)]
        intro = b < 2
        p = mm.pad(notes, BAR + 0.8) * 0.3
        i = int(b0 * SR)
        mix[i:i + len(p)] += p[: total - i]
        for beat in range(4):
            t = b0 + beat * BEAT
            place(mix, mm.kick(), t, 0.85 if beat in (0, 2) else 0.0)
            if beat in (1, 3) and not intro:
                place(mix, mm.snap(), t, 0.32, 0.55)
            for half in (0, 1):
                place(mix, mm.hat(open_=(half == 1 and beat == 3)), t + half * BEAT / 2, 0.1 if half else 0.06, 0.65)
        for step in range(8):
            n = root + (12 if step in (3, 7) else 0)
            place(mix, mm.bass(n if n >= 40 else n + 12, BEAT / 2 * 0.95), b0 + step * BEAT / 2, 0.5)
        k = b % 8  # phrases de la mélodie, sur 2 mesures chacune
        if k in (0, 4):
            put_phrase(mix, MOTIF, b0)
        elif k == 1:
            pass  # la note longue du motif déborde sur cette mesure
        elif k == 2:
            put_phrase(mix, ANSWER_A, b0)
        elif k == 6:
            put_phrase(mix, ANSWER_B, b0)
    d = int(BEAT * 0.75 * SR)
    mix[d:] += 0.22 * mix[:-d]
    mix *= envelope(total, 0.4, 2.5)[:, None]
    return mix / np.abs(mix).max() * 0.82


if __name__ == "__main__":
    save(jingle(), "jingle-kulturable")
    save(theme(), "theme-kulturable")
