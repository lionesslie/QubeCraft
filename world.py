"""
Chunk tabanlı dünya: 16x16 (x,z) genişliğinde, WORLD_HEIGHT yükseklikte parçalar.
Seed verilen bir noise fonksiyonuyla yükseklik haritası üretilir; düşük frekanslı
bir "mountain_factor" noise'u alanın ova mı dağ mı olacağını belirler.
"""
from __future__ import annotations
import numpy as np
from noise_gen import PerlinNoise2D
import blocks as B

CHUNK_SIZE = 16
WORLD_HEIGHT = 64
SEA_LEVEL = 22


def _smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Chunk:
    __slots__ = ("cx", "cz", "blocks", "dirty", "vertex_list", "has_tree_pass")

    def __init__(self, cx, cz):
        self.cx = cx
        self.cz = cz
        self.blocks = np.zeros((CHUNK_SIZE, WORLD_HEIGHT, CHUNK_SIZE), dtype=np.uint8)
        self.dirty = True          # mesh yeniden inşa edilmeli mi
        self.vertex_list = None    # main.py/mesh.py tarafından doldurulur
        self.has_tree_pass = False

    def local_get(self, lx, ly, lz):
        if 0 <= ly < WORLD_HEIGHT:
            return self.blocks[lx, ly, lz]
        return B.AIR

    def local_set(self, lx, ly, lz, block_id):
        if 0 <= ly < WORLD_HEIGHT:
            self.blocks[lx, ly, lz] = block_id
            self.dirty = True


