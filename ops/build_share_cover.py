"""Compose the share banner from the existing brand assets and local fonts."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent


def main():
    canvas = Image.new('RGB', (1200, 630), '#f7f8f5')
    draw = ImageDraw.Draw(canvas)
    font_dir = Path('C:/Windows/Fonts')
    regular = font_dir / 'segoeui.ttf'
    bold = font_dir / 'segoeuib.ttf'
    if not regular.exists() or not bold.exists():
        raise SystemExit('Requires Segoe UI fonts on the design workstation; generated PNG is committed.')
    def text(position, value, size, color='#162238', weight=False):
        draw.text(position, value, font=ImageFont.truetype(str(bold if weight else regular), size), fill=color)
    logo = Image.open(ROOT / 'app/static/brand/logo-mark-256.png').convert('RGB')
    canvas.paste(logo.resize((76, 76), Image.Resampling.LANCZOS), (72, 62))
    text((166, 68), 'визитка', 46, weight=True)
    text((72, 198), 'Все контакты', 67, weight=True)
    text((72, 280), 'в одном касании', 67, weight=True)
    text((76, 393), 'Фото, соцсети и ваш стиль.', 30)
    text((76, 438), 'Делитесь ссылкой, QR-кодом и NFC.', 28)
    text((76, 545), 'visiooo.ru', 28, '#2457db', weight=True)
    draw.rounded_rectangle((836, 85, 1130, 548), 32, fill='#2457db')
    draw.rounded_rectangle((858, 108, 1108, 528), 22, fill='white')
    draw.rounded_rectangle((858, 108, 1108, 234), 22, fill='#e3eaf9')
    canvas.paste(logo.resize((112, 112), Image.Resampling.LANCZOS), (927, 172))
    text((897, 312), 'Это вы', 34, weight=True)
    text((898, 362), 'Ваши контакты', 22)
    draw.rounded_rectangle((885, 422, 1080, 476), 18, fill='#d3f35c')
    text((908, 431), 'Сохранить', 24, weight=True)
    canvas.save(ROOT / 'app/static/brand/share-cover.png', optimize=True)


if __name__ == '__main__':
    main()
