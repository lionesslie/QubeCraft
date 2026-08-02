"""
Minecraft tarzi IZGARA (grid) tabanli crafting: bir tarif, hucrelerin (satir/
sutun) belirli bir duzende dolu olmasini gerektirir (shaped), ya da sadece
dogru malzemelerin herhangi bir duzende bulunmasini gerektirir (shapeless).

2x2 kisisel envanter gridine SIGAN tarifler (tahta, cubuk) oradan da
yapilabilir; 3 satir/sutun gerektiren tarifler (tum aletler) crafting
masasinin 3x3 gridini gerektirir - tipki gercek Minecraft'taki gibi.

Bu dosya pyglet'e bagimli degildir; main.py grid hucrelerini ([item_id,count]
ya da None) burada tanimli match()/craft_once() fonksiyonlarina verir.
"""
import blocks as B
import items as I


class Recipe:
    __slots__ = ("name", "pattern", "output_id", "output_count", "shapeless", "height", "width")

    def __init__(self, name, pattern, output_id, output_count, shapeless=False):
        self.name = name
        self.pattern = pattern  # satir listesi, her satir: item_id ya da None
        self.output_id = output_id
        self.output_count = output_count
        self.shapeless = shapeless
        self.height = len(pattern)
        self.width = max(len(row) for row in pattern)

    def max_dim(self):
        return max(self.height, self.width)


RECIPES = [
    Recipe("Tahta Kutuk -> Tahta", [[B.WOOD]], B.PLANKS, 4, shapeless=True),
    Recipe("Cubuk", [[B.PLANKS], [B.PLANKS]], I.STICK, 4),
    Recipe("Crafting Masasi", [[B.PLANKS, B.PLANKS], [B.PLANKS, B.PLANKS]], B.CRAFTING_TABLE, 1),
]

for _tier in I.TIERS:
    _mat = I.TIER_MATERIAL[_tier]
    _label = I.TIER_LABEL_TR[_tier]
    pick_pattern = [[_mat, _mat, _mat], [None, I.STICK, None], [None, I.STICK, None]]
    axe_pattern = [[_mat, _mat, None], [_mat, I.STICK, None], [None, I.STICK, None]]
    sword_pattern = [[_mat], [_mat], [I.STICK]]
    RECIPES.append(Recipe(f"{_label} Kazma", pick_pattern, I.TOOL_IDS[(I.PICKAXE, _tier)], 1))
    RECIPES.append(Recipe(f"{_label} Balta", axe_pattern, I.TOOL_IDS[(I.AXE, _tier)], 1))
    RECIPES.append(Recipe(f"{_label} Kilic", sword_pattern, I.TOOL_IDS[(I.SWORD, _tier)], 1))


def _ids_grid(grid):
    """grid: satir listesi, her hucre [item_id,count] ya da None -> sadece item_id'lerden olusan grid."""
    return [[(cell[0] if cell else None) for cell in row] for row in grid]


def _trim(ids_grid):
    """Bos kenar satir/sutunlari keser. Tamamen bossa None doner."""
    filled = [(r, c) for r, row in enumerate(ids_grid) for c, v in enumerate(row) if v is not None]
    if not filled:
        return None
    min_r = min(r for r, c in filled)
    max_r = max(r for r, c in filled)
    min_c = min(c for r, c in filled)
    max_c = max(c for r, c in filled)
    return [row[min_c:max_c + 1] for row in ids_grid[min_r:max_r + 1]]


def match(grid):
    """grid: NxN satir listesi ([item_id,count] ya da None hucreler).
    Eslesen Recipe'i (ya da None) doner."""
    ids_grid = _ids_grid(grid)
    trimmed = _trim(ids_grid)
    if trimmed is None:
        return None
    flat_items = sorted(v for row in trimmed for v in row if v is not None)
    for recipe in RECIPES:
        if recipe.shapeless:
            pat_items = sorted(v for row in recipe.pattern for v in row if v is not None)
            if flat_items == pat_items:
                return recipe
        else:
            if len(trimmed) != recipe.height or any(len(row) != recipe.width for row in trimmed):
                continue
            if all(trimmed[r][c] == recipe.pattern[r][c]
                   for r in range(recipe.height) for c in range(recipe.width)):
                return recipe
    return None


def craft_once(grid):
    """Sonuc slotuna tiklaninca cagrilir: eslesen tarifi bulup grid'deki dolu
    her hucreden 1 adet dusurur (tariflerimiz her hucrede en fazla 1 adet
    kullaniyor). Doner: (output_id, output_count) ya da None (eslesme yok)."""
    recipe = match(grid)
    if recipe is None:
        return None
    for row in grid:
        for i, cell in enumerate(row):
            if cell is not None:
                cell[1] -= 1
                if cell[1] <= 0:
                    row[i] = None
    return recipe.output_id, recipe.output_count
