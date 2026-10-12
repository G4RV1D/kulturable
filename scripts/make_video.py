"""Monte une vidéo TikTok verticale (1080 x 1920) à partir d'un dossier tiktok/<id>/.

Contenu du dossier :
  script.txt   le texte lu, un paragraphe par plan (séparés par une ligne vide)
  video.json   les images de chaque plan (sources, recadrage, sens du zoom)
  voix.*       (facultatif) l'enregistrement de la voix : m4a, mp3, wav, ogg, aac, opus
  musique.*    (facultatif) une musique unique pour toute la vidéo.
Par défaut : musique calme (music/ambiance-01) pendant l'accroche (1er paragraphe),
puis musique rythmée (music/rythme-01) pour l'explication, avec un fondu entre les deux.
Dans video.json : "music": null pour aucune musique, "music": "nom" pour une seule,
ou "music": {"intro": "nom", "main": "nom", "switch_after": 1}.

Sans voix, le script produit apercu.mp4, muet, au rythme d'une lecture normale.
Avec la voix, il produit video.mp4 : chaque plan dure à proportion de son texte.

Usage : python scripts/make_video.py tiktok/01-disque-rosetta [--force]
"""
import hashlib
import io
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "fonts" / "Poppins-Bold.ttf"
W, H, FPS = 1080, 1920, 30
ZOOM = 1.12          # amplitude du lent mouvement de caméra
WORDS_PER_SEC = 2.6  # rythme de lecture pour l'aperçu sans voix
UA = "KulturablePublisher/1.0 (+https://github.com)"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


# ---------- entrées ----------

def paragraphs(folder: pathlib.Path) -> list:
    text = (folder / "script.txt").read_text(encoding="utf-8").strip()
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def find_voice(folder: pathlib.Path):
    for ext in ("m4a", "mp3", "wav", "ogg", "aac", "opus", "webm"):
        for f in folder.glob(f"voix*.{ext}"):
            return f
    return None


DEFAULT_MUSIC = {"intro": "ambiance-01", "main": "rythme-01", "switch_after": 1}


def find_music(folder: pathlib.Path, spec: dict):
    """Retourne (musique d'accroche, musique principale, n° du paragraphe de bascule) ou None."""
    if "music" in spec and spec["music"] is None:
        return None
    for ext in ("m4a", "mp3", "wav", "ogg", "aac"):
        for f in folder.glob(f"musique*.{ext}"):
            return (f, None, None)
    m = spec.get("music", DEFAULT_MUSIC)
    path = lambda name: ROOT / "music" / f"{name}.m4a"
    if isinstance(m, str):
        return (path(m), None, None) if path(m).exists() else None
    intro, main = path(m.get("intro", "ambiance-01")), path(m.get("main", "rythme-01"))
    if not intro.exists() or not main.exists():
        return (intro, None, None) if intro.exists() else None
    return (intro, main, int(m.get("switch_after", 1)))


