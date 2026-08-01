"""
Birinci şahıs oyuncu kontrolcüsü: hareket, basit AABB-voxel çarpışması,
survival'da yerçekimi/zıplama, creative'de serbest uçuş, ve blok
kırma/koyma için görüş ışını (raycast).

pyglet'e bağımlı değildir: main.py her frame'de pyglet tuş durumlarını
basit bir dict'e ({"forward": True, ...}) çevirip buraya verir. Böylece
bu dosya pyglet kurulu olmadan da (bu sandbox dahil) test edilebilir.
"""
import math
from world import World

GRAVITY = -20.0
JUMP_SPEED = 8.0
WALK_SPEED = 5.0
FLY_SPEED = 10.0
PLAYER_WIDTH = 0.6   # yatayda oyuncu genişliği (çarpışma kutusu)
PLAYER_HEIGHT = 1.8
EYE_HEIGHT = 1.62
TERMINAL_VELOCITY = -40.0


class Player:
    def __init__(self, world: World, x=0.0, z=0.0, mode="survival"):
        y = world.spawn_height(int(x), int(z))
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.yaw = 0.0     # yatay bakış açısı (derece)
        self.pitch = 0.0   # dikey bakış açısı (derece), -89..89 arası kelepçelenir
        self.vy = 0.0
        self.on_ground = False
        self.mode = mode           # "survival" ya da "creative"
        self.flying = (mode == "creative")

    # ---------- bakış ----------

    def add_look(self, dx, dy, sensitivity=0.15):
        self.yaw = (self.yaw + dx * sensitivity) % 360
        self.pitch = max(-89.0, min(89.0, self.pitch + dy * sensitivity))

    def sight_vector(self):
        yaw_r = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        x = math.cos(pitch_r) * math.sin(yaw_r)
        y = math.sin(pitch_r)
        z = -math.cos(pitch_r) * math.cos(yaw_r)
        return x, y, z

    def eye_position(self):
        return self.x, self.y + EYE_HEIGHT, self.z

    # ---------- hareket ----------

    def set_mode(self, mode):
        self.mode = mode
        self.flying = (mode == "creative")
        if self.flying:
            self.vy = 0.0

    def update(self, dt, action_state, world: World):
        """
        action_state: {"forward","back","left","right","jump","sneak_down","sprint"} -> bool
        """
        yaw_r = math.radians(self.yaw)
        forward_x, forward_z = math.sin(yaw_r), -math.cos(yaw_r)
        right_x, right_z = math.cos(yaw_r), math.sin(yaw_r)

        mx = mz = 0.0
        if action_state.get("forward"):
            mx += forward_x; mz += forward_z
        if action_state.get("back"):
            mx -= forward_x; mz -= forward_z
        if action_state.get("right"):
            mx += right_x; mz += right_z
        if action_state.get("left"):
            mx -= right_x; mz -= right_z

        length = math.hypot(mx, mz)
        if length > 1e-6:
            mx, mz = mx / length, mz / length

        speed = FLY_SPEED if self.flying else WALK_SPEED
        if action_state.get("sprint"):
            speed *= 1.6

        dx = mx * speed * dt
        dz = mz * speed * dt

        if self.flying:
            dy = 0.0
            if action_state.get("jump"):
                dy += FLY_SPEED * dt
            if action_state.get("sneak_down"):
                dy -= FLY_SPEED * dt
            self.vy = 0.0
        else:
            self.vy = max(TERMINAL_VELOCITY, self.vy + GRAVITY * dt)
            if action_state.get("jump") and self.on_ground:
                self.vy = JUMP_SPEED
            dy = self.vy * dt

        self._move_with_collision(dx, dy, dz, world)

    def _aabb_blocked(self, world, x, y, z):
        """Verilen konumda oyuncunun AABB'si içinde katı blok var mı?"""
        half = PLAYER_WIDTH / 2
        x_coords = (x - half, x + half)
        z_coords = (z - half, z + half)
        y_coords = (y, y + PLAYER_HEIGHT)
        for bx in x_coords:
            for bz in z_coords:
                for by in y_coords:
                    if world.is_solid(math.floor(bx), math.floor(by), math.floor(bz)):
                        return True
        return False

    def _move_with_collision(self, dx, dy, dz, world):
        # Eksen eksen hareket ettirip çarpışma varsa o ekseni iptal et
        # (basit ama etkili "sweep" yaklaşımı, voxel oyunlarında yaygın).
        if not self._aabb_blocked(world, self.x + dx, self.y, self.z):
            self.x += dx
        if not self._aabb_blocked(world, self.x, self.y + dy, self.z):
            self.y += dy
            self.on_ground = False
        else:
            if dy < 0:
                self.on_ground = True
            self.vy = 0.0
        if not self._aabb_blocked(world, self.x, self.y, self.z + dz):
            self.z += dz

    # ---------- blok kırma/koyma için raycast ----------

    def raycast(self, world: World, max_distance=6.0, step=0.05):
        """
        Bakış yönünde küçük adımlarla ilerleyip ilk katı bloğu bulur.
        Döner: (hit_block_pos, place_pos) ya da None.
        hit_block_pos  -> kırılacak/işaret edilen blok
        place_pos      -> yeni blok konulacaksa buraya konur (bir önceki boş hücre)
        """
        ox, oy, oz = self.eye_position()
        dx, dy, dz = self.sight_vector()

        prev = (math.floor(ox), math.floor(oy), math.floor(oz))
        dist = 0.0
        while dist <= max_distance:
            x, y, z = ox + dx * dist, oy + dy * dist, oz + dz * dist
            block_pos = (math.floor(x), math.floor(y), math.floor(z))
            if block_pos != prev:
                bx, by, bz = block_pos
                if world.is_solid(bx, by, bz):
                    return block_pos, prev
                prev = block_pos
            dist += step
        return None
