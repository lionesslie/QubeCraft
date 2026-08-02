"""
Basit tarif-listesi tabanli crafting sistemi (3x3 desen eslestirme degil -
malzemeleri say, uret). Bir masaya ihtiyac yok, envanter ekranindan direkt
craft edilir.

Her tarif: (gorunen_isim, {ingredient_item_id: adet}, output_item_id, output_adet)
"""
import blocks as B
import items as I

RECIPES = [
    ("Kutuk -> 4 Tahta", {B.WOOD: 1}, B.PLANKS, 4),
    ("2 Tahta -> 4 Cubuk", {B.PLANKS: 2}, I.STICK, 4),
]

# Alet tarifleri: her tier + tur icin otomatik uret (3 malzeme + 2 cubuk kazma/balta,
# 2 malzeme + 1 cubuk kilic - gercek Minecraft oranlarina yakin)
for _tier in I.TIERS:
    _mat = I.TIER_MATERIAL[_tier]
    for _kind in I.TOOL_KINDS:
        _out = I.TOOL_IDS[(_kind, _tier)]
        _kind_label = I.KIND_LABEL_TR[_kind]
        _tier_label = I.TIER_LABEL_TR[_tier]
        if _kind == I.SWORD:
            ingredients = {_mat: 2, I.STICK: 1}
        else:
            ingredients = {_mat: 3, I.STICK: 2}
        RECIPES.append((f"{_tier_label} {_kind_label}", ingredients, _out, 1))


def _have_counts(inventory):
    have = {}
    for i in range(inventory.total_slots()):
        stack = inventory.get_slot(i)
        if stack:
            have[stack[0]] = have.get(stack[0], 0) + stack[1]
    return have


def can_craft(inventory, recipe):
    _, ingredients, _, _ = recipe
    have = _have_counts(inventory)
    return all(have.get(iid, 0) >= need for iid, need in ingredients.items())


def craft(inventory, recipe):
    """Tarifteki malzemeleri envanterden dusurur, urunu ekler. Basarisizsa False doner
    (yetersiz malzeme) ve envantere dokunmaz."""
    if not can_craft(inventory, recipe):
        return False
    _, ingredients, out_id, out_count = recipe
    for iid, need in ingredients.items():
        remaining = need
        for i in range(inventory.total_slots()):
            if remaining <= 0:
                break
            stack = inventory.get_slot(i)
            if stack and stack[0] == iid:
                take = min(stack[1], remaining)
                stack[1] -= take
                remaining -= take
                if stack[1] <= 0:
                    inventory.set_slot(i, None)
    inventory.add_item(out_id, out_count)
    return True
