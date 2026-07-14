"""Gera o card OG (1200x630) na paleta do Living Portfolio."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

W, H = 1200, 630
BG = (11, 12, 14)
ELEV = (19, 21, 25)
TEXT = (232, 234, 237)
DIM = (154, 160, 168)
ACCENT = (122, 162, 247)
BORDER = (35, 38, 44)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# barra de accent no topo (assinatura visual do site)
d.rectangle([0, 0, W, 8], fill=ACCENT)


def load(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


SANS = ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"]
SANS_BOLD = ["/System/Library/Fonts/HelveticaNeue.ttc", "/Library/Fonts/Arial Bold.ttf"]
MONO = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
]

f_name = load(SANS_BOLD, 74)
f_head = load(SANS, 38)
f_mono = load(MONO, 26)

pad = 80
y = 150

# nome
d.text((pad, y), "Gyovana Santos do Prado", font=f_name, fill=TEXT)
y += 100

# headline em accent
d.text((pad, y), "Data & AI Engineer — Human in the Loop", font=f_head, fill=ACCENT)
y += 90

# linha divisória sutil
d.rectangle([pad, y, W - pad, y + 1], fill=BORDER)
y += 40

# rodapé mono: a assinatura do projeto + handle
d.text((pad, y), "// living portfolio · github.com/gyovana-prado", font=f_mono, fill=DIM)

# ponto pulsante (o "pulso" do site) no canto inferior direito
r = 9
cx, cy = W - pad, H - 90
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)

out = Path.home() / "dev" / "portifolio-vivo" / "site" / "public" / "og.png"
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out, "PNG")
print("gerado:", out, f"{out.stat().st_size // 1024} KB")
