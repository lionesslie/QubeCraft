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
}

# Oyuncunun elle koyabileceği bloklar (hotbar / creative envanteri için sıralı liste)
PLACEABLE = [GRASS, DIRT, STONE, SAND, WOOD, LEAVES, PLANKS, COBBLESTONE]
