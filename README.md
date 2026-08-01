# PyCraft (v1) — Python + OpenGL Minecraft klonu

## Önemli not
Bu proje burada (Claude'un sanal ortamı) **çalıştırılıp test edilemedi**:
internet erişimi kapalı olduğu için `pyglet` kurulamadı, ayrıca ortamda
ekran/görüntü çıkışı yok. Kod dikkatle, bilinen-doğru pyglet/OpenGL
kalıpları kullanılarak yazıldı ve mantık kısımları (noise, dünya üretimi,
mesh üretimi, oyuncu fiziği/çarpışma, raycast) ayrı ayrı test edildi —
ama render/pencere/girdi kısmını ilk açtığında küçük bir hata çıkarsa
(ör. bir pyglet sürüm farkı) bana hatayı yapıştırırsan hemen düzeltirim.

## Kurulum
```bash
python -m venv venv
# Windows: venv\Scripts\activate   /  Mac-Linux: source venv/bin/activate
pip install -r requirements.txt
python main.py
```
`pyglet==1.5.29` kasıtlı sabitlendi (requirements.txt içinde açıklaması var) —
pyglet 2.x farklı bir render mimarisine geçtiği için burada kullanmadık.

## Kontroller
- `WASD`: hareket, `Boşluk`: zıpla (survival) / yüksel (creative uçuş)
- `Sol Shift`: creative'de alçal
- `Sol Ctrl`: koş
- Fare: bakış yönü
- `Sol tık`: blok kır, `Sağ tık`: seçili bloğu koy
- `1-9` veya fare tekerleği: hotbar'da blok seç
- `E`: tam envanteri aç/kapat (hotbar + 3x9 ana grid; sol tık ile al/bırak/birleştir/takas et; creative'de ayrıca sınırsız blok paleti var)
- `ESC`: duraklat / devam et (envanterdeyken de kapatır), duraklatma menüsünden `G` ile creative↔survival,
  `+/-` ile görüş mesafesi
- `F3`: hata ayıklama bilgisini (koordinat, seed, fps...) aç/kapat

## Mimari
| Dosya | Görev |
|---|---|
| `textures.py` | Her blok yüzü için ayrı 16x16 piksel-art PNG üretir (assets/<isim>.png, paylaşılan atlas yok) |
| `noise_gen.py` | Harici bağımlılık olmadan, saf numpy ile seed'lenebilir Perlin noise + FBM |
| `blocks.py` | Blok tipi tanımları (id, texture eşlemesi, katılık/şeffaflık) |
| `world.py` | Chunk sistemi, noise ile terrain üretimi (dağ/ova), ağaç yerleştirme, blok get/set |
| `mesh.py` | Bir chunk için görünür yüzleri bulup OpenGL'e verilecek vertex/uv/renk listesi üretir (pyglet'ten bağımsız, test edilebilir) |
| `player.py` | Birinci şahıs hareket, basit voxel çarpışması, yerçekimi/uçma, blok kırma-koyma için raycast (pyglet'ten bağımsız, test edilebilir) |
| `inventory.py` | Yığın (stack) tabanlı envanter: hotbar + 3x9 grid, ekleme/alma/birleştirme/takas mantığı (pyglet'ten bağımsız, test edilebilir) |
| `main.py` | Pencere, OpenGL kurulum, girdi, menü/HUD/envanter ekranı, chunk yükleme, oyunu birleştiren dosya |

`mesh.py`, `player.py` ve `inventory.py`'ı bilerek pyglet'e bağımlı yapmadım;
böylece mantık hatalarını pyglet kurulu olmayan bir ortamda bile test
edebildim (hepsini burada gerçekten çalıştırıp doğruladım).

## Şu an eksik olan / bir sonraki adımlar
Sıradaki mesajlarda şunları ekleyebiliriz (istediğin sırayla söyle yeter):
1. **Crafting sistemi** (crafting table, tarifler, örn. 4 tahta -> masa, vs.)
2. **Combat sistemi** (can barı, düşman mob'lar / basit AI, saldırı-hasar)
3. **Dünya kaydetme/yükleme** (chunk'ları diske yazma, birden fazla dünya slotu)
4. Chunk unload (şu an yüklenen chunk'lar hafızada kalıyor, sonsuz gezinme
   için bellek yönetimi gerekir)
5. Daha gelişmiş menü: kayıtlı dünyaları listeleme, oyuncu görünümü/adı ayarı

## Bilinen sınırlamalar (v1)
- Chunk mesh üretimi saf Python döngüleriyle yapılıyor (numpy vektörize
  değil) — çok yüksek görüş mesafesinde (8+) ilk yükleme biraz sürebilir.
- Su/yaprak gibi şeffaf bloklarda gerçek sıralı (sorted) saydamlık yok,
  basit alfa blend kullanılıyor.
- Chunk'lar hiç kaldırılmıyor (unload), uzun süre gezinirsen bellek kullanımı artar.
