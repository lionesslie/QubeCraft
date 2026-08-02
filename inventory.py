"""
Yığın (stack) tabanlı envanter sistemi.

Bir "stack" ya None'dur (boş slot) ya da [block_id, count] şeklinde bir liste
(mutable, in-place güncellenebilsin diye tuple değil liste).

Bu dosya pyglet'e bağımlı değildir; main.py mouse tıklamalarını buradaki
yöntemlere (pick_up_or_place, vb.) çevirir. Böylece mantık pyglet kurulu
olmayan bir ortamda bile test edilebilir.
"""
import items as I

HOTBAR_SIZE = 9
MAIN_ROWS = 3
MAIN_COLS = 9
MAIN_SIZE = MAIN_ROWS * MAIN_COLS


class Inventory:
    def __init__(self):
        self.hotbar = [None] * HOTBAR_SIZE   # [block_id, count] ya da None
        self.main = [None] * MAIN_SIZE
        self.selected_hotbar = 0
        self.cursor = None  # fare ile "elde tutulan" stack

    # ---------- birleşik index yardımcıları (0..8 hotbar, 9..35 main) ----------

    def _get(self, index):
        if index < HOTBAR_SIZE:
            return self.hotbar[index]
        return self.main[index - HOTBAR_SIZE]

    def _set(self, index, stack):
        if index < HOTBAR_SIZE:
            self.hotbar[index] = stack
        else:
            self.main[index - HOTBAR_SIZE] = stack

    def total_slots(self):
        return HOTBAR_SIZE + MAIN_SIZE

    def get_slot(self, index):
        return self._get(index)

    def set_slot(self, index, stack):
        self._set(index, stack)

    # ---------- envantere item ekleme (blok kırınca çağrılır) ----------

    def add_item(self, block_id, count=1):
        """Önce var olan aynı-tip yığınlara, sonra boş slotlara ekler.
        Sığmayan miktarı döner (0 = hepsi sığdı)."""
        remaining = count
        n = self.total_slots()
        cap = I.stack_max(block_id)
        for i in range(n):
            if remaining <= 0:
                break
            stack = self._get(i)
            if stack is not None and stack[0] == block_id and stack[1] < cap:
                can_add = min(cap - stack[1], remaining)
                stack[1] += can_add
                remaining -= can_add
        for i in range(n):
            if remaining <= 0:
                break
            if self._get(i) is None:
                add_now = min(cap, remaining)
                self._set(i, [block_id, add_now])
                remaining -= add_now
        return remaining

    # ---------- hotbar'dan harcama (blok koyunca survival'da çağrılır) ----------

    def take_from_hotbar(self, index, count=1):
        stack = self.hotbar[index]
        if stack is None or stack[1] < count:
            return False
        stack[1] -= count
        if stack[1] <= 0:
            self.hotbar[index] = None
        return True

    def selected_block(self):
        stack = self.hotbar[self.selected_hotbar]
        return stack[0] if stack else None

    # ---------- fare ile slot etkileşimi (sol tık: al/koy/birleştir/takas) ----------

    def click_slot(self, index):
        """
        Klasik Minecraft tarzı 'cursor' etkileşimi:
          - Cursor boş, slot dolu  -> slotu cursor'a al
          - Cursor dolu, slot boş  -> cursor'u slota bırak
          - Cursor dolu, slot aynı tip -> mümkün olduğunca birleştir
          - Cursor dolu, slot farklı tip -> takas et
        """
        self.click_external(lambda: self._get(index), lambda v: self._set(index, v))

    def click_external(self, get_fn, set_fn):
        """click_slot ile aynı mantık ama envanterin KENDİ dizisi dışındaki
        bir slotla çalışır (örn. crafting grid hücreleri) - get_fn/set_fn
        üzerinden okunur/yazılır."""
        slot = get_fn()
        if self.cursor is None:
            if slot is not None:
                set_fn(None)
                self.cursor = slot
            return

        if slot is None:
            set_fn(self.cursor)
            self.cursor = None
        elif slot[0] == self.cursor[0]:
            cap = I.stack_max(slot[0])
            can_add = min(cap - slot[1], self.cursor[1])
            slot[1] += can_add
            self.cursor[1] -= can_add
            if self.cursor[1] <= 0:
                self.cursor = None
        else:
            set_fn(self.cursor)
            self.cursor = slot

    def right_click_slot(self, index):
        self.right_click_external(lambda: self._get(index), lambda v: self._set(index, v))

    def right_click_external(self, get_fn, set_fn):
        """
        Sağ tık: TEK adet taşır (crafting grid'ine aynı malzemeden birden
        fazla hücreye dağıtmak için gerekli - örn. kazmanın 3 ayrı tahta hücresi):
          - Cursor boş, slot dolu  -> slottaki yığının YARISINI (yukarı yuvarlak) al
          - Cursor dolu, slot boş ya da aynı tip (dolmamış) -> slota TEK adet bırak
        """
        slot = get_fn()
        if self.cursor is None:
            if slot is not None:
                half = (slot[1] + 1) // 2
                remaining = slot[1] - half
                set_fn([slot[0], remaining] if remaining > 0 else None)
                self.cursor = [slot[0], half]
            return

        if slot is None:
            set_fn([self.cursor[0], 1])
            self.cursor[1] -= 1
        elif slot[0] == self.cursor[0] and slot[1] < I.stack_max(slot[0]):
            slot[1] += 1
            self.cursor[1] -= 1
        if self.cursor is not None and self.cursor[1] <= 0:
            self.cursor = None

    def drop_cursor_into_inventory(self):
        """Envanter kapatılırken elde tutulan stack varsa geri dağıt; sığmayan kaybolur."""
        if self.cursor is None:
            return
        leftover = self.add_item(self.cursor[0], self.cursor[1])
        self.cursor = None if leftover == 0 else [self.cursor[0], leftover]
