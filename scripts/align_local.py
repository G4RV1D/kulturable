"""Alignement forcé texte / voix sans modèle de reconnaissance vocale.

Principe : on détecte dans la voix les passages parlés (séparés par des pauses) et les
noyaux syllabiques (pics d'énergie voisés), puis on aligne le texte, dont on connaît le
nombre de syllabes de chaque mot, par programmation dynamique. Les pauses tombent de
préférence sur la ponctuation. Produit une liste de mots horodatés.
"""
import re
import subprocess
import unicodedata

import imageio_ffmpeg
import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt

SR = 16000
HOP = 0.010
VOW = "aeiouyàâäéèêëîïôöùûüœæ"

UNITS = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
         "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def fr_number(n: int) -> str:
    if n < 20:
        return UNITS[n]
    if n < 70:
        t, u = divmod(n, 10)
        return TENS[t] + ("" if u == 0 else (" et un" if u == 1 else " " + UNITS[u]))
    if n < 80:
        return "soixante " + fr_number(n - 60)
    if n < 100:
        return "quatre vingt" + ("" if n == 80 else " " + fr_number(n - 80))
    if n < 1000:
        c, r = divmod(n, 100)
        return ("cent" if c == 1 else UNITS[c] + " cent") + ("" if r == 0 else " " + fr_number(r))
    if n < 2000:
        return "mille" + ("" if n == 1000 else " " + fr_number(n - 1000))
    m, r = divmod(n, 1000)
    return fr_number(m) + " mille" + ("" if r == 0 else " " + fr_number(r))


def spoken(word: str) -> str:
    w = word.lower()

    def num(m):
        s = m.group(0)
        if len(s) == 4 and 1100 <= int(s) <= 1999:  # années : « dix-sept cent quatre-vingt-dix-neuf »
            return fr_number(int(s[:2])) + " cent " + (fr_number(int(s[2:])) if int(s[2:]) else "")
        return fr_number(int(s))
    w = re.sub(r"\d+", num, w)
    w = re.sub(r"\bp\b", "pé", w)
    return w


def syllables(word: str) -> float:
    w = spoken(word)
    w = re.sub(r"[^a-z" + VOW + r" '-]", "", w)
    total = 0.0
    for part in re.split(r"[ '-]+", w):
        if not part:
            continue
        groups = re.findall(f"[{VOW}]+", part)
        n = len(groups)
        if n > 1 and re.search(r"(e|es|ent)$", part) and not re.search(r"(é|ée|ées|ent)$", part[-3:] if part.endswith("ent") and len(part) <= 4 else "x"):
            n -= 0.6  # e muet final, souvent non prononcé
        total += max(n, 0.5)
    return max(total, 0.6)


# ---------- analyse du signal ----------

def load(path) -> np.ndarray:
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def analyse(x: np.ndarray):
    sos = butter(4, [300, 3000], btype="band", fs=SR, output="sos")
    xb = sosfiltfilt(sos, x)
    win, hop = int(0.025 * SR), int(HOP * SR)
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    fr = xb[idx] * np.hanning(win)
    db = 10 * np.log10((fr ** 2).mean(axis=1) + 1e-10)
    db = np.convolve(db, np.ones(3) / 3, mode="same")
    floor, top = np.percentile(db, 10), np.percentile(db, 97)
    thr = floor + 0.30 * (top - floor)
    speech = db > thr
    # voisement : autocorrélation normalisée dans la plage de la voix (70–400 Hz)
    raw = x[idx]
    raw = raw - raw.mean(axis=1, keepdims=True)
    lo, hi = SR // 400, SR // 70
    f = np.fft.rfft(raw, 2 * win, axis=1)
    ac = np.fft.irfft(f * np.conj(f), axis=1)[:, :win]
    voiced = ac[:, lo:hi].max(axis=1) / (ac[:, 0] + 1e-9)
    peaks, _ = find_peaks(db, prominence=2.0, distance=7, height=thr + 2)
    peaks = peaks[voiced[peaks] > 0.30]
    return db, speech, peaks, thr


def runs_from(speech: np.ndarray, min_pause=0.16, min_run=0.08):
    s = speech.astype(int)
    edges = np.flatnonzero(np.diff(np.r_[0, s, 0]))
    segs = [[a * HOP, b * HOP] for a, b in zip(edges[::2], edges[1::2])]
    merged = []
    for a, b in segs:
        if merged and a - merged[-1][1] < min_pause:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [r for r in merged if r[1] - r[0] >= min_run]


# ---------- alignement ----------

