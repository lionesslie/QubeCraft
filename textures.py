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
    "coal_ore", "iron_ore", "diamond_ore", "crafting_table_top", "crafting_table_side",
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


def make_crafting_table_top(rng):
    img = make_planks(rng)
    px = img.load()
    # basit bir "kesim çizgisi" ızgarası: ortadan çapraz bölünmüş iki üçgen görünümü
    grid_color = (70, 48, 28)
    for i in range(TILE):
        px[i, TILE // 2] = grid_color
        px[TILE // 2, i] = grid_color
    for i in range(0, TILE, 3):
        px[i, i] = (170, 130, 80)
    return img


def make_crafting_table_side(rng):
    img = make_planks(rng)
    px = img.load()
    border = (60, 42, 24)
    for i in range(TILE):
        px[i, 0] = border
        px[i, TILE - 1] = border
        px[0, i] = border
        px[TILE - 1, i] = border
    return img


HANDLE_COLOR = (120, 85, 52)

TOOL_TIER_COLOR = {
    "wood": (156, 110, 66), "stone": (150, 150, 150),
    "iron": (222, 222, 210), "diamond": (100, 220, 210),
}


def _blank(size=TILE):
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _line(px, x0, y0, x1, y1, color):
    """Basit Bresenham benzeri kalın çizgi (piksel-art alet siluetleri için)."""
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        t = i / steps
        x = round(x0 + (x1 - x0) * t)
        y = round(y0 + (y1 - y0) * t)
        for dx in (-1, 0):
            for dy in (-1, 0):
                xx, yy = x + dx, y + dy
                if 0 <= xx < TILE and 0 <= yy < TILE:
                    px[xx, yy] = color


def make_tool_icon(kind, tier):
    """Kazma/balta/kılıç için basit piksel-art ikon üretir (hotbar/envanter ikonu)."""
    img = _blank()
    px = img.load()
    head_color = TOOL_TIER_COLOR[tier]
    if kind == "pickaxe":
        _line(px, 3, 3, 12, 3, head_color)
        _line(px, 3, 3, 6, 6, head_color)
        _line(px, 12, 3, 9, 6, head_color)
        _line(px, 7, 6, 13, 12, HANDLE_COLOR)
    elif kind == "axe":
        _line(px, 9, 2, 13, 5, head_color)
        _line(px, 13, 5, 10, 9, head_color)
        _line(px, 9, 2, 6, 6, head_color)
        _line(px, 6, 6, 10, 9, head_color)
        _line(px, 9, 5, 3, 13, HANDLE_COLOR)
    else:  # sword
        _line(px, 8, 1, 8, 9, head_color)
        _line(px, 6, 3, 10, 3, head_color)
        _line(px, 5, 9, 11, 9, HANDLE_COLOR)
        _line(px, 8, 9, 8, 14, HANDLE_COLOR)
    return img


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
        "crafting_table_top": make_crafting_table_top, "crafting_table_side": make_crafting_table_side,
    }
    paths = {}
    for name in TEXTURE_NAMES:
        img = makers[name](rng).convert("RGBA")
        path = os.path.join(out_dir, f"{name}.png")
        img.save(path)
        paths[name] = path
    print(f"{len(paths)} ayrı texture kaydedildi: {out_dir}/")
    return paths


def build_tool_icons(out_dir="assets"):
    """Her (tier, tür) kombinasyonu için alet ikonu üretir: assets/icon_<tier>_<tur>.png"""
    import os
    os.makedirs(out_dir, exist_ok=True)
    kinds = ["pickaxe", "axe", "sword"]
    tiers = ["wood", "stone", "iron", "diamond"]
    paths = {}
    for tier in tiers:
        for kind in kinds:
            img = make_tool_icon(kind, tier)
            path = os.path.join(out_dir, f"icon_{tier}_{kind}.png")
            img.save(path)
            paths[(kind, tier)] = path
    return paths


if __name__ == "__main__":
    build_individual_textures()
    build_tool_icons()
