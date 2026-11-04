"""Son de fond des Reels Kulturable : mystérieux, reconnaissable, avec une chute.

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


def make(total, hit_at, out):
    mix = np.zeros(int(total * SR))
    put(mix, drone(total), 0, 0.55)
    # la mélodie de la chaîne, une fois, en ouverture
    beat = 0.36
    for m, b in [(74, 0), (81, 1), (77, 2), (76, 2.5), (74, 3), (73, 3.5), (74, 4)]:
        put(mix, music_box(m + 12 if m < 76 else m), 0.25 + b * beat * 1.6, 0.28)
    # quelques notes suspendues ensuite, de plus en plus rares
    t, k = 0.25 + 4 * beat * 1.6 + 1.2, 0
    while t < hit_at - 2.0:
        put(mix, music_box([81, 77, 76, 73][k % 4]), t, 0.18)
        t += 1.3 + 0.3 * k
        k += 1
    # montée, silence, chute
    put(mix, riser(1.5), hit_at - 1.55, 0.6)
    gap = slice(int((hit_at - 0.08) * SR), int(hit_at * SR))
    mix[gap] *= 0.1
    put(mix, impact(), hit_at, 0.9)
    put(mix, music_box(86, 4.0), hit_at + 0.35, 0.3)
    mix = reverb(mix)
    mix *= env(len(mix), 0.05, 0.6)
    mix /= np.abs(mix).max() / 0.89
    pcm = (np.stack([mix, mix], 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out


if __name__ == "__main__":
    make(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3])
