"""Render the KISS logo mark from web/logo.svg geometry as a Windows icon."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
scale = 16
image = Image.new('RGBA', (64 * scale, 64 * scale))
draw = ImageDraw.Draw(image)
def points(values):
    return [(int(x * scale), int(y * scale)) for x, y in values]
draw.rounded_rectangle((2*scale, 2*scale, 62*scale, 62*scale), radius=17*scale,
                       fill='#0b0f19', outline='#005b69', width=scale)
for segment, color in [([(18,16),(18,48)], '#00e7fe'), ([(18,33),(43,16)], '#18d4fe'),
                       ([(18,33),(44,48)], '#3ab8fe')]:
    draw.line(points(segment), fill=color, width=6*scale)
    for x, y in segment:
        draw.ellipse(((x-3)*scale,(y-3)*scale,(x+3)*scale,(y+3)*scale), fill=color)
draw.arc((37*scale,24*scale,57*scale,42*scale), 120, 240, fill='#4facfe', width=2*scale)
draw.ellipse((13*scale,28*scale,23*scale,38*scale), fill='#00f2fe')
image.resize((256,256), Image.Resampling.LANCZOS).save(root/'web/kiss.ico',
    sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
