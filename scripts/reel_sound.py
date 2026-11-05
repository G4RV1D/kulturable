"""Son de fond des Reels Kulturable : synthés analogiques années 80, mystérieux et fascinants (sans angoisse), avec une chute lumineuse.

Construction (composition originale, aucune source extérieure) :
- un souffle grave en ré qui tient tout le Reel (nappe + air filtré) ;
- la mélodie de la chaîne à la boîte à musique : ré-la-fa-mi-ré-do#-ré ;
- une montée de tension dans la seconde et demie qui précède la dernière diapositive ;
- la chute : silence bref, impact sourd et grave pile sur la dernière diapositive,
  puis un ré aigu isolé qui résonne jusqu'à la fin.

Usage : python scripts/reel_sound.py <durée> <instant_chute> <sortie.wav>
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter

SR = 44100
rng = np.random.default_rng(1887)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def music_box(m, length=2.4):
    t = np.arange(int(length * SR)) / SR
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
         + 0.15 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 9))
    return s * np.exp(-t * 2.2) * env(len(t), 0.002, 0.05)


def drone(seconds):
    t = np.arange(int(seconds * SR)) / SR
    lfo = 1 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
    s = (np.sin(2 * np.pi * hz(38) * t) * 0.6 + np.sin(2 * np.pi * hz(45) * t) * 0.25
         + np.sin(2 * np.pi * hz(50) * t + 0.4 * np.sin(2 * np.pi * 0.2 * t)) * 0.15) * lfo
    b, a = butter(2, 900 / (SR / 2), "low")
    air = lfilter(b, a, rng.standard_normal(len(t))) * 0.05
    return (s * 0.5 + air) * env(len(t), 1.2, 0.3)


def riser(seconds):
    t = np.arange(int(seconds * SR)) / SR
    p = t / seconds
    noise = rng.standard_normal(len(t))
    b, a = butter(2, [800 / (SR / 2), 7000 / (SR / 2)], "band")
    noise = lfilter(b, a, noise) * p ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(hz(50) * 2 ** (p * 2)) / SR) * p ** 2 * 0.4
    return (noise * 0.35 + tone) * env(len(t), 0.0, 0.02)


def impact(seconds=3.0):
    t = np.arange(int(seconds * SR)) / SR
    f = 55 * np.exp(-t * 1.8) + 32
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6)
    click = rng.standard_normal(len(t)) * np.exp(-t * 60) * 0.5
    low = sum(np.sin(2 * np.pi * hz(m) * t) for m in (38, 45, 50)) * np.exp(-t * 1.4) * 0.25
    return (boom * 1.1 + click + low) * env(len(t), 0.001, 0.3)


def reverb(x, seconds=2.6, wet=0.35):
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    b, a = butter(1, 5000 / (SR / 2), "low")
    ir = lfilter(b, a, ir)
    ir /= np.abs(ir).sum() ** 0.5 * 4
    return x + wet * fftconvolve(x, ir)[: len(x)]


def put(mix, sig, at, gain=1.0):
    i = int(at * SR)
    if i >= len(mix):
        return
    j = min(len(mix), i + len(sig))
    mix[i:j] += sig[: j - i] * gain


def saw(f, n, detune=0.0):
    """Dent de scie adoucie (somme d'harmoniques), deux oscillateurs légèrement désaccordés."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in (-detune, detune):
        ff = f * (1 + d)
        for k in range(1, int(min(40, (SR / 2) / ff))):
            out += np.sin(2 * np.pi * k * ff * t) / k
    return out / 2


def synth_note(m, length, cutoff, decay=3.0):
    n = int(length * SR)
    x = saw(hz(m), n, 0.004)
    b, a = butter(2, min(cutoff, 16000) / (SR / 2), "low")
    x = lfilter(b, a, x)
    t = np.arange(n) / SR
    return x * np.exp(-t * decay) * env(n, 0.004, 0.03)


def echo(x, delay=0.27, fb=0.35, mix=0.35):
    d = int(delay * SR)
    y = np.concatenate([x, np.zeros(d * 4)])
    for k in range(1, 5):
        y[d * k: d * k + len(x)] += x * (fb ** k) * mix / fb
    return y


def pulse(f, n, width=0.35):
    """Onde rectangulaire adoucie (somme d'harmoniques), timbre des synthés analogiques."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(1, int(min(30, (SR / 2) / f))):
        out += np.sin(np.pi * k * width) / k * np.cos(2 * np.pi * k * f * t)
    return out


def analog(m, length, cutoff, attack=0.005, release=0.05, decay=0.0, kind="saw", detune=0.003):
    n = int(length * SR)
    x = saw(hz(m), n, detune) if kind == "saw" else pulse(hz(m), n)
    b, a = butter(2, min(cutoff, 15000) / (SR / 2), "low")
    x = lfilter(b, a, x)
    t = np.arange(n) / SR
    e = env(n, attack, release)
    if decay:
        e *= np.exp(-t * decay)
    return x * e


def signature(seconds):
    """Signature sonore de la page : trois accords de synthé analogique qui montent
    (fa maj7, la m9, do maj9), le dernier tenu avec écho jusqu'à la fin."""
    out = np.zeros(int(seconds * SR))
    chords = [(53, [0, 4, 7, 11]), (57, [0, 3, 7, 14]), (60, [0, 4, 7, 14])]
    starts = [0.0, 0.42, 0.84]
    for k, ((root, iv), at) in enumerate(zip(chords, starts)):
        length = (starts[k + 1] - at + 0.25) if k < 2 else seconds - at
        rel = 0.25 if k < 2 else min(2.0, length * 0.6)
        for v in iv:
            put(out, analog(root + v, length, 1800 + 900 * k, attack=0.02, release=rel, detune=0.006), at, 0.13)
        put(out, analog(root - 12, length, 420, attack=0.01, release=rel), at, 0.30)
    shine = sum(analog(84 + v, 0.7, 5500, decay=3, kind="pulse") * 0.6 ** j for j, v in enumerate((0, 7, 12)))
    put(out, shine, starts[2] + 0.05, 0.08)
    return echo(out, 0.30, 0.4, 0.4)[: len(out)]


def make(total, hit_at, out, story_end=None):
    """Synthés analogiques des années 80 (composition originale) : nappe chaude, arpège qui scintille,
    basse ronde. Sur la dernière diapositive, la musique revient sur l'accord de départ et le laisse
    se terminer proprement. Au passage à l'écran de fin : la signature de la page en trois accords."""
    story_end = story_end or total
    mix = np.zeros(int(total * SR))
    step = 60 / 96 / 2  # croches à 96 battements par minute
    chords = [(53, [0, 4, 7, 11]), (50, [0, 3, 7, 14]), (46, [0, 4, 7, 11]), (48, [0, 4, 9, 14])]
    pattern = [0, 2, 3, 1, 2, 3, 2, 1]
    final = (53, [0, 4, 7, 14])
    music = np.zeros(int(story_end * SR))
    t, i, landed = 0.1, 0, False
    while t < story_end - step * 0.5:
        if t >= hit_at - 0.01 and not landed:
            landed, i = True, 0
        root, iv = final if landed else chords[(i // 8) % 4]
        if i % 8 == 0:
            span = (story_end - t) if landed else min(step * 8 + 0.6, story_end - t)
            rel = min(1.2, span * 0.5) if landed else 0.6
            for v in iv[:3]:
                put(music, analog(root + 12 + v, span, 1400, attack=0.6 if not landed else 0.2,
                                  release=rel, detune=0.006), t, 0.10)
            put(music, analog(root - 12, span, 380, attack=0.08, release=rel), t, 0.30)
        if landed and i >= 8:  # l'accord final ne relance pas l'arpège : il se termine
            break
        prog = min(1.0, t / max(1.0, hit_at))
        put(music, analog(root + 24 + iv[pattern[i % 8]], step * 1.4, 1500 + 2500 * prog, decay=4, kind="pulse"), t, 0.16)
        t += step
        i += 1
    music = echo(music, delay=step * 1.5, fb=0.35, mix=0.3)[: len(music)]
    music *= env(len(music), 0.08, 0.35)  # l'accord s'éteint juste avant l'écran de fin
    put(mix, music, 0, 1.0)
    if total - story_end > 0.5:
        put(mix, signature(total - story_end), story_end, 1.1)
    mix = reverb(mix, 2.4, 0.3)
    mix *= env(len(mix), 0.05, 0.5)
    mix /= np.abs(mix).max() / 0.89
    pcm = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out


if __name__ == "__main__":
    make(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else None)
