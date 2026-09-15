from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


app = QGuiApplication.instance() or QGuiApplication([])
root = Path(__file__).resolve().parents[1] / "resources" / "branding"


def render(source: str, target: str, width: int, height: int) -> None:
    renderer = QSvgRenderer(str(root / source))
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    if not image.save(str(root / target)):
        raise RuntimeError(target)


for size in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
    render("trigrix-icon.svg", f"trigrix-icon-{size}.png", size, size)
render("trigrix-mark.svg", "trigrix-mark-512.png", 512, 512)
master = Image.open(root / "trigrix-icon-1024.png").convert("RGBA")
master.save(
    root / "trigrix-studio.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)

# Qt SVG text rendering depends on host fonts. Build the horizontal raster
# wordmark deterministically with the Windows UI font used by the application.
canvas = Image.new("RGBA", (1200, 320), (0, 0, 0, 0))
canvas.alpha_composite(master.resize((288, 288), Image.Resampling.LANCZOS), (16, 16))
font_root = Path("C:/Windows/Fonts")
brand_font = ImageFont.truetype(str(font_root / "segoeuib.ttf"), 108)
studio_font = ImageFont.truetype(str(font_root / "seguisb.ttf"), 46)
mask = Image.new("L", canvas.size, 0)
mask_draw = ImageDraw.Draw(mask)
mask_draw.text((350, 42), "TRIGRIX", font=brand_font, fill=255, stroke_width=0)
gradient = Image.new("RGBA", canvas.size)
pixels = gradient.load()
for x in range(canvas.width):
    ratio = max(0.0, min(1.0, (x - 350) / 720))
    left, right = (9, 169, 221), (124, 45, 242)
    color = tuple(round(left[i] * (1 - ratio) + right[i] * ratio) for i in range(3)) + (255,)
    for y in range(canvas.height): pixels[x, y] = color
canvas = Image.composite(gradient, canvas, mask)
draw = ImageDraw.Draw(canvas)
draw.text((358, 190), "S T U D I O", font=studio_font, fill=(125, 135, 156, 255))
canvas.save(root / "trigrix-logo-1200.png")
print(f"Rendered {len(list(root.glob('*')))} branding assets")