class World:
    def __init__(self, seed: int):
        self.seed = seed
        self.noise = PerlinNoise2D(seed)
        self.chunks: dict[tuple[int, int], Chunk] = {}
        # Ağaç yerleşimi için ayrı, deterministik bir RNG kaynağı (chunk koordinatına göre)
        self._tree_seed = seed * 7919 + 104729

    # ---------- chunk / koordinat yardımcıları ----------

    @staticmethod
    def world_to_chunk(x, z):
        return x // CHUNK_SIZE, z // CHUNK_SIZE

    def get_chunk(self, cx, cz, create=True):
        key = (cx, cz)
        chunk = self.chunks.get(key)
        if chunk is None and create:
            chunk = self._generate_chunk(cx, cz)
            self.chunks[key] = chunk
        return chunk

    def height_at(self, wx, wz):
        """Belirli bir dünya koordinatı için arazi yüksekliğini hesaplar (blok üretmeden)."""
        continent = self.noise.fbm(wx, wz, octaves=3, persistence=0.5, lacunarity=2.0, scale=200.0)
        mountain_factor = float(_smoothstep(-0.03, 0.09, np.array(continent)))
        hills = self.noise.fbm(wx, wz, octaves=5, persistence=0.5, lacunarity=2.0, scale=48.0)
        detail = self.noise.fbm(wx, wz, octaves=2, persistence=0.5, lacunarity=2.0, scale=9.0)

        height = SEA_LEVEL + 4 + hills * 14 + mountain_factor * (hills * 46 + 14) + detail * 2.5
        height = int(np.clip(round(height), 2, WORLD_HEIGHT - 3))
        return height, mountain_factor

    # ---------- terrain üretimi ----------

    def _generate_chunk(self, cx, cz) -> Chunk:
        chunk = Chunk(cx, cz)
        base_x = cx * CHUNK_SIZE
        base_z = cz * CHUNK_SIZE

        heightmap = np.empty((CHUNK_SIZE, CHUNK_SIZE), dtype=np.int32)
        for lx in range(CHUNK_SIZE):
            for lz in range(CHUNK_SIZE):
                h, _ = self.height_at(base_x + lx, base_z + lz)
                heightmap[lx, lz] = h

        for lx in range(CHUNK_SIZE):
            for lz in range(CHUNK_SIZE):
                h = int(heightmap[lx, lz])
                col = chunk.blocks[lx, :, lz]
                col[0] = B.BEDROCK
                if h > 1:
                    col[1:max(1, h - 4)] = B.STONE
                    col[max(1, h - 4):max(1, h - 1)] = B.DIRT
                top_id = B.GRASS if h > SEA_LEVEL + 1 else B.SAND
                col[max(1, h - 1):h] = top_id
                if h <= SEA_LEVEL:
                    col[h:SEA_LEVEL + 1] = B.WATER

        self._place_ores(chunk, heightmap, base_x, base_z)
        self._place_trees(chunk, heightmap)
        chunk.dirty = True
        return chunk

    def _place_ores(self, chunk, heightmap, base_x, base_z):
        """Taş bölgesine derinliğe göre kömür/demir/elmas cevheri serper.
        Elmas en derinde ve en nadir, kömür sığ/orta derinlikte en yaygın."""
        raw_seed = (self.seed * 486187739 + chunk.cx * 341873128712 + chunk.cz * 132897987541)
        rng = np.random.default_rng(raw_seed & 0xFFFFFFFF)
        for lx in range(CHUNK_SIZE):
            for lz in range(CHUNK_SIZE):
                h = int(heightmap[lx, lz])
                stone_top = max(1, h - 4)
                for y in range(1, stone_top):
                    r = rng.random()
                    if y <= 12 and r < 0.018:
                        chunk.blocks[lx, y, lz] = B.DIAMOND_ORE
                    elif y <= 28 and r < 0.03:
                        chunk.blocks[lx, y, lz] = B.IRON_ORE
                    elif r < 0.045:
                        chunk.blocks[lx, y, lz] = B.COAL_ORE

    def _place_trees(self, chunk: Chunk, heightmap):
        raw_seed = self._tree_seed + chunk.cx * 341873128712 + chunk.cz * 132897987541
        rng = np.random.default_rng(raw_seed & 0xFFFFFFFF)
        for lx in range(2, CHUNK_SIZE - 2):
            for lz in range(2, CHUNK_SIZE - 2):
                h = int(heightmap[lx, lz])
                if h <= SEA_LEVEL + 1:
                    continue  # sudaki/kumsaldaki bloklara ağaç dikme
                if chunk.blocks[lx, h - 1, lz] != B.GRASS:
                    continue
                if rng.random() < 0.012:  # ~%1.2 ihtimalle ağaç
                    self._build_tree(chunk, lx, h, lz, rng)

    @staticmethod
    def _build_tree(chunk: Chunk, lx, base_y, lz, rng):
        trunk_h = int(rng.integers(4, 7))
        for i in range(trunk_h):
            chunk.local_set(lx, base_y + i, lz, B.WOOD)
        leaf_center_y = base_y + trunk_h - 1
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(-1, 3):
                    if abs(dx) == 2 and abs(dz) == 2:
                        continue  # köşeleri yuvarlat
                    lxx, lzz, lyy = lx + dx, lz + dz, leaf_center_y + dy
                    if 0 <= lxx < CHUNK_SIZE and 0 <= lzz < CHUNK_SIZE:
                        if chunk.local_get(lxx, lyy, lzz) == B.AIR:
                            chunk.local_set(lxx, lyy, lzz, B.LEAVES)

    # ---------- global blok erişimi ----------

    def get_block(self, x, y, z):
        if y < 0 or y >= WORLD_HEIGHT:
            return B.AIR
        cx, cz = self.world_to_chunk(x, z)
        chunk = self.get_chunk(cx, cz, create=True)
        lx, lz = x - cx * CHUNK_SIZE, z - cz * CHUNK_SIZE
        return int(chunk.blocks[lx, y, lz])

    def set_block(self, x, y, z, block_id):
        if y < 0 or y >= WORLD_HEIGHT:
            return []
        cx, cz = self.world_to_chunk(x, z)
        chunk = self.get_chunk(cx, cz, create=True)
        lx, lz = x - cx * CHUNK_SIZE, z - cz * CHUNK_SIZE
        chunk.local_set(lx, y, lz, block_id)

        dirty_chunks = [(cx, cz)]
        # Chunk sınırındaysa komşu chunk'ın da yüz kaplamasını (culling) güncellemesi gerekir
        if lx == 0:
            dirty_chunks.append((cx - 1, cz))
        if lx == CHUNK_SIZE - 1:
            dirty_chunks.append((cx + 1, cz))
        if lz == 0:
            dirty_chunks.append((cx, cz - 1))
        if lz == CHUNK_SIZE - 1:
            dirty_chunks.append((cx, cz + 1))
        for key in dirty_chunks:
            c = self.chunks.get(key)
            if c is not None:
                c.dirty = True
        return dirty_chunks

    def is_solid(self, x, y, z):
        return B.BLOCKS[self.get_block(x, y, z)].solid

    def spawn_height(self, x, z):
        h, _ = self.height_at(x, z)
        return h + 1
