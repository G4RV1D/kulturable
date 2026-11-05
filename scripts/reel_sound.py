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
SIGNATURE = "b"  # "a" : trois accords ; "b" : cascade lydienne ; "c" : la porte qui s'ouvre
rng = np.random.default_rng(1887)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a, r):
    e = np.ones(n)
    na, nr = min(int(a * SR), n), min(int(r * SR), n)
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


def signature_b(seconds):
    """Signature de la page : une basse qui glisse vers le grave, puis un grand accord fa maj7(#11) qui s'ouvre, respire
    et s'éteint lentement jusqu'à la fin."""
    out = np.zeros(int(seconds * SR))
    land = 0.05  # pas de montée : la basse et le grand accord arrivent directement
    # basse qui glisse du fa vers le fa grave
    n = int(min(seconds - land, 3.0) * SR)
    tt = np.arange(n) / SR
    f = hz(41) * (1 + 0.5 * np.exp(-tt * 9))
    bass = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    put(out, bass * np.exp(-tt * 0.8) * env(n, 0.005, 0.4), land, 0.35)
    # le grand accord qui s'ouvre (filtre qui s'éclaircit en le tenant)
    length = seconds - land
    for v in (0, 7, 11, 16, 18, 23):  # fa, do, mi, la, si (la quarte augmentée), mi
        nn = int(length * SR)
        x = saw(hz(53 + v), nn, 0.006)
        cut = np.linspace(700, 3800, nn)
        y = np.zeros(nn)
        for c0 in range(0, nn, 2048):  # filtre qui s'ouvre progressivement
            b, a = butter(2, cut[c0] / (SR / 2), "low")
            y[c0:c0 + 2048] = lfilter(b, a, x[c0:c0 + 2048])
        put(out, y * env(nn, 0.25, length * 0.85), land, 0.075)  # la note de fond s'éteint lentement
    return echo(out, 0.25, 0.3, 0.3)[: len(out)]


def lead(m_from, m_to, length, glide=0.06):
    """Lead de synthé : dent de scie + carré, petit glissando d'attaque et léger vibrato."""
    n = int(length * SR)
    t = np.arange(n) / SR
    f0, f1 = hz(m_from), hz(m_to)
    f = f1 + (f0 - f1) * np.exp(-t / glide)
    f = f * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = sum(np.sin(k * ph) / k for k in range(1, 18)) * 0.7 + np.sign(np.sin(ph)) * 0.15
    b, a = butter(2, 3200 / (SR / 2), "low")
    return lfilter(b, a, x) * env(n, 0.01, 0.12)


def signature_c(seconds):
    """Variante C, « la porte qui s'ouvre » : une nappe suspendue qui enfle, la mélodie de la chaîne
    (ré-la-fa-mi) jouée par un lead de synthé, puis la résolution en ré majeur : le mystère s'éclaire."""
    out = np.zeros(int(seconds * SR))
    sw = 0.7  # nappe suspendue (ré sus4) qui enfle
    for v in (0, 5, 7, 12):
        nn = int((sw + 0.3) * SR)
        x = saw(hz(50 + v), nn, 0.006)
        b, a = butter(2, 1600 / (SR / 2), "low")
        put(out, lfilter(b, a, x) * np.linspace(0, 1, nn) ** 2 * env(nn, 0, 0.3), 0, 0.09)
    prev = 74
    for k, m in enumerate((74, 81, 77, 76)):  # ré la fa mi
        put(out, lead(prev, m, 0.34 if k < 3 else 0.5), sw + k * 0.3, 0.16)
        prev = m
    res = sw + 4 * 0.3 + 0.12
    length = seconds - res
    for v in (0, 4, 7, 14, 16):  # ré majeur ajouté neuvième : l'éclaircie
        put(out, analog(62 + v, length, 3000, attack=0.04, release=min(1.8, length * 0.6), detune=0.007), res, 0.10)
    put(out, lead(74, 78, length * 0.8, glide=0.08), res, 0.10)  # le lead monte sur la tierce majeure
    put(out, analog(38, length, 360, attack=0.01, release=1.0, decay=0.9), res, 0.45)
    shine = sum(analog(86 + v, 0.8, 6000, decay=3, kind="pulse") * 0.6 ** j for j, v in enumerate((0, 4, 7, 12)))
    put(out, shine, res + 0.15, 0.06)
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
        if landed and i >= 8:  # l'accord final ne relance pas l'arpège : il se termine
            break
        if i % 8 == 0:
            span = (story_end - t) if landed else min(step * 8 + 0.6, story_end - t)
            rel = min(1.2, span * 0.5) if landed else 0.6
            for v in iv[:3]:
                put(music, analog(root + 12 + v, span, 1400, attack=0.6 if not landed else 0.2,
                                  release=rel, detune=0.006), t, 0.10)
            put(music, analog(root - 12, span, 380, attack=0.08, release=rel), t, 0.30)
        prog = min(1.0, t / max(1.0, hit_at))
        put(music, analog(root + 24 + iv[pattern[i % 8]], step * 1.4, 1500 + 2500 * prog, decay=4, kind="pulse"), t, 0.16)
        t += step
        i += 1
    music = echo(music, delay=step * 1.5, fb=0.35, mix=0.3)[: len(music)]
    music *= env(len(music), 0.08, 0.35)  # l'accord s'éteint juste avant l'écran de fin
    put(mix, music, 0, 1.0)
    if total - story_end > 0.5:
        put(mix, {"b": signature_b, "c": signature_c}.get(SIGNATURE, signature)(total - story_end), story_end, 1.1)
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


