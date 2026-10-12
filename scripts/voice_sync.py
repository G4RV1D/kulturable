"""Synchronisation exacte voix / texte / sous-titres.

1. Transcription mot par mot de la voix (faster-whisper), mise en cache dans transcription.json.
2. Alignement des mots prononcés sur le texte écrit (script.txt) :
   - mots identiques : on garde l'orthographe et la ponctuation du texte, avec les horaires réels ;
   - mots mal reconnus : orthographe du texte, horaires de la voix ;
   - mots dits en plus : on garde ce qui a été dit ;
   - hésitations (« euh ») et phrases reprises : retirées de l'audio.
3. Montage de la voix : blancs trop longs raccourcis, coupes adoucies (fondus de 10 ms).
Résultat : une voix montée (voix_montee.wav) et la liste des mots avec leurs horaires dans ce nouveau montage.
"""
import difflib
import hashlib
import json
import pathlib
import re
import subprocess
import unicodedata
import wave

import imageio_ffmpeg
import numpy as np

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SR = 48000
FILLERS = {"euh", "heu", "hum", "hmm", "bah", "ben", "euhm", "mmh"}
GAP_IN = 0.40      # blanc maximal à l'intérieur d'un paragraphe
GAP_PARA = 0.70    # blanc maximal entre deux paragraphes
LEAD, TAIL = 0.15, 0.8


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t)


def script_tokens(paras: list) -> list:
    toks = []
    for p, text in enumerate(paras):
        for raw in text.split():
            if not norm(raw) and toks and toks[-1]["p"] == p:
                toks[-1]["t"] += " " + raw  # ponctuation isolée (« : », « … ») collée au mot précédent
                continue
            toks.append({"t": raw, "n": norm(raw), "p": p})
    return [t for t in toks if t["n"]]


# ---------- 1. transcription ----------

