# วาดไอคอน git-sync.ico (ลูกศรขึ้น-ลง บนวงกลมสีส้ม) — รัน: py make-icon.py
from PIL import Image, ImageDraw
S = 256
im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.ellipse((8, 8, S - 8, S - 8), fill=(240, 80, 50, 255))
w = (255, 255, 255, 255)
# ลูกศรลง (ซ้าย = pull)
d.rectangle((70, 60, 100, 150), fill=w); d.polygon([(45, 140), (125, 140), (85, 200)], fill=w)
# ลูกศรขึ้น (ขวา = push)
d.rectangle((156, 106, 186, 196), fill=w); d.polygon([(131, 116), (211, 116), (171, 56)], fill=w)
im.save('git-sync.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
im.save('git-sync.png')
print('ok')