def make_loop(total, cuts, radio_cut, out):
    """Son en boucle parfaite (Reel sans écran de fin) : nappe grave continue, battement sourd,
    bips radio de la NASA (tonalités Quindar) à chaque plan, grésillement puis radio coupée.
    La fin se raccorde exactement au début : la traîne est repliée sur les premières secondes."""
    extra = 2.0
    n = int(total * SR)
    mix = np.zeros(int((total + extra) * SR))
    tt = np.arange(len(mix)) / SR
    lfo = 1 + 0.2 * np.sin(2 * np.pi * tt / total)  # période = durée du Reel : se raccorde
    bass = lfilter(*butter(2, 260 / (SR / 2), "low"), saw(hz(29), len(mix), 0.004)) * 0.55
    pad = sum(lfilter(*butter(2, 900 / (SR / 2), "low"), saw(hz(53 + v), len(mix), 0.006)) for v in (0, 7, 16, 23)) * 0.07
    pe = np.ones(len(mix))  # la nappe s'efface quand la radio est coupée, revient avant la boucle
    i0, i1 = int(radio_cut * SR), int((radio_cut + 0.12) * SR)
    pe[i0:i1] = np.linspace(1, 0.12, i1 - i0)
    pe[i1:] = 0.12
    r0, r1 = int((total - 0.9) * SR), n
    pe[r0:r1] = np.linspace(0.12, 1, r1 - r0)
    pe[r1:] = 1
    mix += (bass + pad) * lfo * pe
    beat = 60 / 72  # battement de cœur, tombe juste sur la durée
    for k in range(int(round(total / beat)) + 3):
        for off, g in ((0, 0.55), (0.22, 0.35)):
            t = np.arange(int(0.35 * SR)) / SR
            put(mix, np.sin(2 * np.pi * (48 * np.exp(-t * 6) + 34) * t) * np.exp(-t * 14), k * beat * total / (round(total / beat) * beat) + off, g)
    for c in cuts:  # bip radio d'Apollo, discret
        t = np.arange(int(0.22 * SR)) / SR
        put(mix, np.sin(2 * np.pi * 2525 * t) * env(len(t), 0.005, 0.03), c, 0.05)
    t = np.arange(int(0.55 * SR)) / SR  # grésillement puis silence radio
    stat = lfilter(*butter(2, [900 / (SR / 2), 5000 / (SR / 2)], "band"), rng.standard_normal(len(t)))
    put(mix, stat * (0.5 + 0.5 * (rng.random(len(t)) > 0.6)) * env(len(t), 0.01, 0.25), radio_cut - 0.15, 0.35)
    mix = reverb(mix, 2.0, 0.25)
    loop = mix[:n].copy()
    tail = mix[n:]
    loop[: len(tail)] += tail  # la traîne de la fin se prolonge sur le début : raccord invisible
    loop /= np.abs(loop).max() / 0.89
    pcm = (np.stack([loop, loop], 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out


if __name__ == "__main__":
    make(float(sys.argv[1]), float(sys.argv[2]), sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else None)
