"""
Python + Pyglet/OpenGL Minecraft klonu - v1 (temel sürüm)

Bu sürümde var olanlar:
  - Seed'li noise ile prosedürel dünya (dağlar, ovalar, sahiller, su)
  - Chunk (16x16) tabanlı dünya, ağaçlar
  - Her blok yüzü için ayrı 16x16 piksel-art texture dosyası (paylaşılan atlas yok)
  - Birinci şahıs kamera, yürüme/koşma/zıplama (survival) ya da uçma (creative)
  - Blok kırma / koyma
  - Basit hotbar + envanter (survival'da blok toplama/harcama, creative'de sınırsız)
  - Başlangıç menüsü: seed girme, oyun modu seçimi, görüş mesafesi
  - Oyun içi duraklatma menüsü: dünya/oyuncu bilgisi ve ayarlar

Henüz YOK (bir sonraki adımlarda eklenecek): crafting sistemi, combat/canlı
düşmanlar, tam ızgara envanter arayüzü, chunk unload/kaydetme.

Çalıştırmak için (kendi bilgisayarında):
    pip install -r requirements.txt
    python textures.py     # (main.py zaten otomatik çağırıyor, elle gerekmez)
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
from world import World, CHUNK_SIZE, SEA_LEVEL
from mesh import build_chunk_mesh
from player import Player
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


# ---------------------------------------------------------------- yardımcılar

def make_hotbar_slot_rect(x, y, size=48):
    return pyglet.shapes.Rectangle(x, y, size, size, color=(40, 40, 40))


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
        self.textures = {}  # texture ismi -> pyglet Texture
        for name in TEX.TEXTURE_NAMES:
            img = pyglet.image.load(f"assets/{name}.png").get_texture()
            gl.glBindTexture(gl.GL_TEXTURE_2D, img.id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
            self.textures[name] = img

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
        self._build_menu_labels()

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

        pyglet.clock.schedule_interval(self.update, TICK_RATE)

    # ------------------------------------------------------------ menü UI

    def _build_menu_labels(self):
        cx, cy = WINDOW_W // 2, WINDOW_H // 2
        self.menu_title = pyglet.text.Label(
            "PyCraft", font_size=48, x=cx, y=cy + 180,
            anchor_x="center", anchor_y="center", bold=True)
        self.menu_lines = [
            "Seed yazip ENTER'a basarak baslayin (bos birakirsaniz rastgele seed)",
            "[C] Creative  /  [S] Survival  -  Simdiki mod: {mode}",
            "[UP]/[DOWN] Gorus mesafesi (chunk): {rd}",
            "Seed: {seed}",
            "",
            "ENTER: Dunyayi baslat",
        ]

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
                # Bilerek Batch.add() KULLANMIYORUZ: chunk'lar sürekli
                # add()/delete() ile paylaşılan bir static buffer'a girip çıkınca
                # pyglet'in buffer ayırıcısında bozulma (çapraz/kaymış geometri)
                # oluşabiliyor. Her chunk+texture kombinasyonu kendi bağımsız
                # vertex buffer'ına sahip olsun diye pyglet.graphics.vertex_list()
                # doğrudan kullanılıyor.
                chunk.vertex_list[tex_name] = pyglet.graphics.vertex_list(
                    count,
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
                self.set_exclusive_mouse(False)
            elif self.state == STATE_PAUSED:
                self.state = STATE_PLAYING
                self.set_exclusive_mouse(True)
            elif self.state == STATE_INVENTORY:
                self._close_inventory()
            return

        if symbol == key.E:
            if self.state == STATE_PLAYING:
                self.state = STATE_INVENTORY
                self.set_exclusive_mouse(False)
            elif self.state == STATE_INVENTORY:
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
        """Envanter ekranını kapatır; elde tutulan (cursor) stack varsa envantere geri dağıtır."""
        self.inventory.drop_cursor_into_inventory()
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
        if self.state == STATE_INVENTORY:
            if button == mouse.LEFT:
                self._handle_inventory_click(x, y)
            return
        if self.state != STATE_PLAYING:
            return
        hit = self.player.raycast(self.world, max_distance=6.0)
        if hit is None:
            return
        block_pos, place_pos = hit

        if button == mouse.LEFT:
            self._break_block(block_pos)
        elif button == mouse.RIGHT:
            self._place_block(place_pos)

    def _handle_inventory_click(self, mx, my):
        hotbar_rects, main_rects, palette_rects = self._inventory_layout()
        for index, rx, ry, size in hotbar_rects + main_rects:
            if rx <= mx <= rx + size and ry <= my <= ry + size:
                self.inventory.click_slot(index)
                return
        if self.player.mode == "creative":
            for block_id, rx, ry, size in palette_rects:
                if rx <= mx <= rx + size and ry <= my <= ry + size:
                    # Palet sınırsızdır: tıklanınca eldeki (cursor) her neyse
                    # üzerine yeni, dolu bir yığın alınır.
                    self.inventory.cursor = [block_id, CREATIVE_STACK]
                    return

    def _break_block(self, pos):
        bx, by, bz = pos
        block_id = self.world.get_block(bx, by, bz)
        block_def = B.BLOCKS[block_id]
        if not block_def.breakable:
            return
        self.world.set_block(bx, by, bz, B.AIR)
        if self.player.mode == "survival":
            self.inventory.add_item(block_id, 1)

    def _place_block(self, pos):
        bx, by, bz = pos
        selected = self.inventory.selected_block()
        if selected is None:
            return
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

        self.set_2d()
        self._draw_hud()
        if self.state == STATE_PAUSED:
            self._draw_pause_menu()
        elif self.state == STATE_INVENTORY:
            self._draw_inventory_screen()

    def _draw_chunks(self):
        # ÖNEMLİ: pyglet'in metin (Label) ve şekil (shapes) çizimi shader
        # kullanıyor olabilir. Önceki karede HUD çizildikten sonra bir shader
        # program aktif kalmışsa, bizim eski-usul (glVertexPointer tabanlı)
        # chunk çizimimiz o shader'ın beklediği generic vertex attribute'ları
        # üzerinden YANLIŞ yorumlanabilir - gördüğün çapraz/kırpılmış geometri
        # tam olarak bu tarz bir "kalıntı state" belirtisidir. Programı burada
        # elle sıfırlıyoruz (sabit-fonksiyon pipeline'a zorluyoruz).
        gl.glUseProgram(0)
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glColor3f(1, 1, 1)
        for coord in self.loaded_chunks:
            chunk = self.world.chunks.get(coord)
            if chunk is None or not chunk.vertex_list:
                continue
            for tex_name, vl in chunk.vertex_list.items():
                gl.glBindTexture(gl.GL_TEXTURE_2D, self.textures[tex_name].id)
                vl.draw(gl.GL_QUADS)
        gl.glDisable(gl.GL_TEXTURE_2D)

    def _draw_target_outline(self):
        hit = self.player.raycast(self.world, max_distance=6.0)
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

    def _draw_hud(self):
        width, height = self.get_size()
        # crosshair
        gl.glColor3f(1, 1, 1)
        cx, cy = width // 2, height // 2
        gl.glBegin(gl.GL_LINES)
        gl.glVertex2f(cx - 8, cy)
        gl.glVertex2f(cx + 8, cy)
        gl.glVertex2f(cx, cy - 8)
        gl.glVertex2f(cx, cy + 8)
        gl.glEnd()

        # hotbar
        slot_size = 44
        total_w = slot_size * HOTBAR_SIZE
        start_x = width // 2 - total_w // 2
        for i in range(HOTBAR_SIZE):
            x = start_x + i * slot_size
            border = (255, 255, 0) if i == self.inventory.selected_hotbar else (30, 30, 30)
            bg = pyglet.shapes.BorderedRectangle(
                x, 10, slot_size - 4, slot_size - 4, border=3,
                color=(70, 70, 70), border_color=border)
            bg.draw()
            stack = self.inventory.hotbar[i]
            if stack is not None:
                name = B.BLOCKS[stack[0]].name
                count = "*" if self.player.mode == "creative" else str(stack[1])
                pyglet.text.Label(f"{name[:4]}\n{count}", font_size=8, x=x + slot_size // 2, y=10 + slot_size // 2,
                                   anchor_x="center", anchor_y="center", multiline=True, width=slot_size,
                                   align="center", color=(255, 255, 255, 255)).draw()

        if self.debug_overlay:
            self.fps_display.draw()
            p = self.player
            info = (f"seed={self.seed_used}  mod={p.mode}  x={p.x:.1f} y={p.y:.1f} z={p.z:.1f}  "
                    f"yaw={p.yaw:.0f} pitch={p.pitch:.0f}  yuklu_chunk={len(self.loaded_chunks)}  "
                    f"gorus_mesafesi={self.render_distance}")
            pyglet.text.Label(info, font_size=11, x=10, y=height - 20,
                               color=(255, 255, 255, 255)).draw()
            pyglet.text.Label("ESC: duraklat/menu  E: envanter  F3: debug  Sol tik: kir  Sag tik: koy  Tekerlek/1-9: blok sec",
                               font_size=11, x=10, y=height - 40, color=(255, 255, 0, 255)).draw()

    def _inventory_layout(self):
        """
        Envanter slotlarının ekran koordinatlarını hesaplar. Hem çizim hem de
        tıklama testi AYNI bu fonksiyonu kullanır, böylece ikisi asla birbirinden
        sapmaz. Döner: (hotbar_rects, main_rects, palette_rects)
          hotbar_rects / main_rects: [(slot_index, x, y, size), ...]
          palette_rects:             [(block_id, x, y, size), ...]
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

        return hotbar_rects, main_rects, palette_rects

    def _draw_slot(self, x, y, size, stack, highlight=False):
        border = (255, 255, 0) if highlight else (90, 90, 90)
        pyglet.shapes.BorderedRectangle(x, y, size, size, border=2,
                                         color=(60, 60, 60), border_color=border).draw()
        if stack is not None:
            name = B.BLOCKS[stack[0]].name
            count = "*" if (self.player.mode == "creative") else str(stack[1])
            pyglet.text.Label(f"{name[:5]}\n{count}", font_size=8, x=x + size // 2, y=y + size // 2,
                               anchor_x="center", anchor_y="center", multiline=True, width=size,
                               align="center", color=(255, 255, 255, 255)).draw()

    def _draw_inventory_screen(self):
        width, height = self.get_size()
        overlay = pyglet.shapes.Rectangle(0, 0, width, height, color=(0, 0, 0))
        overlay.opacity = 170
        overlay.draw()

        hotbar_rects, main_rects, palette_rects = self._inventory_layout()

        pyglet.text.Label("Envanter  -  [E]/[ESC] kapat, sol tik: al / birak / birlestir / takas et",
                           font_size=14, x=width // 2, y=height - 40,
                           anchor_x="center", color=(255, 255, 255, 255)).draw()

        for index, x, y, size in main_rects:
            self._draw_slot(x, y, size, self.inventory.hotbar[index] if index < HOTBAR_SIZE else
                             self.inventory.main[index - HOTBAR_SIZE])
        for index, x, y, size in hotbar_rects:
            self._draw_slot(x, y, size, self.inventory.hotbar[index],
                             highlight=(index == self.inventory.selected_hotbar))

        if self.player.mode == "creative":
            pyglet.text.Label("Sinirsiz blok paleti (tikla -> ele al)", font_size=12,
                               x=width // 2, y=palette_rects[0][2] + 34,
                               anchor_x="center", color=(220, 220, 220, 255)).draw()
            for block_id, x, y, size in palette_rects:
                self._draw_slot(x, y, size, [block_id, CREATIVE_STACK])

        # elde tutulan (cursor) stack, fare imlecini takip eder
        if self.inventory.cursor is not None:
            mx, my = self._mouse_pos
            self._draw_slot(mx - 22, my - 22, 44, self.inventory.cursor)

    def _draw_pause_menu(self):
        width, height = self.get_size()
        overlay = pyglet.shapes.Rectangle(0, 0, width, height, color=(0, 0, 0))
        overlay.opacity = 160
        overlay.draw()
        p = self.player
        lines = [
            "-- DURAKLATILDI --",
            f"Dunya: {self.world_name}   Seed: {self.seed_used}",
            f"Oyun modu: {p.mode}   [G] ile degistir",
            f"Konum: x={p.x:.1f} y={p.y:.1f} z={p.z:.1f}",
            f"Gorus mesafesi: {self.render_distance} chunk   [+/-] ile degistir",
            f"Fare hassasiyeti: {self.mouse_sensitivity:.2f}",
            "",
            "[ESC] Devam et    [Q] Ana menuye don",
        ]
        y = height // 2 + 120
        for line in lines:
            pyglet.text.Label(line, font_size=16, x=width // 2, y=y,
                               anchor_x="center", color=(255, 255, 255, 255)).draw()
            y -= 28

    def _draw_menu(self):
        self.set_2d()
        self.menu_title.draw()
        width, height = self.get_size()
        seed_show = self.menu_seed_text if self.menu_seed_text else "(rastgele)"
        text_vals = {"mode": self.menu_mode, "rd": self.menu_render_distance, "seed": seed_show}
        y = height // 2 + 60
        for template in self.menu_lines:
            line = template.format(**text_vals)
            pyglet.text.Label(line, font_size=15, x=width // 2, y=y,
                               anchor_x="center", color=(255, 255, 255, 255)).draw()
            y -= 30


def main():
    game = Game()
    pyglet.app.run()


if __name__ == "__main__":
    main()
