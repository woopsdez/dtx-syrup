"""Draw the app icon (a smiling toy drum with crossed sticks) and save icon.ico / icon.png next to this file.

Run with a Python that has Pillow, e.g. the TubeDTX venv:
  C:\\tools\\TubeDTX\\venv\\Scripts\\python.exe assets\\make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 1024  # draw big, shrink later for smooth edges

PINK = (255, 112, 134)
PINK_DARK = (222, 72, 100)
CREAM = (255, 246, 230)
CREAM_DARK = (238, 214, 180)
WOOD = (219, 166, 108)
WOOD_TIP = (246, 214, 170)
INK = (44, 40, 52)
BLUSH = (255, 170, 190)
GOLD = (255, 205, 92)


def stick(d, p0, p1, w, color):
    d.line([p0, p1], fill=color, width=w)
    for x, y in (p0, p1):
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=color)


def main() -> None:
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    # drumsticks behind the drum, crossed
    stick(d, (235, 330), (560, 70), 50, WOOD)
    stick(d, (789, 330), (464, 70), 50, WOOD)
    for x, y in ((560, 70), (464, 70)):
        d.ellipse((x - 44, y - 44, x + 44, y + 44), fill=WOOD_TIP)

    # drum body (toy drum seen a little from above)
    cx, cy = 512, 585
    rx, ry = 345, 115
    d.rectangle((cx - rx, cy, cx + rx, cy + 250), fill=PINK)
    d.ellipse((cx - rx, cy + 250 - ry, cx + rx, cy + 250 + ry), fill=PINK)
    # rope zigzag on the shell
    n = 8
    for i in range(n):
        x0 = cx - rx + 40 + i * ((2 * rx - 80) / n)
        x1 = x0 + (2 * rx - 80) / n
        d.line([(x0, cy + 40), ((x0 + x1) / 2, cy + 225), (x1, cy + 40)], fill=GOLD, width=16)
    # bottom rim
    d.ellipse((cx - rx, cy + 250 - ry, cx + rx, cy + 250 + ry), outline=PINK_DARK, width=22)
    d.rectangle((cx - rx, cy, cx + rx, cy + 250), fill=PINK)
    for i in range(n):
        x0 = cx - rx + 40 + i * ((2 * rx - 80) / n)
        x1 = x0 + (2 * rx - 80) / n
        d.line([(x0, cy + 40), ((x0 + x1) / 2, cy + 225), (x1, cy + 40)], fill=GOLD, width=16)
    d.chord((cx - rx, cy + 250 - ry, cx + rx, cy + 250 + ry), 0, 180, fill=PINK, outline=PINK_DARK, width=22)
    # top head
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=PINK_DARK)
    d.ellipse((cx - rx + 34, cy - ry + 20, cx + rx - 34, cy + ry - 20), fill=CREAM, outline=CREAM_DARK, width=10)

    # face on the shell
    ey = cy + 120
    for ex in (cx - 120, cx + 120):
        d.ellipse((ex - 30, ey - 30, ex + 30, ey + 30), fill=INK)
        d.ellipse((ex - 2, ey - 20, ex + 16, ey - 2), fill=(255, 255, 255))
    for bx in (cx - 215, cx + 215):
        d.ellipse((bx - 48, ey + 10, bx + 48, ey + 60), fill=BLUSH)
    d.arc((cx - 70, ey - 10, cx + 70, ey + 90), start=15, end=165, fill=INK, width=20)

    # a little sparkle
    for (sx, sy, r) in ((150, 160, 26), (880, 190, 18)):
        d.polygon([(sx, sy - r), (sx + r * .3, sy - r * .3), (sx + r, sy), (sx + r * .3, sy + r * .3),
                   (sx, sy + r), (sx - r * .3, sy + r * .3), (sx - r, sy), (sx - r * .3, sy - r * .3)], fill=GOLD)

    out = im.resize((256, 256), Image.LANCZOS)
    out.save(HERE / 'icon.png')
    out.save(HERE / 'icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print('wrote', HERE / 'icon.ico')


if __name__ == '__main__':
    main()
