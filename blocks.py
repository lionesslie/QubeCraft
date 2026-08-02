"""Blok tipi tanımları: id, isim, hangi texture dosyasını (assets/<isim>.png)
hangi yüzde kullanacağı, katılık/şeffaflık ve envanter/crafting için ek bilgiler.
"""

AIR = 0
GRASS = 1
DIRT = 2
STONE = 3
SAND = 4
WATER = 5
WOOD = 6
LEAVES = 7
BEDROCK = 8
PLANKS = 9
COBBLESTONE = 10
COAL_ORE = 11
IRON_ORE = 12
DIAMOND_ORE = 13
CRAFTING_TABLE = 14


class BlockDef:
    __slots__ = ("id", "name", "top", "side", "bottom", "solid", "transparent", "breakable")

    def __init__(self, id_, name, top, side=None, bottom=None, solid=True,
                 transparent=False, breakable=True):
        self.id = id_
        self.name = name
        self.top = top                # texture dosya adı, örn "grass_top"
        self.side = side or top
        self.bottom = bottom or top
        self.solid = solid              # oyuncu içinden geçemez / raycast çarpar
        self.transparent = transparent  # komşu blok yüzeyi bunun arkasında da çizilmeli mi
        self.breakable = breakable


BLOCKS = {
    AIR:  BlockDef(AIR, "air", "grass_top", solid=False, transparent=True, breakable=False),
    GRASS: BlockDef(GRASS, "grass", "grass_top", "grass_side", "dirt"),
    DIRT: BlockDef(DIRT, "dirt", "dirt"),
    STONE: BlockDef(STONE, "stone", "stone"),
    SAND: BlockDef(SAND, "sand", "sand"),
    WATER: BlockDef(WATER, "water", "water", solid=False, transparent=True, breakable=False),
    WOOD: BlockDef(WOOD, "wood", "wood_top", "wood_side", "wood_top"),
    LEAVES: BlockDef(LEAVES, "leaves", "leaves", transparent=True),
    BEDROCK: BlockDef(BEDROCK, "bedrock", "bedrock", breakable=False),
    PLANKS: BlockDef(PLANKS, "planks", "planks"),
    COBBLESTONE: BlockDef(COBBLESTONE, "cobblestone", "cobblestone"),
    COAL_ORE: BlockDef(COAL_ORE, "coal_ore", "coal_ore"),
    IRON_ORE: BlockDef(IRON_ORE, "iron_ore", "iron_ore"),
    DIAMOND_ORE: BlockDef(DIAMOND_ORE, "diamond_ore", "diamond_ore"),
    CRAFTING_TABLE: BlockDef(CRAFTING_TABLE, "crafting_table", "crafting_table_top",
                              "crafting_table_side", "planks"),
}

# Oyuncunun elle koyabileceği bloklar (hotbar / creative envanteri için sıralı liste)
PLACEABLE = [GRASS, DIRT, STONE, SAND, WOOD, LEAVES, PLANKS, COBBLESTONE,
             COAL_ORE, IRON_ORE, DIAMOND_ORE, CRAFTING_TABLE]

# Blok kırılınca envantere hangi item'ın düşeceği (belirtilmeyenler kendi id'sini düşürür).
# Gerçek Minecraft'taki gibi: TAŞ kırınca MOLOZ TAŞI (cobblestone) düşer.
# Cevherler ise item modülündeki ham madenleri (kömür/demir/elmas) düşürür - bunlar
# items.py'de tanımlı, burada blocks.py'nin items.py'ye bağımlı olmaması için
# sadece işaretçi olarak orion (ore) blok id'lerini bırakıyoruz; gerçek eşleme
# main.py'de items.ORE_DROPS ile yapılıyor.
BREAK_DROPS = {
    STONE: COBBLESTONE,
}
