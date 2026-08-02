"""
Blok olmayan eşyalar (çubuk, ham madenler) ve alet (kazma/balta/kılıç x
tahta/taş/demir/elmas) tanımları. blocks.py'ye bağımlıdır ama pyglet'e
bağımlı değildir - test edilebilir.

Item id alanları çakışmasın diye:
  0-99    : bloklar (blocks.py)
  100-199 : blok olmayan ham maddeler (çubuk, kömür, demir, elmas)
  200+    : aletler (kazma/balta/kılıç x tier)
"""
import blocks as B

STICK = 100
COAL = 101
IRON = 102
DIAMOND = 103

PICKAXE = "pickaxe"
AXE = "axe"
SWORD = "sword"
TOOL_KINDS = (PICKAXE, AXE, SWORD)

TIERS = ("wood", "stone", "iron", "diamond")
TIER_LEVEL = {"wood": 1, "stone": 2, "iron": 3, "diamond": 4}
TIER_MINING_SPEED = {"wood": 2.0, "stone": 4.0, "iron": 6.0, "diamond": 8.0}
TIER_ATTACK_BONUS = {"wood": 1.0, "stone": 1.5, "iron": 2.0, "diamond": 3.0}

TIER_LABEL_TR = {"wood": "Ahsap", "stone": "Tas", "iron": "Demir", "diamond": "Elmas"}
KIND_LABEL_TR = {"pickaxe": "Kazma", "axe": "Balta", "sword": "Kilic"}

# Tier'e göre craft malzemesi (kazma/balta 3 adet, kılıç 2 adet gerektirir)
TIER_MATERIAL = {"wood": B.PLANKS, "stone": B.COBBLESTONE, "iron": IRON, "diamond": DIAMOND}

TOOL_IDS = {}  # (kind, tier) -> item id
_next_id = 200
for _tier in TIERS:
    for _kind in TOOL_KINDS:
        TOOL_IDS[(_kind, _tier)] = _next_id
        _next_id += 1


class ItemDef:
    __slots__ = ("id", "name", "label", "stack_max", "tool_kind", "tool_tier",
                 "mining_speed", "tier_level", "attack_damage")

    def __init__(self, id_, name, label, stack_max=64, tool_kind=None, tool_tier=None,
                 mining_speed=1.0, tier_level=0, attack_damage=1.0):
        self.id = id_
        self.name = name
        self.label = label            # kısa Türkçe görüntü adı (UI için)
        self.stack_max = stack_max
        self.tool_kind = tool_kind    # "pickaxe" / "axe" / "sword" / None
        self.tool_tier = tool_tier    # "wood"/"stone"/"iron"/"diamond" / None
        self.mining_speed = mining_speed
        self.tier_level = tier_level
        self.attack_damage = attack_damage


ITEMS = {}

# blocks.py'deki her blok aynı zamanda bir "item" (envanterde durabilir)
for _bid, _bdef in B.BLOCKS.items():
    if _bid == B.AIR:
        continue
    ITEMS[_bid] = ItemDef(_bid, _bdef.name, _bdef.name.replace("_", " ").title())

ITEMS[STICK] = ItemDef(STICK, "stick", "Cubuk")
ITEMS[COAL] = ItemDef(COAL, "coal", "Komur")
ITEMS[IRON] = ItemDef(IRON, "iron", "Demir")
ITEMS[DIAMOND] = ItemDef(DIAMOND, "diamond", "Elmas")

for (_kind, _tier), _iid in TOOL_IDS.items():
    _name = f"{_tier}_{_kind}"
    _label = f"{TIER_LABEL_TR[_tier]} {KIND_LABEL_TR[_kind]}"
    if _kind == SWORD:
        _dmg = 3.0 + TIER_ATTACK_BONUS[_tier] * 1.5
        _speed = 1.0
    else:
        _dmg = 1.0 + TIER_ATTACK_BONUS[_tier] * 0.4
        _speed = TIER_MINING_SPEED[_tier]
    ITEMS[_iid] = ItemDef(_iid, _name, _label, stack_max=1, tool_kind=_kind, tool_tier=_tier,
                           mining_speed=_speed, tier_level=TIER_LEVEL[_tier], attack_damage=_dmg)


def stack_max(item_id):
    item = ITEMS.get(item_id)
    return item.stack_max if item else 64


def label(item_id):
    item = ITEMS.get(item_id)
    return item.label if item else "?"


def short_label(item_id, n=5):
    item = ITEMS.get(item_id)
    if item is None:
        return "?"
    if item.tool_kind:
        return f"{item.tool_tier[:2].upper()}{item.tool_kind[0].upper()}"
    return item.name[:n]


# ---------------------------------------------------------------- kazma hızı

# Hangi bloklar kazma (pickaxe) kategorisinde, hangileri balta (axe) kategorisinde
PICKAXE_BLOCKS = {B.STONE, B.COBBLESTONE, B.COAL_ORE, B.IRON_ORE, B.DIAMOND_ORE}
AXE_BLOCKS = {B.WOOD, B.PLANKS}

# Elle (alet olmadan) bir bloğu kırmanın temel süresi (saniye)
BLOCK_HARDNESS = {
    B.DIRT: 0.5, B.GRASS: 0.6, B.SAND: 0.5,
    B.STONE: 1.5, B.COBBLESTONE: 2.0,
    B.WOOD: 2.0, B.PLANKS: 2.0, B.LEAVES: 0.2,
    B.COAL_ORE: 3.0, B.IRON_ORE: 3.75, B.DIAMOND_ORE: 4.5,
}

# Cevherden verim almak için gereken minimum kazma tier seviyesi (TIER_LEVEL)
ORE_MIN_TIER_LEVEL = {B.COAL_ORE: 1, B.IRON_ORE: 2, B.DIAMOND_ORE: 3}

ORE_DROPS = {B.COAL_ORE: COAL, B.IRON_ORE: IRON, B.DIAMOND_ORE: DIAMOND}


def mining_seconds(block_id, held_item_id):
    """Bu bloğu bu eşyayla kırmak kaç saniye sürer? Kırılamaz bloklar için None."""
    hardness = BLOCK_HARDNESS.get(block_id)
    if hardness is None:
        hardness = 1.0
    multiplier = 1.0
    item = ITEMS.get(held_item_id) if held_item_id is not None else None
    if item and item.tool_kind == PICKAXE and block_id in PICKAXE_BLOCKS:
        multiplier = item.mining_speed
    elif item and item.tool_kind == AXE and block_id in AXE_BLOCKS:
        multiplier = item.mining_speed
    return hardness / multiplier


def get_drop(block_id, held_item_id):
    """Blok kırılınca envantere hangi item, kaç adet düşer? (None, 0) = düşmez."""
    min_level = ORE_MIN_TIER_LEVEL.get(block_id)
    if min_level is not None:
        item = ITEMS.get(held_item_id) if held_item_id is not None else None
        held_level = item.tier_level if (item and item.tool_kind == PICKAXE) else 0
        if held_level < min_level:
            return None, 0
        return ORE_DROPS[block_id], 1
    drop_id = B.BREAK_DROPS.get(block_id, block_id)
    return drop_id, 1
