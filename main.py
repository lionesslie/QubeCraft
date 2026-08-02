"""
Python + Pyglet/OpenGL Minecraft klonu

Bu sürümde var olanlar:
  - Seed'li noise ile prosedürel dünya (dağlar, ovalar, sahiller, su)
  - Chunk (16x16) tabanlı dünya, ağaçlar
  - Yeraltı madenleri: kömür, demir, elmas (derinliğe göre dağılım)
  - Her blok yüzü için ayrı 16x16 piksel-art texture dosyası (paylaşılan atlas yok)
  - Birinci şahıs kamera, yürüme/koşma/zıplama (survival) ya da uçma (creative)
  - Blok kırma / koyma - survival'da alete göre değişen kazma HIZI
    (kazma/balta/kılıç x tahta/taş/demir/elmas, 12 alet + doğru kategori/tier kontrolü)
  - Can barı + açlık barı (nokta/kalp şeklinde), düşme hasarı, açlıktan hasar, respawn
  - Tam envanter: hotbar (9) + ana grid (3x9), yığın sistemi, al/bırak/birleştir/takas
  - Crafting: 14 tarif (tahta->çubuk, 4 tier x 3 alet türü), envanter ekranından craft
  - Başlangıç menüsü: seed girme, oyun modu seçimi, görüş mesafesi (görsel panel)
  - Oyun içi duraklatma menüsü: dünya/oyuncu bilgisi, can/açlık, ayarlar

Henüz YOK (bir sonraki adımlarda eklenecek): combat/canlı düşmanlar, ateş/pişirme
(demir cevheri direkt "demir" düşürüyor, gerçek Minecraft'taki fırın/smelting yok),
yiyecek/çiftçilik (açlık şu an sadece azalıyor, geri dolduracak yiyecek yok),
dünya kaydetme/yükleme, chunk unload.

Çalıştırmak için (kendi bilgisayarında):
    pip install -r requirements.txt
    python main.py
"""
from __future__ import annotations

import math
import random
import time
from collections import deque

import pyglet
from pyglet import gl
from pyglet.window import key, mouse

import blocks as B
import items as I
import crafting as C
from world import World, CHUNK_SIZE, SEA_LEVEL
from mesh import build_chunk_mesh
from player import Player, MAX_HEALTH, MAX_HUNGER
from inventory import Inventory, HOTBAR_SIZE, MAIN_ROWS, MAIN_COLS
import textures as TEX

WINDOW_W, WINDOW_H = 1024, 640
TICK_RATE = 1 / 60.0
CHUNK_BUILD_BUDGET = 2       # frame başına en fazla kaç yeni chunk mesh'lensin
DEFAULT_RENDER_DISTANCE = 4  # chunk cinsinden (yarıçap)
CREATIVE_STACK = 64

STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_INVENTORY = "inventory"
STATE_CRAFTING_TABLE = "crafting_table"
INVENTORY_STATES = (STATE_INVENTORY, STATE_CRAFTING_TABLE)


# ---------------------------------------------------------------- yardımcılar