def audio_duration(path: pathlib.Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_image(urls: list, cache: pathlib.Path) -> Image.Image:
    if cache.exists():
        return Image.open(cache).convert("RGB")
    last = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                img = Image.open(io.BytesIO(r.read())).convert("RGB")
            img.save(cache, "JPEG", quality=92)
            return img
        except Exception as e:
            last = e
            print(f"   échec {url} : {e}")
    raise RuntimeError(f"Aucune source utilisable pour {cache.name} ({last})")


# ---------- synchronisation sur la voix ----------

def silences(path: pathlib.Path) -> list:
    """Pauses de la voix (début, fin), seuil adapté au niveau de l'enregistrement."""
    out = subprocess.run([FFMPEG, "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean = float(re.search(r"mean_volume: (-?[\d.]+) dB", out).group(1))
    thr = max(-55.0, mean - 8.0)
    out = subprocess.run([FFMPEG, "-i", str(path), "-af", f"silencedetect=noise={thr:.1f}dB:d=0.45",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    dur = audio_duration(path)
    if len(ends) < len(starts):
        ends.append(dur)
    return [(max(0.0, s), e) for s, e in zip(starts, ends)]


def align(paras: list, sil: list, dur: float):
    """Place les changements de paragraphe sur les pauses les plus plausibles.

    Retourne les instants de coupure (au milieu des pauses) et le début/fin de la parole.
    """
    s0 = sil[0][1] if sil and sil[0][0] <= 0.05 else 0.0
    s1 = sil[-1][0] if sil and sil[-1][1] >= dur - 0.05 else dur
    inner = [(a, b) for a, b in sil if a > s0 + 0.1 and b < s1 - 0.1]
    w = [len(p.split()) for p in paras]

    def speech_at(T):  # temps de parole écoulé (pauses exclues) entre s0 et T
        tot = T - s0
        for a, b in sil:
            a2, b2 = max(a, s0), min(b, T)
            if b2 > a2:
                tot -= b2 - a2
        return tot

    S = speech_at(s1)
    cum, expected = 0, []
    for x in w[:-1]:
        cum += x
        target, lo, hi = S * cum / sum(w), s0, s1
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if speech_at(mid) < target else (lo, mid)
        expected.append(lo)
    k, m = len(expected), len(inner)
    if m < k:
        return None, s0, s1
    span = s1 - s0
    cost = lambda i, j: abs((inner[j][0] + inner[j][1]) / 2 - expected[i]) / span * 100 - 4 * (inner[j][1] - inner[j][0])
    INF = float("inf")
    best = [[INF] * m for _ in range(k)]
    prev = [[-1] * m for _ in range(k)]
    for j in range(m):
        best[0][j] = cost(0, j)
    for i in range(1, k):
        run, arg = INF, -1
        for j in range(m):
            if j > 0 and best[i - 1][j - 1] < run:
                run, arg = best[i - 1][j - 1], j - 1
            if arg >= 0:
                best[i][j] = run + cost(i, j)
                prev[i][j] = arg
    j = min(range(m), key=lambda x: best[k - 1][x])
    picks = []
    for i in range(k - 1, -1, -1):
        picks.append(j)
        j = prev[i][j]
    picks.reverse()
    return [(inner[j][0] + inner[j][1]) / 2 for j in picks], s0, s1


def caption_times(caps: list, start: float, end: float, sil: list) -> list:
    """Instant d'apparition de chaque sous-titre, réparti sur le temps de parole (hors pauses)."""
    gaps = [(max(a, start), min(b, end)) for a, b in sil if b > start and a < end]
    speech, cur = [], start
    for a, b in gaps:
        if a > cur:
            speech.append((cur, a))
        cur = max(cur, b)
    if cur < end:
        speech.append((cur, end))
    total = sum(b - a for a, b in speech) or 1.0
    words = [len(c.split()) for c in caps]
    times, acc = [], 0
    for wcount in words:
        target, t = total * acc / sum(words), None
        for a, b in speech:
            if target <= b - a:
                t = a + target
                break
            target -= b - a
        times.append(t if t is not None else end)
        acc += wcount
    return times


def caption_chunks_from_words(words: list, max_words: int = 5) -> list:
    """Blocs de sous-titres à partir des mots horodatés (jamais à cheval sur deux paragraphes)."""
    chunks_, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_para = nxt is None or nxt["p"] != w["p"]
        pause = nxt is not None and nxt["s"] - w["e"] > 0.35
        punct = re.search(r"[.,:;?!…»]$", w["t"]) and len(cur) >= 2
        if len(cur) >= max_words or end_para or pause or punct:
            chunks_.append({"t": " ".join(x["t"] for x in cur), "s": cur[0]["s"], "e": cur[-1]["e"]})
            cur = []
    return chunks_


def active_caption(chunks_: list, now: float):
    if not chunks_:
        return None
    if now < chunks_[0]["s"]:
        return chunks_[0]["t"]  # l'accroche est visible dès la première image
    for i, c in enumerate(chunks_):
        nxt = chunks_[i + 1]["s"] if i + 1 < len(chunks_) else float("inf")
        if c["s"] - 0.05 <= now < nxt - 0.05:
            return c["t"] if now <= c["e"] + 0.5 else None
    return None


# ---------- image ----------

def base_canvas(src: Image.Image, crop) -> Image.Image:
    """Image entière sur fond flou, à la taille agrandie pour le mouvement de caméra."""
    if crop:
        l, t, r, b = crop
        src = src.crop((round(l * src.width), round(t * src.height),
                        round(r * src.width), round(b * src.height)))
    BW, BH = round(W * ZOOM), round(H * ZOOM)
    s = max(BW / src.width, BH / src.height)
    bg = src.resize((round(src.width * s), round(src.height * s)), Image.BILINEAR)
    x, y = (bg.width - BW) // 2, (bg.height - BH) // 2
    bg = bg.crop((x, y, x + BW, y + BH)).filter(ImageFilter.GaussianBlur(45))
    bg = ImageEnhance.Brightness(bg).enhance(0.4)
    s = min(BW / src.width, BH * 0.62 / src.height)  # laisse de la place aux sous-titres
    fg = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    bg.paste(fg, ((BW - fg.width) // 2, round(BH * 0.36 - fg.height / 2)))
    return bg


def camera(base: Image.Image, t: float, direction: str) -> Image.Image:
    """t de 0 à 1 : zoom avant ('in') ou arrière ('out'), centré."""
    k = t if direction == "in" else 1 - t
    k = k * k * (3 - 2 * k)  # mouvement doux
    z = 1 + (ZOOM - 1) * k   # 1 = plan large, ZOOM = plan serré
    cw, ch = base.width / z, base.height / z
    x, y = (base.width - cw) / 2, (base.height - ch) / 2
    return base.resize((W, H), Image.BILINEAR, box=(x, y, x + cw, y + ch))


# ---------- sous-titres ----------

def chunks(paragraph: str, max_words: int = 5) -> list:
    """Découpe en petits blocs de mots, en coupant de préférence après la ponctuation."""
    words, out, cur = paragraph.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or (len(cur) >= 2 and re.search(r"[.,:;?!…]$", w)):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def draw_caption(frame: Image.Image, text: str, font: ImageFont.FreeTypeFont) -> None:
    d = ImageDraw.Draw(frame)
    lines, line = [], ""
    for w in text.split():
        trial = (line + " " + w).strip()
        if d.textlength(trial, font=font) > 900 and line:
            lines.append(line)
            line = w
        else:
            line = trial
    lines.append(line)
    y = 1290 - len(lines) * 45
    for ln in lines:
        x = (W - d.textlength(ln, font=font)) / 2
        d.text((x, y), ln, font=font, fill="white", stroke_width=7, stroke_fill="black")
        y += 92


def draw_signature(frame: Image.Image, font: ImageFont.FreeTypeFont) -> None:
    d = ImageDraw.Draw(frame)
    txt = "@kulturable"
    d.text(((W - d.textlength(txt, font=font)) / 2, 150), txt, font=font,
           fill=(255, 255, 255, 200), stroke_width=3, stroke_fill="black")


# ---------- montage ----------

def build(folder: pathlib.Path, force: bool = False) -> pathlib.Path:
    spec = json.loads((folder / "video.json").read_text(encoding="utf-8"))
    paras = paragraphs(folder)
    segs = spec["segments"]
    if len(segs) != len(paras):
        raise ValueError(f"{len(paras)} paragraphes mais {len(segs)} plans dans video.json")
    voice = find_voice(folder)
    music = find_music(folder, spec)
    out = folder / ("video.mp4" if voice else "apercu.mp4")

    # Ne refait la vidéo que si une entrée a changé.
    h = hashlib.sha256()
    code = [pathlib.Path(__file__), pathlib.Path(__file__).with_name("voice_sync.py")] if voice else []
    for f in sorted([folder / "script.txt", folder / "video.json"] + code + ([voice] if voice else []) + ([f for f in music[:2] if f] if music else [])):
        h.update(f.read_bytes())
    stamp = folder / f".{out.stem}.hash"
    if out.exists() and stamp.exists() and stamp.read_text() == h.hexdigest() and not force:
        print(f"{out} est déjà à jour.")
        return out

    weights = [len(p.split()) + 1.5 for p in paras]  # +1.5 : la pause entre deux paragraphes
    sil, cuts, words, voice_input = [], None, None, voice
    synced = None
    if voice:
        import voice_sync
        synced = voice_sync.sync(folder, voice, paras)
    if synced:
        # synchronisation exacte : mots reconnus et horodatés, voix nettoyée
        voice_input, words, vtotal = synced
        total = vtotal + 0.6
        cuts = []
        for k in range(len(paras) - 1):
            ends = [w["e"] for w in words if w["p"] == k]
            starts = [w["s"] for w in words if w["p"] == k + 1]
            prev = cuts[-1] if cuts else 0.0
            c = (max(ends) + min(starts)) / 2 if ends and starts else prev + 0.5
            cuts.append(max(c, prev + 0.3))
        print("   synchronisation mot à mot : " + ", ".join(f"{c:.1f}s" for c in cuts))
    elif voice:
        vdur = audio_duration(voice)
        total = vdur + 0.6
        sil = silences(voice)
        cuts, s0, s1 = align(paras, sil, vdur)
        if spec.get("cuts"):  # réglage manuel possible dans video.json
            cuts = [float(c) for c in spec["cuts"]]
    else:
        total = sum(weights) / WORDS_PER_SEC
    if cuts:
        bounds = [0.0] + cuts + [total]
        if not words:
            print("   coupures sur les pauses : " + ", ".join(f"{c:.1f}s" for c in cuts))
    else:
        acc, bounds = 0.0, [0.0]
        for w in weights:
            acc += total * w / sum(weights)
            bounds.append(acc)
    durations = [b - a for a, b in zip(bounds, bounds[1:])]
    print(f"{folder.name} : {len(paras)} plans, {total:.1f} s, voix : {voice.name if voice else 'aucune (aperçu)'}, musique : {' puis '.join(f.name for f in music[:2] if f) if music else 'aucune'}")

    cache = folder / "_images"
    cache.mkdir(exist_ok=True)
    sources = {k: load_image(v, cache / f"{k}.jpg") for k, v in spec["images"].items()}
    cap_font = ImageFont.truetype(str(FONT), 68)
    sig_font = ImageFont.truetype(str(FONT), 40)

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    fade_out = max(0.0, total - 3.0)
    idx = 1
    if voice:
        cmd += ["-i", str(voice_input)]
        idx = 2
    music_chain = None
    if music:
        intro, main, switch_after = music
        v_intro, v_main = (0.22, 0.17) if voice else (0.8, 0.65)
        cmd += ["-stream_loop", "-1", "-i", str(intro)]
        if main:
            cmd += ["-stream_loop", "-1", "-i", str(main)]
            s = bounds[min(switch_after, len(bounds) - 2)]  # fin de l'accroche
            music_chain = (
                f"[{idx}:a]volume={v_intro},afade=t=in:d=1.5,afade=t=out:st={max(0, s - 0.8):.2f}:d=1.6,"
                f"atrim=0:{s + 1:.2f}[m1];"
                f"[{idx + 1}:a]volume={v_main},afade=t=in:d=1.2,"
                f"adelay={int(max(0, s - 0.6) * 1000)}:all=1,afade=t=out:st={fade_out:.2f}:d=3[m2];"
                f"[m1][m2]amix=inputs=2:duration=longest:normalize=0[m]")
        else:
            music_chain = f"[{idx}:a]volume={v_intro},afade=t=in:d=2,afade=t=out:st={fade_out:.2f}:d=3[m]"
    voice_chain = "[1:a]highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100,apad"
    if voice and music_chain:
        # la musique baisse automatiquement quand la voix parle
        graph = (f"{voice_chain},asplit=2[v][key];{music_chain};"
                 f"[m][key]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=600[md];"
                 f"[v][md]amix=inputs=2:duration=first:normalize=0[a]")
    elif music_chain:
        graph = music_chain.replace("[m]", "[a]") if music_chain.endswith("[m]") else music_chain
    elif voice:
        graph = f"{voice_chain}[a]"
    else:
        graph = None
    if graph:
        cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    if not voice:  # aperçu : version légère, juste pour vérifier les images
        cmd += ["-vf", "scale=720:1280", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]
    cmd += ["-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{total:.2f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    word_caps = caption_chunks_from_words(words) if words else None
    frame_no = 0
    for k, (seg, para) in enumerate(zip(segs, paras)):
        start, end = bounds[k], bounds[k + 1]
        base = base_canvas(sources[seg["image"]], seg.get("crop"))
        caps = chunks(para)
        times = caption_times(caps, start, end, sil)
        last = round(end * FPS)
        first = frame_no
        while frame_no < last:
            now = frame_no / FPS
            t = (frame_no - first) / max(1, last - first)
            idx = 0
            for j, ct in enumerate(times):
                if ct <= now:
                    idx = j
            frame_no += 1
            frame = camera(base, t, seg.get("zoom", "in"))
            draw_signature(frame, sig_font)
            if word_caps is not None:
                text = active_caption(word_caps, now)
                if text:
                    draw_caption(frame, text, cap_font)
            else:
                draw_caption(frame, caps[idx], cap_font)
            ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg a échoué")
    stamp.write_text(h.hexdigest())
    print(f"OK : {out}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    folders = [pathlib.Path(a) for a in args] or sorted(p for p in (ROOT / "tiktok").iterdir() if p.is_dir())
    import traceback
    failed, journal = 0, []
    for f in folders:
        try:
            build(f, force)
            journal.append(f"OK     {f.name}")
        except Exception as e:
            failed += 1
            print(f"ÉCHEC {f.name} : {e}")
            journal.append(f"ÉCHEC  {f.name} : {e}\n" + traceback.format_exc())
    (ROOT / "tiktok" / "_journal.txt").write_text("\n".join(journal) + "\n", encoding="utf-8")
    sys.exit(1 if failed else 0)
