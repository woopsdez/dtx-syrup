"""Render the drum emoji (U+1F941) with Windows' Segoe UI Emoji into drum.ico / drum.png next to this file.

Run with a Python that has Pillow, e.g. the TubeDTX venv:
  C:\\tools\\TubeDTX\\venv\\Scripts\\python.exe assets\\make_icon.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
EMOJI = '\U0001F941'  # drum
FONT = Path(r'C:\Windows\Fonts\seguiemj.ttf')
S = 512  # render size; the icon is shrunk from here


def main() -> int:
    if not FONT.exists():
        print('Segoe UI Emoji not found:', FONT)
        return 1
    font = ImageFont.truetype(str(FONT), int(S * 0.78))
    probe = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), EMOJI, font=font, embedded_color=True)
    w, h = right - left, bottom - top
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text(((S - w) / 2 - left, (S - h) / 2 - top), EMOJI, font=font, embedded_color=True)
    if not im.getbbox():
        print('the emoji rendered empty (Pillow/FreeType without color font support?)')
        return 1
    out = im.resize((256, 256), Image.LANCZOS)
    out.save(HERE / 'drum.png')
    out.save(HERE / 'drum.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print('wrote', HERE / 'drum.ico', 'bbox', im.getbbox())
    return 0


if __name__ == '__main__':
    sys.exit(main())
