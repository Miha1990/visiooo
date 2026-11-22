"""Export browser and home-screen icons from the original generated logo."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'assets' / 'brand' / 'visiooo-logo-master.png'
DESTINATION = ROOT / 'app' / 'static' / 'brand'


def main():
    source = Image.open(SOURCE).convert('RGB')
    if source.width != source.height:
        raise ValueError('Logo source must be square')
    DESTINATION.mkdir(parents=True, exist_ok=True)
    sizes = {
        'logo-mark-96.png': 96,
        'logo-mark-256.png': 256,
        'favicon-16.png': 16,
        'favicon-32.png': 32,
        'favicon-48.png': 48,
        'favicon-96.png': 96,
        'apple-touch-icon-120.png': 120,
        'apple-touch-icon-152.png': 152,
        'apple-touch-icon-167.png': 167,
        'apple-touch-icon-180.png': 180,
        'android-icon-192.png': 192,
        'android-icon-512.png': 512,
        'android-maskable-192.png': 192,
        'android-maskable-512.png': 512,
    }
    # The white mark must fit the standardized central 40%-radius safe circle.
    center = (source.width - 1) / 2
    for y in range(source.height):
        for x in range(source.width):
            r, g, b = source.getpixel((x, y))
            if min(r, g, b) > 220 and (x - center) ** 2 + (y - center) ** 2 > (source.width * .4) ** 2:
                raise ValueError('Logo extends beyond the maskable icon safe circle')
    for filename, size in sizes.items():
        source.resize((size, size), Image.Resampling.LANCZOS).save(DESTINATION / filename, optimize=True)
    source.save(DESTINATION / 'favicon.ico', format='ICO',
                sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    archive = ROOT / '.artifacts' / 'visiooo-brand-kit.zip'
    archive.parent.mkdir(exist_ok=True)
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as package:
        package.write(SOURCE, 'visiooo-logo-master.png')
        package.write(SOURCE.with_name('README.txt'), 'README.txt')
        for path in sorted(DESTINATION.iterdir()):
            if path.is_file():
                package.write(path, path.name)
    print(f'Exported {len(sizes)} PNG icons and favicon.ico; archive: {archive.name}')


if __name__ == '__main__':
    main()