def align(paras: list, audio_path):
    x = load(audio_path)
    db, speech, peaks, thr = analyse(x)
    runs = runs_from(speech)
    ptimes = peaks * HOP
    nuclei = [ptimes[(ptimes >= a) & (ptimes <= b)] for a, b in runs]

    words = []
    for p, text in enumerate(paras):
        for raw in text.split():
            core = re.sub(r"^[«(\"]+|[»)\".,:;!?…]+$", "", raw)
            if not core:
                if words:
                    words[-1]["t"] += " " + raw
                    words[-1]["brk"] = 2
                continue
            words.append({"t": raw, "p": p, "syl": syllables(core),
                          "brk": 2 if re.search(r"[.!?…:;]$", raw) else (1 if raw.endswith(",") else 0)})
        words[-1]["brk"] = 3  # fin de paragraphe
    W, R = len(words), len(runs)
    cum = np.r_[0, np.cumsum([w["syl"] for w in words])]
    total_syl, total_nuc = cum[-1], sum(len(n) for n in nuclei)
    rate = total_nuc / total_syl if total_syl else 1  # noyaux détectés par syllabe écrite
    speech_time = sum(b - a for a, b in runs)
    sps = total_syl / speech_time  # syllabes écrites par seconde de parole

    INF = 1e18
    # best[r][w] : coût minimal si les runs 0..r-1 couvrent les mots 0..w-1
    best = np.full((R + 1, W + 1), INF)
    back = np.zeros((R + 1, W + 1), dtype=int)
    best[0][0] = 0
    MAXW = 45
    for r in range(R):
        a, b = runs[r]
        dur = b - a
        n_nuc = len(nuclei[r])
        gap_after = runs[r + 1][0] - b if r + 1 < R else 9
        for w0 in range(W + 1):
            if best[r][w0] >= INF:
                continue
            for w1 in range(w0 + 1, min(W, w0 + MAXW) + 1):
                syl = cum[w1] - cum[w0]
                exp_n = syl * rate
                c = ((n_nuc - exp_n) ** 2) / max(2.0, exp_n) * 1.0
                c += ((dur * sps - syl) ** 2) / max(2.0, syl) * 0.6
                brk = words[w1 - 1]["brk"]
                # une pause doit tomber sur une ponctuation ; une longue pause plutôt en fin de phrase
                c += {0: 6.0, 1: 1.0, 2: 0.0, 3: 0.0}[brk] * (1.0 + min(gap_after, 1.5))
                if gap_after > 0.9 and brk < 2:
                    c += 4.0
                tot = best[r][w0] + c
                if tot < best[r + 1][w1]:
                    best[r + 1][w1] = tot
                    back[r + 1][w1] = w0
        # un run peut aussi être un bruit sans mot (souffle, clic) : coût fixe
        for w0 in range(W + 1):
            if best[r][w0] < INF and len(nuclei[r]) <= 1 and dur < 0.35:
                tot = best[r][w0] + 3.0
                if tot < best[r + 1][w0]:
                    best[r + 1][w0] = tot
                    back[r + 1][w0] = w0
    if best[R][W] >= INF:
        raise RuntimeError("alignement impossible")
    # remontée
    assign, w1 = [], W
    for r in range(R, 0, -1):
        w0 = back[r][w1]
        assign.append((r - 1, w0, w1))
        w1 = w0
    assign.reverse()

    # horaires à l'intérieur de chaque run, calés sur les noyaux syllabiques
    for r, w0, w1 in assign:
        if w0 == w1:
            continue
        a, b = runs[r]
        nuc = np.sort(nuclei[r])
        syl = cum[w1] - cum[w0]
        if len(nuc) >= 2:
            # bornes syllabiques : début du run, milieux entre noyaux, fin du run
            knots_t = np.r_[a, (nuc[:-1] + nuc[1:]) / 2, b]
            knots_x = np.linspace(0, syl, len(knots_t))
        else:
            knots_t, knots_x = np.array([a, b]), np.array([0, syl])
        for k in range(w0, w1):
            words[k]["s"] = float(np.interp(cum[k] - cum[w0], knots_x, knots_t))
            words[k]["e"] = float(np.interp(cum[k + 1] - cum[w0], knots_x, knots_t))
    info = {"runs": len(runs), "noyaux": int(total_nuc), "syllabes_texte": round(float(total_syl), 1),
            "noyaux_par_syllabe": round(float(rate), 2), "cout": round(float(best[R][W]), 1),
            "parole_s": round(speech_time, 1)}
    per_run = [(round(runs[r][0], 2), round(runs[r][1], 2), len(nuclei[r]),
                " ".join(words[k]["t"] for k in range(w0, w1))) for r, w0, w1 in assign]
    return [{"w": w["t"], "s": round(w["s"], 3), "e": round(w["e"], 3), "p": w["p"]} for w in words], info, per_run
