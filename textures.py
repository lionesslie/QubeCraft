"""
16x16 piksel-art block texture'ları üretir. Her blok yüzü KENDİ AYRI PNG
dosyasına kaydedilir (assets/<isim>.png) - paylaşılan bir atlas YOK.

İsim listesi:
  grass_top, grass_side, dirt, stone, sand, water,
  wood_side, wood_top, leaves, bedrock, planks, cobblestone
"""
import random
from PIL import Image

TILE = 16

TEXTURE_NAMES = [
    "grass_top", "grass_side", "dirt", "stone", "sand", "water",
    "wood_side", "wood_top", "leaves", "bedrock", "planks", "cobblestone",
    "coal_ore", "iron_ore", "diamond_ore",
]


def _speckle(img, base, variants, density, rng):
    """base renk üstüne rastgele varyant renkli pikseller serper (basit piksel-art dokusu)."""
    px = img.load()
    for x in range(TILE):
        for y in range(TILE):
            px[x, y] = base
    for x in range(TILE):
        for y in range(TILE):
            if rng.random() < density:
                px[x, y] = rng.choice(variants)
    return img


def make_grass_top(rng):
    img = Image.new("RGB", (TILE, TILE))
    return _speckle(img, (86, 156, 60), [(76, 140, 52), (98, 168, 70), (67, 130, 46)], 0.35, rng)


def make_grass_side(rng):
    img = Image.new("RGB", (TILE, TILE))
    px = img.load()
    for x in range(TILE):
        for y in range(TILE):
            if y < 4:
                px[x, y] = rng.choice([(86, 156, 60), (76, 140, 52), (98, 168, 70)])
            elif y == 4:
                px[x, y] = rng.choice([(70, 120, 48), (60, 105, 40)])
            else:
                px[x, y] = rng.choice([(134, 96, 67), (120, 85, 58), (145, 105, 74)])
    return img


def make_dirt(rng):
    img = Image.new("RGB", (TILE, TILE))
    return _speckle(img, (134, 96, 67), [(120, 85, 58), (145, 105, 74), (110, 78, 52)], 0.3, rng)


def make_stone(rng):
    img = Image.new("RGB", (TILE, TILE))
    return _speckle(img, (128, 128, 128), [(115, 115, 115), (140, 140, 140), (100, 100, 100)], 0.3, rng)


def make_sand(rng):
    img = Image.new("RGB", (TILE, TILE))
    return _speckle(img, (219, 205, 145), [(230, 216, 158), (206, 190, 130), (198, 182, 122)], 0.25, rng)


def make_water(rng):
    img = Image.new("RGBA", (TILE, TILE))
    px = img.load()
    for x in range(TILE):
        for y in range(TILE):
            base = rng.choice([(52, 96, 196), (44, 84, 176), (60, 108, 210)])
            px[x, y] = (*base, 170)
    return img


def make_wood_side(rng):
    img = Image.new("RGB", (TILE, TILE))
    px = img.load()
    for x in range(TILE):
        line = (x % 4 == 0)
        for y in range(TILE):
            if line:
                px[x, y] = rng.choice([(90, 62, 38), (80, 55, 33)])
            else:
                px[x, y] = rng.choice([(120, 85, 52), (110, 77, 47), (128, 92, 58)])
    return img


def make_wood_top(rng):
    img = Image.new("RGB", (TILE, TILE))
    px = img.load()
    cx, cy = TILE / 2 - 0.5, TILE / 2 - 0.5
    for x in range(TILE):
        for y in range(TILE):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            ring = int(d) % 3
            base = [(150, 110, 70), (134, 96, 60), (120, 85, 52)][ring]
            px[x, y] = base
    return img


def make_leaves(rng):
    img = Image.new("RGBA", (TILE, TILE))
    px = img.load()
    for x in range(TILE):
        for y in range(TILE):
            base = rng.choice([(46, 110, 46), (38, 96, 38), (56, 124, 56), (34, 84, 34)])
            a = 255 if rng.random() > 0.06 else 0  # hafif seyrek yapraklar
            px[x, y] = (*base, a)
    return img


def make_bedrock(rng):
    img = Image.new("RGB", (TILE, TILE))
    return _speckle(img, (40, 40, 40), [(30, 30, 30), (55, 55, 55), (20, 20, 20)], 0.4, rng)


def make_planks(rng):
    img = Image.new("RGB", (TILE, TILE))
    px = img.load()
    for y in range(TILE):
        plank_line = (y % 4 == 0)
        for x in range(TILE):
            if plank_line:
                px[x, y] = (150, 108, 66)
            else:
                px[x, y] = rng.choice([(196, 150, 96), (184, 138, 88), (206, 160, 104)])
    return img


def make_cobblestone(rng):
    img = Image.new("RGB", (TILE, TILE))
    return _speckle(img, (120, 120, 120), [(100, 100, 100), (140, 140, 140), (90, 90, 90), (150, 150, 150)], 0.45, rng)


def _ore_texture(rng, vein_colors, vein_density=0.16):
    """Taş zemin üstüne renkli maden damarları serper (kömür/demir/elmas cevheri için ortak)."""
    img = Image.new("RGB", (TILE, TILE))
    px = img.load()
    stone_base = [(128, 128, 128), (115, 115, 115), (140, 140, 140), (105, 105, 105)]
    for x in range(TILE):
        for y in range(TILE):
            px[x, y] = rng.choice(stone_base)
    # birbirine yakın 2x2/3x3 kümeler halinde damar noktaları koy (daha "cevher" gibi görünsün)
    placed = 0
    attempts = 0
    while placed < int(TILE * TILE * vein_density) and attempts < 200:
        attempts += 1
        cx, cy = rng.randrange(TILE), rng.randrange(TILE)
        for ddx, ddy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            x, y = cx + ddx, cy + ddy
            if 0 <= x < TILE and 0 <= y < TILE and rng.random() < 0.8:
                px[x, y] = rng.choice(vein_colors)
                placed += 1
    return img


def make_coal_ore(rng):
    return _ore_texture(rng, [(25, 25, 25), (15, 15, 15), (35, 35, 35)])


def make_iron_ore(rng):
    return _ore_texture(rng, [(216, 175, 140), (198, 152, 116), (230, 190, 155)])


def make_diamond_ore(rng):
    return _ore_texture(rng, [(120, 235, 225), (90, 210, 200), (160, 245, 235)])


def build_individual_textures(seed=1337, out_dir="assets"):
    """Her blok yüzü için ayrı bir PNG dosyası üretir (assets/<isim>.png)."""
    import os
    os.makedirs(out_dir, exist_ok=True)
    rng = random.Random(seed)
    makers = {
        "grass_top": make_grass_top, "grass_side": make_grass_side, "dirt": make_dirt,
        "stone": make_stone, "sand": make_sand, "water": make_water,
        "wood_side": make_wood_side, "wood_top": make_wood_top, "leaves": make_leaves,
        "bedrock": make_bedrock, "planks": make_planks, "cobblestone": make_cobblestone,
        "coal_ore": make_coal_ore, "iron_ore": make_iron_ore, "diamond_ore": make_diamond_ore,
    }
    paths = {}
    for name in TEXTURE_NAMES:
        img = makers[name](rng).convert("RGBA")
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path)
        paths[name] = path
    print(f"{len(paths)} ayrı texture kaydedildi: {out_dir}/")
    return paths


if __name__ == "__main__":
    build_individual_textures()
