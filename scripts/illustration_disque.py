"""Illustration originale d'un disque gravé de micro-textes en plusieurs langues (pas une reproduction du vrai disque)."""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
random.seed(7)
S = 2000
img = Image.new("RGB", (S, S), (14, 16, 22))
# fond : léger dégradé
bg = Image.new("L", (S, S), 0); bd = ImageDraw.Draw(bg)
for r in range(S, 0, -8): bd.ellipse([S/2-r, S/2-r, S/2+r, S/2+r], fill=int(40*(1-r/S)))
img = Image.composite(Image.new("RGB", (S, S), (40, 46, 60)), img, bg)
d = ImageDraw.Draw(img)
R = 820; cx = cy = S // 2
# disque métallique : dégradé radial + reflet
disk = Image.new("RGB", (S, S)); dd = ImageDraw.Draw(disk)
for r in range(R, 0, -2):
    t = r / R; v = int(150 + 70 * math.cos(t * 3.2) * (1 - t * 0.3))
    dd.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(v, v+4, v+10))
shine = Image.new("L", (S, S), 0); sd = ImageDraw.Draw(shine)
sd.ellipse([cx-R*0.95, cy-R*1.1, cx+R*0.2, cy-R*0.1], fill=70); shine = shine.filter(ImageFilter.GaussianBlur(120))
disk = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), disk, shine)
mask = Image.new("L", (S, S), 0); ImageDraw.Draw(mask).ellipse([cx-R, cy-R, cx+R, cy+R], fill=255)
img.paste(disk, (0, 0), mask)
d = ImageDraw.Draw(img)
latin = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
cjk_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
words = ["bonjour", "hello", "hola", "ciao", "hallo", "olá", "привет", "γειά σου", "merhaba", "salut", "dzień dobry",
         "hej", "sveiki", "здравствуйте", "kia ora", "jambo", "aloha", "sawubona", "tere", "zdravo", "moïen", "kaixo",
         "你好", "こんにちは", "안녕하세요", "demat", "bon dia", "dobrý den", "szia", "salve", "ahoj", "hallå"]
def ring_text(radius, size, color, step_deg=None):
    font_l = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    try: font_c = ImageFont.truetype(cjk_path, size)
    except Exception: font_c = font_l
    ang = random.random() * 360; start = ang
    circ = 2 * math.pi * radius
    while True:
        w = random.choice(words) + "  ·  "
        f = font_c if any(ord(c) > 0x2E80 for c in w) else font_l
        for ch in w:
            cw = f.getlength(ch) or size * 0.3
            a = math.radians(ang)
            x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
            tile = Image.new("L", (size * 2, size * 2), 0)
            ImageDraw.Draw(tile).text((size * 0.5, size * 0.3), ch, font=f, fill=255)
            tile = tile.rotate(-(ang + 90), resample=Image.BICUBIC)
            img.paste(Image.new("RGB", tile.size, color), (int(x - size), int(y - size)), tile)
            ang += math.degrees(cw / radius)
            if ang - start >= 357: return
# anneaux de texte, de plus en plus fins vers le centre
r = R - 40; size = 34
while r > 140:
    col = (40, 44, 52) if size > 12 else (60, 64, 72)
    ring_text(r, size, col)
    d.ellipse([cx-r-size*0.9, cy-r-size*0.9, cx+r+size*0.9, cy+r+size*0.9], outline=(110, 116, 126), width=1)
    r -= size * 1.5; size = max(7, int(size * 0.86))
# centre : petit globe stylisé
for k in range(6):
    rr = 130 - k * 4
    d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=(70, 76, 86), width=2)
for k in range(-3, 4):
    d.ellipse([cx-130*math.cos(k*0.4), cy-130, cx+130*math.cos(k*0.4), cy+130], outline=(70, 76, 86), width=1)
    yy = cy + 130 * math.sin(k * 0.4); half = 130 * math.cos(k * 0.4)
    d.line([cx-half, yy, cx+half, yy], fill=(70, 76, 86), width=1)
d.ellipse([cx-R, cy-R, cx+R, cy+R], outline=(200, 205, 214), width=6)
img.save("disk.jpg", quality=92)
img.crop((cx - 420, cy - 900, cx + 420 + 200, cy - 60)).resize((1600, 1300)).save("disk2.jpg", quality=92)