def transcribe(folder: pathlib.Path, voice: pathlib.Path, paras: list):
    cache = folder / "transcription.json"
    key = hashlib.sha256(voice.read_bytes()).hexdigest()
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("voice_sha") == key:
            return data["words"]
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    rare = sorted({w.strip(".,:;!?…«»()") for p in paras for w in p.split()
                   if any(c.isdigit() for c in w) or w[:1].isupper() or len(w) > 9})
    prompt = "Vocabulaire : " + ", ".join(rare)[:600]
    import os
    model = WhisperModel(os.environ.get("WHISPER_MODEL", "medium"), device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(voice), language="fr", word_timestamps=True,
                                   initial_prompt=prompt, beam_size=5, condition_on_previous_text=False)
    words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
             for seg in segments for w in (seg.words or []) if w.word.strip()]
    cache.write_text(json.dumps({"voice_sha": key, "words": words}, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    return words


# ---------- 2. alignement ----------

def align(paras: list, words: list, report: list) -> list:
    A = script_tokens(paras)
    B = [dict(w, n=norm(w["w"])) for w in words if norm(w["w"])]
    sm = difflib.SequenceMatcher(None, [a["n"] for a in A], [b["n"] for b in B], autojunk=False)
    out = []
    last_p = 0

    def add(text, s, e, p, keep=True):
        out.append({"t": text, "s": s, "e": e, "p": p, "keep": keep})

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for a, b in zip(A[i1:i2], B[j1:j2]):
                add(a["t"], b["s"], b["e"], a["p"])
                last_p = a["p"]
        elif op == "replace":
            sa = " ".join(a["n"] for a in A[i1:i2])
            sb = " ".join(b["n"] for b in B[j1:j2])
            ratio = difflib.SequenceMatcher(None, sa, sb).ratio()
            if ratio >= 0.55 or (i2 - i1 <= 3 and j2 - j1 <= 3 and ratio >= 0.4):
                # mal reconnu : orthographe du texte, réparti sur la durée réellement prononcée
                s0, e0 = B[j1]["s"], B[j2 - 1]["e"]
                tot = sum(len(a["n"]) for a in A[i1:i2]) or 1
                acc = 0
                for a in A[i1:i2]:
                    s = s0 + (e0 - s0) * acc / tot
                    acc += len(a["n"])
                    add(a["t"], s, s0 + (e0 - s0) * acc / tot, a["p"])
                    last_p = a["p"]
            else:
                report.append(f"Dit autrement que le texte : « {' '.join(b['w'] for b in B[j1:j2])} »"
                              f" au lieu de « {' '.join(a['t'] for a in A[i1:i2])} »")
                p = A[i1]["p"]
                for b in B[j1:j2]:
                    add(b["w"], b["s"], b["e"], p)
                last_p = p
        elif op == "insert":
            seg = B[j1:j2]
            ns = [b["n"] for b in seg]
            nxt = [a["n"] for a in A[i1:i1 + len(ns)]]
            prv = [a["n"] for a in A[max(0, i1 - len(ns)):i1]]
            dup = len(ns) >= 2 and max(difflib.SequenceMatcher(None, ns, nxt).ratio(),
                                       difflib.SequenceMatcher(None, ns, prv).ratio()) >= 0.75
            if dup or all(n in FILLERS for n in ns):
                kind = "phrase reprise" if dup else "hésitation"
                report.append(f"Coupé ({kind}) à {seg[0]['s']:.1f} s : « {' '.join(b['w'] for b in seg)} »")
                for b in seg:
                    add(b["w"], b["s"], b["e"], last_p, keep=False)
            else:
                report.append(f"Ajouté à l'oral (gardé) : « {' '.join(b['w'] for b in seg)} »")
                for b in seg:
                    add(b["w"], b["s"], b["e"], last_p)
        elif op == "delete":
            report.append(f"Non prononcé (retiré des sous-titres) : « {' '.join(a['t'] for a in A[i1:i2])} »")
    out.sort(key=lambda x: x["s"])
    return out


# ---------- 3. montage de la voix ----------

def load_pcm(path: pathlib.Path) -> np.ndarray:
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32)


def edit(voice: pathlib.Path, tokens: list, out_wav: pathlib.Path, report: list):
    pcm = load_pcm(voice)
    dur = len(pcm) / SR
    kept = [t for t in tokens if t["keep"]]
    # intervalles conservés, dans le temps d'origine
    spans = [[max(0.0, kept[0]["s"] - LEAD), None]]
    for a, b in zip(kept, kept[1:]):
        gap = b["s"] - a["e"]
        limit = GAP_PARA if a["p"] != b["p"] else GAP_IN
        removed = any((not t["keep"]) and a["e"] <= t["s"] < b["s"] for t in tokens)
        if gap > limit or removed:
            half = min(gap, limit) / 2
            spans[-1][1] = a["e"] + half
            spans.append([b["s"] - half, None])
    spans[-1][1] = min(dur, kept[-1]["e"] + TAIL)
    # assemblage avec de courts fondus pour éviter les clics
    fade = int(0.010 * SR)
    pieces, mapping, t_new = [], [], 0.0
    for s, e in spans:
        seg = pcm[int(s * SR):int(e * SR)].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade)
            seg[-fade:] *= np.linspace(1, 0, fade)
        mapping.append((s, e, t_new))
        t_new += len(seg) / SR
        pieces.append(seg)
    audio = np.concatenate(pieces)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(audio, -32768, 32767).astype(np.int16).tobytes())

    def remap(t):
        for s, e, n in mapping:
            if t <= e:
                return n + max(0.0, t - s)
        return t_new

    for t in kept:
        t["s"], t["e"] = remap(t["s"]), remap(t["e"])
    report.append(f"Voix : {dur:.1f} s à l'origine, {t_new:.1f} s après montage "
                  f"({len(spans) - 1} blancs raccourcis ou passages coupés).")
    return kept, t_new


def sync(folder: pathlib.Path, voice: pathlib.Path, paras: list):
    """Retourne (voix montée, mots horodatés, durée) ou None si la transcription est indisponible."""
    words = transcribe(folder, voice, paras)
    if not words:
        return None
    report = []
    tokens = align(paras, words, report)
    out_wav = folder / "_voix_montee.wav"
    kept, total = edit(voice, tokens, out_wav, report)
    (folder / "montage.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    return out_wav, kept, total