def _average_color(path):
    """Bir PNG'nin ortalama rengini döner - hotbar/envanter ikonlarında kullanılır."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    small = img.resize((1, 1))
    return small.getpixel((0, 0))


TOOL_TIER_COLOR = {
    "wood": (156, 110, 66), "stone": (150, 150, 150),
    "iron": (216, 216, 200), "diamond": (100, 220, 210),
}


def item_icon_color(game, item_id):
    item = I.ITEMS.get(item_id)
    if item is None:
        return (200, 200, 200)
    if item.tool_tier:
        return TOOL_TIER_COLOR[item.tool_tier]
    block_def = B.BLOCKS.get(item_id)
    if block_def is not None:
        return game.texture_colors.get(block_def.top, (200, 200, 200))
    return (230, 230, 230)


# ---------------------------------------------------------------- ana pencere

class Game(pyglet.window.Window):
    def __init__(self):
        super().__init__(width=WINDOW_W, height=WINDOW_H, caption="PyCraft",
                          resizable=True, vsync=True)
        gl.glClearColor(0.53, 0.75, 0.92, 1.0)  # gökyüzü rengi

        # texture dosyaları henüz yoksa üret
        import os
        if not os.path.exists("assets/grass_top.png"):
            TEX.build_individual_textures()
        if not os.path.exists("assets/icon_wood_pickaxe.png"):
            TEX.build_tool_icons()
        self.textures = {}       # texture ismi -> pyglet Texture
        self.texture_colors = {}  # texture ismi -> (r,g,b) ortalama renk (ikon rengi için)
        self.texture_groups = {}  # texture ismi -> pyglet.graphics.TextureGroup
        for name in TEX.TEXTURE_NAMES:
            pil_avg = _average_color(f"assets/{name}.png")
            self.texture_colors[name] = pil_avg
            img = pyglet.image.load(f"assets/{name}.png").get_texture()
            gl.glBindTexture(gl.GL_TEXTURE_2D, img.id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            self.textures[name] = img
            self.texture_groups[name] = pyglet.graphics.TextureGroup(img)

        # PERFORMANS: tüm chunk'lar TEK paylaşılan Batch'e ekleniyor. pyglet
        # Batch, aynı TextureGroup'a sahip vertex_list'leri otomatik olarak
        # gruplayıp minimum texture bind ile TEK seferde çiziyor - chunk
        # başına chunk başına ayrı draw call yapmaktan çok daha hızlı.
        self.batch = pyglet.graphics.Batch()

        self.tool_icons = {}  # (kind,tier) -> pyglet Texture (hotbar/envanter ikonu)
        for tier in I.TIERS:
            for kind in I.TOOL_KINDS:
                path = f"assets/icon_{tier}_{kind}.png"
                img = pyglet.image.load(path).get_texture()
                gl.glBindTexture(gl.GL_TEXTURE_2D, img.id)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
                self.tool_icons[(kind, tier)] = img

        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # NOT: GL_CULL_FACE bilerek KAPALI. Yüz sırası (winding) matematiksel
        # olarak doğru hesaplandı ama render bozukluğunu ararken bir
        # değişkeni daha elemek için culling'i devre dışı bıraktık. Her şey
        # düzgün çalıştıktan sonra performans için tekrar açılabilir.

        self.state = STATE_MENU
        self.keys_down = set()
        self.exclusive_mouse = False

        # --- menü durumu ---
        self.menu_seed_text = ""
        self.menu_mode = "survival"
        self.menu_render_distance = DEFAULT_RENDER_DISTANCE

        # --- oyun durumu (start_world çağrılınca doldurulur) ---
        self.world: World | None = None
        self.player: Player | None = None
        self.inventory: Inventory | None = None
        self.loaded_chunks = set()
        self.pending_chunks = deque()
        self.pending_set = set()
        self.render_distance = DEFAULT_RENDER_DISTANCE
        self.world_name = "World1"
        self.mouse_sensitivity = 0.15
        self.fps_display = pyglet.window.FPSDisplay(self)
        self.debug_overlay = True
        self._mouse_pos = (WINDOW_W // 2, WINDOW_H // 2)
        self.mouse_left_down = False
        self.breaking = None  # {"pos": (x,y,z), "progress": 0..1, "total": saniye}
        self.craft_grid = [[None, None, None] for _ in range(3)]  # her hücre [item_id,count] ya da None
        self.crafting_table_pos = None  # STATE_CRAFTING_TABLE'dayken bakılan masanın konumu
        self._cached_raycast = None    # bu karede hesaplanan raycast (outline+mining paylaşır)
        self._label_cache = {}
        self._shape_cache = {}

        pyglet.clock.schedule_interval(self.update, TICK_RATE)

    # ------------------------------------------------------------ UI önbellekleme
    # PERFORMANS: pyglet.text.Label / pyglet.shapes.* nesnelerini her karede
    # sıfırdan oluşturmak (glyph texture + vertex buffer yeniden ayırma
    # anlamına geliyor) FPS'i ciddi şekilde düşürüyordu. Bunun yerine aynı
    # mantıksal UI öğesi için nesneyi BİR KERE oluşturup sonraki karelerde
    # sadece x/y/text/color gibi alanlarını güncelliyoruz.

    def _label(self, key, text, **kwargs):
        lbl = self._label_cache.get(key)
        if lbl is None:
            lbl = pyglet.text.Label(text, **kwargs)
            self._label_cache[key] = lbl
        else:
            if lbl.text != text:
                lbl.text = text
            for attr in ("x", "y", "color", "font_size"):
                if attr in kwargs and getattr(lbl, attr) != kwargs[attr]:
                    setattr(lbl, attr, kwargs[attr])
        return lbl

    def _rect(self, key, x, y, w, h, color, opacity=255):
        r = self._shape_cache.get(key)
        if r is None:
            r = pyglet.shapes.Rectangle(x, y, w, h, color=color)
            self._shape_cache[key] = r
        else:
            r.x, r.y, r.width, r.height, r.color = x, y, w, h, color
        r.opacity = opacity
        return r

    def _brect(self, key, x, y, w, h, border, color, border_color):
        r = self._shape_cache.get(key)
        if r is None:
            r = pyglet.shapes.BorderedRectangle(x, y, w, h, border=border,
                                                 color=color, border_color=border_color)
            self._shape_cache[key] = r
        else:
            r.x, r.y, r.width, r.height = x, y, w, h
            r.color = color
            r.border_color = border_color
        return r

    def _circle(self, key, x, y, radius, color):
        c = self._shape_cache.get(key)
        if c is None:
            c = pyglet.shapes.Circle(x, y, radius, color=color)
            self._shape_cache[key] = c
        else:
            c.x, c.y, c.radius, c.color = x, y, radius, color
        return c

    # ------------------------------------------------------------ menü UI

    def start_world(self):
        seed = int(self.menu_seed_text) if self.menu_seed_text.strip().isdigit() \
            else random.randint(0, 10_000_000)
        self.world = World(seed=seed)
        self.player = Player(self.world, 0.5, 0.5, mode=self.menu_mode)
        self.inventory = Inventory()
        if self.menu_mode == "creative":
            for i, block_id in enumerate(B.PLACEABLE[:HOTBAR_SIZE]):
                self.inventory.hotbar[i] = [block_id, CREATIVE_STACK]
        self.loaded_chunks = set()
        self.pending_chunks = deque()
        self.pending_set = set()
        self.render_distance = self.menu_render_distance
        self.seed_used = seed
        self.state = STATE_PLAYING
        self.mouse_left_down = False
        self.breaking = None
        self.craft_grid = [[None, None, None] for _ in range(3)]
        self.crafting_table_pos = None
        self.set_exclusive_mouse(True)
        self._queue_chunks_around_player()

    # ------------------------------------------------------------ chunk akışı

    def _queue_chunks_around_player(self):
        pcx = int(math.floor(self.player.x)) // CHUNK_SIZE
        pcz = int(math.floor(self.player.z)) // CHUNK_SIZE
        rd = self.render_distance
        needed = []
        for dx in range(-rd, rd + 1):
            for dz in range(-rd, rd + 1):
                if dx * dx + dz * dz <= rd * rd:
                    needed.append((pcx + dx, pcz + dz))
        needed.sort(key=lambda c: (c[0] - pcx) ** 2 + (c[1] - pcz) ** 2)
        for coord in needed:
            if coord not in self.loaded_chunks and coord not in self.pending_set:
                self.pending_chunks.append(coord)
                self.pending_set.add(coord)

    def _process_pending_chunks(self):
        built = 0
        while self.pending_chunks and built < CHUNK_BUILD_BUDGET:
            cx, cz = self.pending_chunks.popleft()
            self.pending_set.discard((cx, cz))
            chunk = self.world.get_chunk(cx, cz)
            self._rebuild_chunk_mesh(chunk)
            self.loaded_chunks.add((cx, cz))
            built += 1

    def _rebuild_dirty_chunks(self, budget=2):
        done = 0
        for coord in list(self.loaded_chunks):
            if done >= budget:
                break
            chunk = self.world.chunks.get(coord)
            if chunk is not None and chunk.dirty:
                self._rebuild_chunk_mesh(chunk)
                done += 1

    def _rebuild_chunk_mesh(self, chunk):
        if chunk.vertex_list:
            for vl in chunk.vertex_list.values():
                vl.delete()
        chunk.vertex_list = {}
        groups = build_chunk_mesh(self.world, chunk)
        for tex_name, (verts, uvs, colors) in groups.items():
            count = len(verts) // 3
            if count > 0:
                chunk.vertex_list[tex_name] = self.batch.add(
                    count, gl.GL_QUADS, self.texture_groups[tex_name],
                    ("v3f/dynamic", verts),
                    ("t2f/dynamic", uvs),
                    ("c3B/dynamic", colors),
                )
        chunk.dirty = False

    # ------------------------------------------------------------ input

    def on_key_press(self, symbol, modifiers):
        self.keys_down.add(symbol)

        if self.state == STATE_MENU:
            if symbol == key.ENTER:
                self.start_world()
            elif symbol == key.C:
                self.menu_mode = "creative"
            elif symbol == key.S:
                self.menu_mode = "survival"
            elif symbol == key.UP:
                self.menu_render_distance = min(8, self.menu_render_distance + 1)
            elif symbol == key.DOWN:
                self.menu_render_distance = max(2, self.menu_render_distance - 1)
            elif symbol == key.BACKSPACE:
                self.menu_seed_text = self.menu_seed_text[:-1]
            return

        if symbol == key.ESCAPE:
            if self.state == STATE_PLAYING:
                self.state = STATE_PAUSED
                self.mouse_left_down = False
                self.breaking = None
                self.set_exclusive_mouse(False)
            elif self.state == STATE_PAUSED:
                self.state = STATE_PLAYING
                self.set_exclusive_mouse(True)
            elif self.state in INVENTORY_STATES:
                self._close_inventory()
            return

        if symbol == key.E:
            if self.state == STATE_PLAYING:
                hit = self.player.raycast(self.world, max_distance=6.0)
                if hit is not None and self.world.get_block(*hit[0]) == B.CRAFTING_TABLE:
                    self.state = STATE_CRAFTING_TABLE
                    self.crafting_table_pos = hit[0]
                else:
                    self.state = STATE_INVENTORY
                self.mouse_left_down = False
                self.breaking = None
                self.set_exclusive_mouse(False)
            elif self.state in INVENTORY_STATES:
                self._close_inventory()
            return

        if self.state == STATE_PAUSED:
            if symbol == key.G:
                new_mode = "creative" if self.player.mode == "survival" else "survival"
                self.player.set_mode(new_mode)
            elif symbol in (key.EQUAL, key.PLUS):
                self.render_distance = min(8, self.render_distance + 1)
                self._queue_chunks_around_player()
            elif symbol == key.MINUS:
                self.render_distance = max(2, self.render_distance - 1)
            elif symbol == key.Q:
                self.state = STATE_MENU
                self.set_exclusive_mouse(False)
            return

        if self.state == STATE_PLAYING:
            if symbol == key.F3:
                self.debug_overlay = not self.debug_overlay
            num_keys = [key._1, key._2, key._3, key._4, key._5, key._6, key._7, key._8, key._9]
            if symbol in num_keys:
                self.inventory.selected_hotbar = num_keys.index(symbol)

    def _close_inventory(self):
        """Envanter/crafting ekranını kapatır; elde tutulan (cursor) stack ve
        crafting grid'inde kalan malzemeler varsa envantere geri dağıtılır."""
        self.inventory.drop_cursor_into_inventory()
        for row in self.craft_grid:
            for i, cell in enumerate(row):
                if cell is not None:
                    self.inventory.add_item(cell[0], cell[1])
                    row[i] = None
        self.crafting_table_pos = None
        self.state = STATE_PLAYING
        self.set_exclusive_mouse(True)

    def on_key_release(self, symbol, modifiers):
        self.keys_down.discard(symbol)

    def on_text(self, text):
        if self.state == STATE_MENU and text.isdigit() and len(self.menu_seed_text) < 9:
            self.menu_seed_text += text

    def on_mouse_motion(self, x, y, dx, dy):
        self._mouse_pos = (x, y)
        if self.state == STATE_PLAYING:
            self.player.add_look(dx, dy, self.mouse_sensitivity)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._mouse_pos = (x, y)
        if self.state == STATE_PLAYING:
            self.player.add_look(dx, dy, self.mouse_sensitivity)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if self.state == STATE_PLAYING:
            self.inventory.selected_hotbar = (self.inventory.selected_hotbar - int(scroll_y)) % HOTBAR_SIZE

    def on_mouse_press(self, x, y, button, modifiers):
        if button != mouse.LEFT and self.state in (STATE_MENU, STATE_PAUSED):
            return
        if self.state == STATE_MENU:
            self._handle_menu_click(x, y)
            return
        if self.state == STATE_PAUSED:
            self._handle_pause_click(x, y)
            return
        if self.state in INVENTORY_STATES:
            if button == mouse.LEFT:
                self._handle_inventory_click(x, y, right=False)
            elif button == mouse.RIGHT:
                self._handle_inventory_click(x, y, right=True)
            return
        if self.state != STATE_PLAYING:
            return

        if button == mouse.LEFT:
            self.mouse_left_down = True
            if self.player.mode == "creative":
                hit = self.player.raycast(self.world, max_distance=6.0)
                if hit is not None:
                    self._break_block_instant(hit[0])
        elif button == mouse.RIGHT:
            hit = self.player.raycast(self.world, max_distance=6.0)
            if hit is not None:
                self._place_block(hit[1])

    def _handle_menu_click(self, mx, my):
        panel_w, panel_h, mode_rects, rd_rects, start_rect = self._menu_layout()

        def hit(rect):
            rx, ry, rw, rh = rect
            return rx <= mx <= rx + rw and ry <= my <= ry + rh

        if hit(mode_rects["survival"]):
            self.menu_mode = "survival"
        elif hit(mode_rects["creative"]):
            self.menu_mode = "creative"
        elif hit(rd_rects["rd_minus"]):
            self.menu_render_distance = max(2, self.menu_render_distance - 1)
        elif hit(rd_rects["rd_plus"]):
            self.menu_render_distance = min(8, self.menu_render_distance + 1)
        elif hit(start_rect):
            self.start_world()

    def _handle_pause_click(self, mx, my):
        rects = self._pause_layout()

        def hit(rect):
            rx, ry, rw, rh = rect
            return rx <= mx <= rx + rw and ry <= my <= ry + rh

        if hit(rects["resume"]):
            self.state = STATE_PLAYING
            self.set_exclusive_mouse(True)
        elif hit(rects["quit"]):
            self.state = STATE_MENU
            self.set_exclusive_mouse(False)

    def on_mouse_release(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            self.mouse_left_down = False
            self.breaking = None

    def _update_mining(self, dt):
        """Survival'da sol tık basılıysa kırma ilerlemesini işler (aletle hız değişir)."""
        if self.player.mode != "survival" or not self.mouse_left_down:
            self.breaking = None
            return
        hit = self._cached_raycast
        if hit is None:
            self.breaking = None
            return
        pos, _ = hit
        block_id = self.world.get_block(*pos)
        block_def = B.BLOCKS[block_id]
        if not block_def.breakable:
            self.breaking = None
            return

        held_item = self.inventory.selected_block()
        total = I.mining_seconds(block_id, held_item)

        if self.breaking is None or self.breaking["pos"] != pos:
            self.breaking = {"pos": pos, "progress": 0.0, "total": total}
        else:
            self.breaking["progress"] += dt / max(0.05, total)
            if self.breaking["progress"] >= 1.0:
                self._break_block_survival(pos, held_item)
                self.breaking = None

    def _break_block_instant(self, pos):
        """Creative: alet/hız umursanmadan anında kırar, envantere hiçbir şey eklemez."""
        bx, by, bz = pos
        block_def = B.BLOCKS[self.world.get_block(bx, by, bz)]
        if not block_def.breakable:
            return
        self.world.set_block(bx, by, bz, B.AIR)

    def _break_block_survival(self, pos, held_item):
        bx, by, bz = pos
        block_id = self.world.get_block(bx, by, bz)
        self.world.set_block(bx, by, bz, B.AIR)
        drop_id, drop_count = I.get_drop(block_id, held_item)
        if drop_id is not None and drop_count > 0:
            self.inventory.add_item(drop_id, drop_count)

    def _handle_inventory_click(self, mx, my, right=False):
        hotbar_rects, main_rects, palette_rects, craft_rects, result_rect = self._inventory_layout()
        for index, rx, ry, size in hotbar_rects + main_rects:
            if rx <= mx <= rx + size and ry <= my <= ry + size:
                if right:
                    self.inventory.right_click_slot(index)
                else:
                    self.inventory.click_slot(index)
                return
        if self.player.mode == "creative" and not right:
            for block_id, rx, ry, size in palette_rects:
                if rx <= mx <= rx + size and ry <= my <= ry + size:
                    # Palet sınırsızdır: tıklanınca eldeki (cursor) her neyse
                    # üzerine yeni, dolu bir yığın alınır.
                    self.inventory.cursor = [block_id, CREATIVE_STACK]
                    return
        for row, col, rx, ry, size in craft_rects:
            if rx <= mx <= rx + size and ry <= my <= ry + size:
                get_fn = lambda r=row, c=col: self.craft_grid[r][c]
                set_fn = lambda v, r=row, c=col: self.craft_grid[r].__setitem__(c, v)
                if right:
                    self.inventory.right_click_external(get_fn, set_fn)
                else:
                    self.inventory.click_external(get_fn, set_fn)
                return
        if not right:
            rx, ry, size = result_rect
            if rx <= mx <= rx + size and ry <= my <= ry + size:
                self._try_craft()

    def _try_craft(self):
        """Sonuç slotuna tıklanınca: eşleşen tarif varsa ürünü cursor'a ekler (mevcut
        cursor içeriğiyle aynı item ise birleştirir, farklıysa ya da yer yoksa üretime izin vermez)."""
        recipe = C.match(self.craft_grid)
        if recipe is None:
            return
        if self.inventory.cursor is not None:
            if self.inventory.cursor[0] != recipe.output_id:
                return
            if self.inventory.cursor[1] + recipe.output_count > I.stack_max(recipe.output_id):
                return  # cursor'da yer yok (örn. tek seferde 1'e kadar alet)
        produced = C.craft_once(self.craft_grid)
        if produced is None:
            return
        out_id, out_count = produced
        if self.inventory.cursor is None:
            self.inventory.cursor = [out_id, out_count]
        else:
            self.inventory.cursor[1] += out_count

    def _place_block(self, pos):
        bx, by, bz = pos
        selected = self.inventory.selected_block()
        if selected is None or selected not in B.PLACEABLE:
            return  # alet ya da yerleştirilemeyen bir item seçili
        # oyuncunun kendi bulunduğu hücreye blok koymayı engelle
        px, py, pz = math.floor(self.player.x), math.floor(self.player.y), math.floor(self.player.z)
        py2 = math.floor(self.player.y + 1.0)
        if (bx, by, bz) in {(px, py, pz), (px, py2, pz)}:
            return
        if self.player.mode == "creative":
            self.world.set_block(bx, by, bz, selected)
        else:
            if self.inventory.take_from_hotbar(self.inventory.selected_hotbar, 1):
                self.world.set_block(bx, by, bz, selected)

    # ------------------------------------------------------------ update / render

    def update(self, dt):
        if self.state != STATE_PLAYING:
            return
        action_state = {
            "forward": key.W in self.keys_down,
            "back": key.S in self.keys_down,
            "left": key.A in self.keys_down,
            "right": key.D in self.keys_down,
            "jump": key.SPACE in self.keys_down,
            "sneak_down": key.LSHIFT in self.keys_down,
            "sprint": key.LCTRL in self.keys_down,
        }
        self.player.update(dt, action_state, self.world)
        self._cached_raycast = self.player.raycast(self.world, max_distance=6.0)
        self._update_mining(dt)
        self._queue_chunks_around_player()
        self._process_pending_chunks()
        self._rebuild_dirty_chunks()

    def set_3d(self):
        width, height = self.get_size()
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glViewport(0, 0, max(1, width), max(1, height))
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        fov, near, far = 65.0, 0.1, 300.0
        aspect = width / float(height or 1)
        top = near * math.tan(math.radians(fov) / 2)
        bottom = -top
        right = top * aspect
        left = -right
        gl.glFrustum(left, right, bottom, top, near, far)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

        yaw, pitch = self.player.yaw, self.player.pitch
        gl.glRotatef(yaw, 0, 1, 0)
        gl.glRotatef(-pitch, math.cos(math.radians(yaw)), 0, math.sin(math.radians(yaw)))
        ex, ey, ez = self.player.eye_position()
        gl.glTranslatef(-ex, -ey, -ez)

    def set_2d(self):
        width, height = self.get_size()
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glOrtho(0, max(1, width), 0, max(1, height), -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

    def on_draw(self):
        self.clear()
        if self.state == STATE_MENU:
            self._draw_menu()
            return

        self.set_3d()
        self._draw_chunks()
        self._draw_target_outline()
        self._draw_held_item()

        self.set_2d()
        self._draw_hud()
        if self.state == STATE_PAUSED:
            self._draw_pause_menu()
        elif self.state in INVENTORY_STATES:
            self._draw_inventory_screen()

    def _draw_chunks(self):
        # ÖNEMLİ: pyglet'in metin (Label) ve şekil (shapes) çizimi shader
        # kullanıyor olabilir. Önceki karede HUD çizildikten sonra bir shader
        # program aktif kalmışsa, bizim eski-usul (glVertexPointer tabanlı)
        # chunk çizimimiz o shader'ın beklediği generic vertex attribute'ları
        # üzerinden YANLIŞ yorumlanabilir. Programı burada elle sıfırlıyoruz
        # (sabit-fonksiyon pipeline'a zorluyoruz).
        gl.glUseProgram(0)
        gl.glColor3f(1, 1, 1)
        self.batch.draw()

    def _draw_target_outline(self):
        hit = self._cached_raycast
        if hit is None:
            return
        bx, by, bz = hit[0]
        gl.glColor3f(0, 0, 0)
        gl.glLineWidth(2.0)
        x0, y0, z0 = bx, by, bz
        x1, y1, z1 = bx + 1, by + 1, bz + 1
        edges = [
            (x0, y0, z0, x1, y0, z0), (x1, y0, z0, x1, y0, z1), (x1, y0, z1, x0, y0, z1), (x0, y0, z1, x0, y0, z0),
            (x0, y1, z0, x1, y1, z0), (x1, y1, z0, x1, y1, z1), (x1, y1, z1, x0, y1, z1), (x0, y1, z1, x0, y1, z0),
            (x0, y0, z0, x0, y1, z0), (x1, y0, z0, x1, y1, z0), (x1, y0, z1, x1, y1, z1), (x0, y0, z1, x0, y1, z1),
        ]
        gl.glBegin(gl.GL_LINES)
        for ax, ay, az, bx2, by2, bz2 in edges:
            gl.glVertex3f(ax, ay, az)
            gl.glVertex3f(bx2, by2, bz2)
        gl.glEnd()
        gl.glColor3f(1, 1, 1)

    def _draw_held_item(self):
        """Ekranın sağ altında, kameraya göre SABİT konumda elde tutulan item'ı
        çizer (klasik FPS 'viewmodel' tekniği): derinlik tamponunu temizleyip
        modelview'i kimliğe sıfırlıyoruz, böylece dünyanın arkasında kalmaz ve
        oyuncunun bakış açısından etkilenmez."""
        if self.player is None or self.inventory is None:
            return
        selected = self.inventory.selected_block()
        if selected is None:
            return
        item = I.ITEMS.get(selected)
        if item is None:
            return

        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glPushMatrix()
        gl.glLoadIdentity()
        gl.glTranslatef(0.62, -0.5, -1.1)
        gl.glRotatef(-20, 0, 1, 0)
        gl.glRotatef(15, 1, 0, 0)

        if item.tool_kind:
            gl.glRotatef(35, 0, 0, 1)
            self._draw_tool_model(item)
        else:
            gl.glScalef(0.5, 0.5, 0.5)
            self._draw_block_model(selected)

        gl.glPopMatrix()

    def _draw_block_model(self, block_id):
        """Elde tutulan blok için gerçek dokulu küp çizer (chunk render'ıyla aynı texture'lar)."""
        block_def = B.BLOCKS[block_id]
        faces = [
            ("top", block_def.top, [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)]),
            ("front", block_def.side, [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]),
            ("right", block_def.side, [(1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1)]),
            ("left", block_def.side, [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)]),
            ("back", block_def.side, [(1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0)]),
            ("bottom", block_def.bottom, [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
        ]
        uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glColor3f(1, 1, 1)
        for _face, tex_name, offsets in faces:
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.textures[tex_name].id)
            gl.glBegin(gl.GL_QUADS)
            for (ox, oy, oz), (u, v) in zip(offsets, uv):
                gl.glTexCoord2f(u, v)
                gl.glVertex3f(ox - 0.5, oy - 0.5, oz - 0.5)
            gl.glEnd()
        gl.glDisable(gl.GL_TEXTURE_2D)

    def _draw_tool_model(self, item):
        """Elde tutulan alet için basit (texture'sız, düz renkli) 3D siluet:
        ince bir sap + tier rengine boyalı bir kafa/ağız parçası."""
        gl.glDisable(gl.GL_TEXTURE_2D)
        handle_color = (0.47, 0.33, 0.20)
        head_color = tuple(c / 255 for c in TOOL_TIER_COLOR[item.tool_tier])

        def box(cx, cy, cz, sx, sy, sz, color):
            gl.glColor3f(*color)
            x0, x1 = cx - sx / 2, cx + sx / 2
            y0, y1 = cy - sy / 2, cy + sy / 2
            z0, z1 = cz - sz / 2, cz + sz / 2
            faces = [
                [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
                [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
                [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
                [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            ]
            gl.glBegin(gl.GL_QUADS)
            for face in faces:
                for vx, vy, vz in face:
                    gl.glVertex3f(vx, vy, vz)
            gl.glEnd()

        box(0, -0.15, 0, 0.08, 0.5, 0.08, handle_color)  # sap
        if item.tool_kind == I.SWORD:
            box(0, 0.25, 0, 0.10, 0.35, 0.05, head_color)   # kılıç bıçağı
            box(0, 0.08, 0, 0.22, 0.06, 0.06, handle_color)  # kabza
        elif item.tool_kind == I.AXE:
            box(0.10, 0.18, 0, 0.22, 0.16, 0.06, head_color)  # balta ağzı
        else:  # pickaxe
            box(0, 0.22, 0, 0.32, 0.08, 0.06, head_color)   # kazma başı (yatay)
        gl.glColor3f(1, 1, 1)

    def _draw_hud(self):
        width, height = self.get_size()
        # crosshair (immediate mode - zaten ucuz, önbelleğe gerek yok)
        gl.glColor3f(1, 1, 1)
        cx, cy = width // 2, height // 2
        gl.glBegin(gl.GL_LINES)
        gl.glVertex2f(cx - 8, cy)
        gl.glVertex2f(cx + 8, cy)
        gl.glVertex2f(cx, cy - 8)
        gl.glVertex2f(cx, cy + 8)
        gl.glEnd()

        # kazma ilerleme çubuğu (crosshair'in hemen altında)
        if self.breaking is not None:
            prog = min(1.0, self.breaking["progress"])
            bw = 60
            self._rect("mine_bg", cx - bw // 2, cy - 26, bw, 6, (40, 40, 40)).draw()
            self._rect("mine_fg", cx - bw // 2, cy - 26, max(1, int(bw * prog)), 6, (255, 210, 60)).draw()

        slot_size = 46
        total_w = slot_size * HOTBAR_SIZE
        start_x = width // 2 - total_w // 2
        bar_bottom = 14

        # can (kirmizi noktalar) ve aclik (turuncu noktalar) - hotbar'in hemen ustunde
        p = self.player
        dots_y = bar_bottom + slot_size + 14
        self._draw_point_bar("health", width // 2 - 100, dots_y, p.health, MAX_HEALTH, (220, 40, 40))
        self._draw_point_bar("hunger", width // 2 + 12, dots_y, p.hunger, MAX_HUNGER, (230, 150, 40))

        # hotbar arka plan paneli
        self._rect("hotbar_panel", start_x - 6, bar_bottom - 6, total_w + 12, slot_size + 12,
                   (15, 15, 15), opacity=150).draw()

        for i in range(HOTBAR_SIZE):
            x = start_x + i * slot_size
            self._draw_slot(f"hb{i}", x, bar_bottom, slot_size - 4, self.inventory.hotbar[i],
                             highlight=(i == self.inventory.selected_hotbar), key_label=str(i + 1))

        if self.debug_overlay:
            self.fps_display.draw()
            info = (f"seed={self.seed_used}  mod={p.mode}  x={p.x:.1f} y={p.y:.1f} z={p.z:.1f}  "
                    f"yaw={p.yaw:.0f} pitch={p.pitch:.0f}  yuklu_chunk={len(self.loaded_chunks)}  "
                    f"gorus_mesafesi={self.render_distance}")
            self._label("dbg_info", info, font_size=11, x=10, y=height - 20,
                        color=(255, 255, 255, 255)).draw()
            self._label("dbg_hint",
                        "ESC: duraklat/menu  E: envanter  F3: debug  Sol tik: kir(basili tut)  Sag tik: koy  Tekerlek/1-9: sec",
                        font_size=11, x=10, y=height - 40, color=(255, 255, 0, 255)).draw()

    def _draw_point_bar(self, key_prefix, x, y, value, max_value, color, radius=7, gap=16):
        """'Nokta şeklinde' can/açlık barı: her nokta 2 birimi temsil eder (10 nokta)."""
        n = max_value // 2
        for i in range(n):
            point_value = (i + 1) * 2
            cx_dot = x + i * gap
            if value >= point_value:
                fill = color
            elif value >= point_value - 1:
                fill = tuple(c // 2 + 40 for c in color)  # yarım nokta
            else:
                fill = (60, 60, 60)
            self._circle(f"{key_prefix}{i}", cx_dot, y, radius, fill).draw()

    def _inventory_layout(self):
        """
        Envanter slotlarının ekran koordinatlarını hesaplar. Hem çizim hem de
        tıklama testi AYNI bu fonksiyonu kullanır, böylece ikisi asla birbirinden
        sapmaz. Döner: (hotbar_rects, main_rects, palette_rects, craft_rects, result_rect)
          hotbar_rects / main_rects: [(slot_index, x, y, size), ...]
          palette_rects:             [(block_id, x, y, size), ...]
          craft_rects:                [(row, col, x, y, size), ...] (2x2 ya da 3x3)
          result_rect:                (x, y, size)
        """
        width, height = self.get_size()
        size = 44
        gap = 6
        cx = width // 2

        hotbar_y = height // 2 - 170
        hotbar_w = HOTBAR_SIZE * (size + gap) - gap
        hx0 = cx - hotbar_w // 2
        hotbar_rects = [(i, hx0 + i * (size + gap), hotbar_y, size) for i in range(HOTBAR_SIZE)]

        main_w = MAIN_COLS * (size + gap) - gap
        mx0 = cx - main_w // 2
        main_y0 = hotbar_y + size + 30
        main_rects = []
        for row in range(MAIN_ROWS):
            for col in range(MAIN_COLS):
                idx = HOTBAR_SIZE + row * MAIN_COLS + col
                x = mx0 + col * (size + gap)
                y = main_y0 + row * (size + gap)
                main_rects.append((idx, x, y, size))

        palette_rects = []
        if self.player is not None and self.player.mode == "creative":
            palette_y = main_y0 + MAIN_ROWS * (size + gap) + 30
            palette_w = len(B.PLACEABLE) * (size + gap) - gap
            px0 = cx - palette_w // 2
            for i, block_id in enumerate(B.PLACEABLE):
                palette_rects.append((block_id, px0 + i * (size + gap), palette_y, size))

        # crafting grid: ekranın sağ üstünde, 2x2 (kişisel) ya da 3x3 (masa)
        grid_n = 3 if self.state == STATE_CRAFTING_TABLE else 2
        craft_size = 42
        craft_gap = 6
        grid_w = grid_n * (craft_size + craft_gap) - craft_gap
        gx0 = width - grid_w - 130
        gy0 = height - 90
        craft_rects = []
        for row in range(grid_n):
            for col in range(grid_n):
                x = gx0 + col * (craft_size + craft_gap)
                y = gy0 - row * (craft_size + craft_gap)
                craft_rects.append((row, col, x, y, craft_size))
        result_x = gx0 + grid_w + 40
        result_y = gy0 - (grid_n - 1) * (craft_size + craft_gap) // 2
        result_rect = (result_x, result_y, craft_size)

        return hotbar_rects, main_rects, palette_rects, craft_rects, result_rect

    def _draw_slot(self, key, x, y, size, stack, highlight=False, key_label=None):
        border = (255, 220, 40) if highlight else (95, 95, 95)
        self._brect(f"{key}_bg", x, y, size, size, 2, (58, 58, 58), border).draw()
        if stack is not None:
            item_id, count = stack
            item = I.ITEMS.get(item_id)
            pad = 6
            if item is not None and item.tool_kind:
                icon_tex = self.tool_icons.get((item.tool_kind, item.tool_tier))
                if icon_tex is not None:
                    gl.glEnable(gl.GL_TEXTURE_2D)
                    gl.glColor3f(1, 1, 1)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, icon_tex.id)
                    gl.glBegin(gl.GL_QUADS)
                    gl.glTexCoord2f(0, 1); gl.glVertex2f(x + pad, y + pad)
                    gl.glTexCoord2f(1, 1); gl.glVertex2f(x + size - pad, y + pad)
                    gl.glTexCoord2f(1, 0); gl.glVertex2f(x + size - pad, y + size - pad)
                    gl.glTexCoord2f(0, 0); gl.glVertex2f(x + pad, y + size - pad)
                    gl.glEnd()
                    gl.glDisable(gl.GL_TEXTURE_2D)
            else:
                icon_color = item_icon_color(self, item_id)
                self._rect(f"{key}_icon", x + pad, y + pad, size - pad * 2, size - pad * 2, icon_color).draw()
            label_text = I.short_label(item_id)
            self._label(f"{key}_name", label_text, font_size=8, x=x + size // 2, y=y + size - 9,
                        anchor_x="center", anchor_y="center", color=(255, 255, 255, 255)).draw()
            if self.player is not None and self.player.mode == "creative" and I.stack_max(item_id) > 1:
                count_text = "*"
            else:
                count_text = str(count)
            self._label(f"{key}_count", count_text, font_size=10, x=x + size - 6, y=y + 6,
                        anchor_x="right", anchor_y="bottom", bold=True,
                        color=(255, 255, 255, 255)).draw()
        if key_label is not None:
            self._label(f"{key}_keylabel", key_label, font_size=8, x=x + 3, y=y + size - 2,
                        anchor_x="left", anchor_y="top", color=(210, 210, 210, 255)).draw()

    def _draw_inventory_screen(self):
        width, height = self.get_size()
        self._rect("inv_overlay", 0, 0, width, height, (0, 0, 0), opacity=170).draw()

        hotbar_rects, main_rects, palette_rects, craft_rects, result_rect = self._inventory_layout()

        title = "Crafting Masasi (3x3)" if self.state == STATE_CRAFTING_TABLE else "Envanter (2x2 crafting)"
        self._label("inv_title",
                    f"{title}  -  [E]/[ESC] kapat  |  sol tik: al/birak/birlestir/takas  |  sag tik: yarisini al / tek tek birak",
                    font_size=13, x=width // 2, y=height - 40,
                    anchor_x="center", color=(255, 255, 255, 255)).draw()

        for index, x, y, size in main_rects:
            self._draw_slot(f"inv_m{index}", x, y, size,
                             self.inventory.hotbar[index] if index < HOTBAR_SIZE else
                             self.inventory.main[index - HOTBAR_SIZE])
        for index, x, y, size in hotbar_rects:
            self._draw_slot(f"inv_h{index}", x, y, size, self.inventory.hotbar[index],
                             highlight=(index == self.inventory.selected_hotbar))

        if self.player.mode == "creative":
            self._label("inv_palette_hint", "Sinirsiz blok paleti (tikla -> ele al)", font_size=12,
                        x=width // 2, y=palette_rects[0][2] + 34,
                        anchor_x="center", color=(220, 220, 220, 255)).draw()
            for block_id, x, y, size in palette_rects:
                self._draw_slot(f"inv_p{block_id}", x, y, size, [block_id, CREATIVE_STACK])

        self._draw_crafting_panel(craft_rects, result_rect)

        # elde tutulan (cursor) stack, fare imlecini takip eder
        if self.inventory.cursor is not None:
            mx, my = self._mouse_pos
            self._draw_slot("cursor", mx - 22, my - 22, 44, self.inventory.cursor)

    def _draw_crafting_panel(self, craft_rects, result_rect):
        if not craft_rects:
            return
        first_x = min(x for _, _, x, y, s in craft_rects)
        top_y = max(y for _, _, x, y, s in craft_rects)
        self._label("craft_title", "Crafting", font_size=15, x=first_x, y=top_y + 60,
                    anchor_x="left", color=(255, 255, 255, 255), bold=True).draw()

        for row, col, x, y, size in craft_rects:
            self._draw_slot(f"craft_{row}_{col}", x, y, size, self.craft_grid[row][col])

        recipe = C.match(self.craft_grid)
        rx, ry, rsize = result_rect
        self._rect("craft_arrow", rx - 20, ry + rsize // 2 - 1, 34, 2, (200, 200, 200)).draw()
        can_take = recipe is not None and (
            self.inventory.cursor is None or
            (self.inventory.cursor[0] == recipe.output_id and
             self.inventory.cursor[1] + recipe.output_count <= I.stack_max(recipe.output_id)))
        border = (120, 220, 120) if can_take else (95, 95, 95)
        self._brect("craft_result_bg", rx, ry, rsize, rsize, 3, (58, 58, 58), border).draw()
        if recipe is not None:
            self._draw_slot("craft_result", rx, ry, rsize, [recipe.output_id, recipe.output_count])
        if not any(cell for row in self.craft_grid for cell in row):
            self._label("craft_hint", "Malzemeleri sol grid'e\nsurukleyip yerlestir", font_size=9,
                        x=first_x, y=top_y - (3 * 48) - 10,
                        anchor_x="left", multiline=True, width=200,
                        color=(200, 200, 200, 255)).draw()

    def _pause_layout(self):
        width, height = self.get_size()
        y = height // 2 + 120 - 28 * 7 - 12  # son metin satırının biraz altı
        cx = width // 2
        return {
            "resume": (cx - 110, y - 12, 100, 30),
            "quit": (cx + 10, y - 12, 100, 30),
        }

    def _draw_pause_menu(self):
        width, height = self.get_size()
        self._rect("pause_overlay", 0, 0, width, height, (0, 0, 0), opacity=160).draw()
        p = self.player
        lines = [
            "-- DURAKLATILDI --",
            f"Dunya: {self.world_name}   Seed: {self.seed_used}",
            f"Oyun modu: {p.mode}   [G] ile degistir",
            f"Konum: x={p.x:.1f} y={p.y:.1f} z={p.z:.1f}",
            f"Can: {p.health:.0f}/{MAX_HEALTH}   Aclik: {p.hunger:.0f}/{MAX_HUNGER}",
            f"Gorus mesafesi: {self.render_distance} chunk   [+/-] ile degistir",
            f"Fare hassasiyeti: {self.mouse_sensitivity:.2f}",
        ]
        y = height // 2 + 120
        for i, line in enumerate(lines):
            self._label(f"pause_line{i}", line, font_size=16, x=width // 2, y=y,
                        anchor_x="center", color=(255, 255, 255, 255)).draw()
            y -= 28

        rects = self._pause_layout()
        rx, ry, rw, rh = rects["resume"]
        self._brect("pause_resume", rx, ry, rw, rh, 2, (60, 120, 60), (255, 255, 255)).draw()
        self._label("pause_resume_lbl", "Devam et", font_size=12, x=rx + rw // 2, y=ry + rh // 2,
                    anchor_x="center", anchor_y="center", color=(255, 255, 255, 255)).draw()
        qx, qy, qw, qh = rects["quit"]
        self._brect("pause_quit", qx, qy, qw, qh, 2, (120, 60, 60), (255, 255, 255)).draw()
        self._label("pause_quit_lbl", "Ana menu", font_size=12, x=qx + qw // 2, y=qy + qh // 2,
                    anchor_x="center", anchor_y="center", color=(255, 255, 255, 255)).draw()

    def _menu_layout(self):
        width, height = self.get_size()
        cx, cy = width // 2, height // 2
        panel_w, panel_h = 480, 300
        y = cy + panel_h // 2 - 10
        y -= 60
        mode_rects = {
            "survival": (cx - 40, y - 26, 130, 30),
            "creative": (cx - 40 + 150, y - 26, 130, 30),
        }
        y -= 60
        rd_rects = {
            "rd_minus": (cx + 195, y - 24, 26, 26),
            "rd_plus": (cx + 225, y - 24, 26, 26),
        }
        y -= 70
        start_rect = (cx - 100, y - 34, 200, 40)
        return panel_w, panel_h, mode_rects, rd_rects, start_rect

    def _draw_menu(self):
        self.set_2d()
        width, height = self.get_size()
        cx, cy = width // 2, height // 2

        # gökyüzü zaten temizlenmiş arka plan; üstüne dekoratif bir zemin şeridi çiz
        self._rect("menu_ground", 0, 0, width, height // 3, (70, 130, 60)).draw()

        self._label("menu_title", "PyCraft", font_size=52, x=cx, y=height - 90,
                    anchor_x="center", anchor_y="center", bold=True, color=(255, 255, 255, 255)).draw()
        self._label("menu_subtitle", "Python + OpenGL", font_size=13, x=cx, y=height - 130,
                    anchor_x="center", anchor_y="center", color=(230, 230, 230, 255)).draw()

        panel_w, panel_h, mode_rects, rd_rects, start_rect = self._menu_layout()
        self._brect("menu_panel", cx - panel_w // 2, cy - panel_h // 2 + 20, panel_w, panel_h,
                    3, (30, 30, 30), (255, 255, 255)).draw()

        seed_show = self.menu_seed_text if self.menu_seed_text else "(rastgele)"
        y = cy + panel_h // 2 - 10
        self._label("menu_seed_lbl", "Seed:", font_size=13, x=cx - panel_w // 2 + 24, y=y,
                    anchor_x="left", color=(200, 200, 200, 255)).draw()
        self._brect("menu_seed_box", cx - 60, y - 32, 220, 30, 2, (50, 50, 50), (150, 150, 150)).draw()
        self._label("menu_seed_val", seed_show, font_size=13, x=cx - 50, y=y - 17,
                    anchor_x="left", anchor_y="center", color=(255, 255, 0, 255)).draw()
        self._label("menu_seed_hint", "(rakam yaz, Backspace ile sil)", font_size=10,
                    x=cx + 170, y=y - 17, anchor_x="left", anchor_y="center",
                    color=(180, 180, 180, 255)).draw()

        y -= 60
        self._label("menu_mode_lbl", "Oyun modu:", font_size=13, x=cx - panel_w // 2 + 24, y=y,
                    anchor_x="left", color=(200, 200, 200, 255)).draw()
        for mode_id, label in [("survival", "Survival"), ("creative", "Creative")]:
            bx, by, bw, bh = mode_rects[mode_id]
            active = self.menu_mode == mode_id
            self._brect(f"menu_mode_{mode_id}", bx, by, bw, bh, 2,
                        (60, 110, 60) if active else (50, 50, 50),
                        (255, 255, 0) if active else (120, 120, 120)).draw()
            self._label(f"menu_mode_{mode_id}_lbl", label, font_size=12, x=bx + bw // 2, y=by + bh // 2,
                        anchor_x="center", anchor_y="center", color=(255, 255, 255, 255)).draw()

        y -= 60
        self._label("menu_rd_lbl", f"Gorus mesafesi:  {self.menu_render_distance} chunk",
                    font_size=13, x=cx - panel_w // 2 + 24, y=y,
                    anchor_x="left", color=(200, 200, 200, 255)).draw()
        mx, my, mw, mh = rd_rects["rd_minus"]
        self._brect("menu_rd_minus", mx, my, mw, mh, 2, (60, 60, 60), (150, 150, 150)).draw()
        self._label("menu_rd_minus_lbl", "-", font_size=16, x=mx + mw // 2, y=my + mh // 2,
                    anchor_x="center", anchor_y="center", bold=True, color=(255, 255, 255, 255)).draw()
        px, py, pw, ph = rd_rects["rd_plus"]
        self._brect("menu_rd_plus", px, py, pw, ph, 2, (60, 60, 60), (150, 150, 150)).draw()
        self._label("menu_rd_plus_lbl", "+", font_size=16, x=px + pw // 2, y=py + ph // 2,
                    anchor_x="center", anchor_y="center", bold=True, color=(255, 255, 255, 255)).draw()

        sx, sy, sw, sh = start_rect
        self._brect("menu_start", sx, sy, sw, sh, 3, (60, 140, 60), (255, 255, 255)).draw()
        self._label("menu_start_lbl", "BASLAT (ENTER)", font_size=15, x=sx + sw // 2, y=sy + sh // 2,
                    anchor_x="center", anchor_y="center", bold=True, color=(255, 255, 255, 255)).draw()


def main():
    game = Game()
    pyglet.app.run()


if __name__ == "__main__":
    main()
