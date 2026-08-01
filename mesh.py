"""
Bir chunk'ın görünür (komşusu hava/şeffaf olan) yüzlerini bulup, KULLANILAN
TEXTURE İSMİNE GÖRE GRUPLANMIŞ OpenGL mesh verisi (vertices/tex_coords/colors)
üretir. Artık paylaşılan bir atlas yok; her blok yüzü kendi tam texture'ını
([0,0]-[1,1] UV aralığı) kullanıyor, bu yüzden aynı chunk içinde farklı
texture'lar için ayrı ayrı vertex grupları gerekiyor.

Bilerek pyglet'e bağımlı DEĞİL: main.py bu sözlüğü alıp her texture ismi için
ayrı bir pyglet vertex_list/texture bind işlemine çevirir.
"""
import blocks as B
from world import CHUNK_SIZE, WORLD_HEIGHT

# face adı -> (4 köşe ofseti (blok orijinine göre), (dx,dy,dz) komşu blok yönü)
FACES = {
    "top":    ([(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)], (0, 1, 0)),
    "bottom": ([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], (0, -1, 0)),
    "front":  ([(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], (0, 0, 1)),
    "back":   ([(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)], (0, 0, -1)),
    "right":  ([(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)], (1, 0, 0)),
    "left":   ([(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)], (-1, 0, 0)),
}
FULL_UV = [(0, 0), (1, 0), (1, 1), (0, 1)]

# Basit sahte-ışıklandırma: yöne göre parlaklık çarpanı (0-255 renk kanalı)
FACE_SHADE = {
    "top": 255, "bottom": 130, "front": 200, "back": 200, "right": 170, "left": 170,
}


def _face_texture(block_def, face_name):
    if face_name == "top":
        return block_def.top
    if face_name == "bottom":
        return block_def.bottom
    return block_def.side


def build_chunk_mesh(world, chunk):
    """
    Döner: dict[texture_name] -> (vertices, tex_coords, colors)
      vertices:   [x,y,z, x,y,z, ...]           (her yüz için 4 köşe x 3)
      tex_coords: [u,v, u,v, ...]                (her yüz için 4 köşe x 2, her zaman 0..1)
      colors:     [r,g,b, r,g,b, ...] (0-255)    (her yüz için 4 köşe x 3)
    Her texture ismi GL_QUADS ile ayrı ayrı çizilmeye hazırdır.
    """
    groups = {}  # texture_name -> [vertices, tex_coords, colors]

    def _get_group(name):
        g = groups.get(name)
        if g is None:
            g = ([], [], [])
            groups[name] = g
        return g

    base_x = chunk.cx * CHUNK_SIZE
    base_z = chunk.cz * CHUNK_SIZE
    blocks_arr = chunk.blocks

    for lx in range(CHUNK_SIZE):
        wx = base_x + lx
        for lz in range(CHUNK_SIZE):
            wz = base_z + lz
            column = blocks_arr[lx, :, lz]
            nz = column.nonzero()[0]
            if len(nz) == 0:
                continue
            y_min, y_max = int(nz.min()), int(nz.max())
            for ly in range(y_min, y_max + 1):
                block_id = int(blocks_arr[lx, ly, lz])
                if block_id == B.AIR:
                    continue
                block_def = B.BLOCKS[block_id]
                wy = ly

                for face_name, (offsets, (dx, dy, dz)) in FACES.items():
                    nx, ny, nz2 = lx + dx, ly + dy, lz + dz
                    if 0 <= nx < CHUNK_SIZE and 0 <= ny < WORLD_HEIGHT and 0 <= nz2 < CHUNK_SIZE:
                        neighbor_id = int(blocks_arr[nx, ny, nz2])
                    else:
                        neighbor_id = world.get_block(wx + dx, ly + dy, wz + dz)

                    neighbor_def = B.BLOCKS[neighbor_id]
                    if not (neighbor_def.transparent and (neighbor_id != block_id)):
                        continue

                    tex_name = _face_texture(block_def, face_name)
                    shade = FACE_SHADE[face_name]
                    verts, uvs, colors = _get_group(tex_name)

                    for (ox, oy, oz), (uu, vv) in zip(offsets, FULL_UV):
                        verts.extend((wx + ox, wy + oy, wz + oz))
                        uvs.extend((uu, vv))
                        colors.extend((shade, shade, shade))

    return groups
