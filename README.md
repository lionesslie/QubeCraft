# QubeCraft (v1) — Python + OpenGL

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
- `Sol tık` (basılı tut): blok kır — survival'da elindeki alete göre HIZ değişir
  (yanlış alet ya da elle kırmak yavaştır; doğru alet çok daha hızlıdır).
  Creative'de anlık kırar.
- `Sağ tık`: seçili bloğu koy (sadece yerleştirilebilir bloklar; aletler konulamaz)
- `1-9` veya fare tekerleği: hotbar'da eşya seç
- `E`: tam envanteri aç/kapat (hotbar + 3x9 ana grid + crafting paneli;
  sol tık ile al/bırak/birleştir/takas et; creative'de ayrıca sınırsız blok paleti var)
- `ESC`: duraklat / devam et (envanterdeyken de kapatır), duraklatma menüsünden `G` ile creative↔survival,
  `+/-` ile görüş mesafesi
- `F3`: hata ayıklama bilgisini (koordinat, seed, fps...) aç/kapat

## Aletler ve kazma hızı
4 tier (Ahşap < Taş < Demir < Elmas) x 3 tür (Kazma/Balta/Kılıç) = 12 alet.
- **Kazma**: taş/moloztaşı/cevherleri hızlandırır. Cevherden ürün almak için
  yeterli tier gerekir — kömür için ahşap kazma yeter, demir için en az taş
  kazma, elmas için en az demir kazma gerekir (yetersizse blok kırılır ama
  hiçbir şey düşmez, gerçek Minecraft'taki gibi).
- **Balta**: kütük/tahta kırmayı hızlandırır.
- **Kılıç**: şu an sadece daha yüksek hasar değeri taşıyor (combat sistemi
  gelince kullanılacak, henüz düşman/mob yok).
Tüm tarifler `crafting.py` içinde otomatik üretiliyor (`items.TIER_MATERIAL`:
ahşap→tahta, taş→moloztaşı, demir→ham demir, elmas→elmas).

## Mimari
| Dosya | Görev |
|---|---|
| `textures.py` | Her blok yüzü için ayrı 16x16 piksel-art PNG üretir (assets/<isim>.png, paylaşılan atlas yok) |
| `noise_gen.py` | Harici bağımlılık olmadan, saf numpy ile seed'lenebilir Perlin noise + FBM |
| `blocks.py` | Blok tipi tanımları (id, texture eşlemesi, katılık/şeffaflık, kırılınca ne düşer) |
| `items.py` | Blok olmayan eşyalar (çubuk, kömür, demir, elmas) + alet tanımları (4 tier x 3 tür), kazma hızı/tier hesaplama |
| `world.py` | Chunk sistemi, noise ile terrain üretimi (dağ/ova), cevher yerleştirme, ağaç yerleştirme, blok get/set |
| `mesh.py` | Bir chunk için görünür yüzleri bulup OpenGL'e verilecek vertex/uv/renk listesi üretir (pyglet'ten bağımsız, test edilebilir) |
| `player.py` | Birinci şahıs hareket, çarpışma, can/açlık, düşme hasarı, raycast (pyglet'ten bağımsız, test edilebilir) |
| `inventory.py` | Yığın (stack) tabanlı envanter: hotbar + 3x9 grid, ekleme/alma/birleştirme/takas mantığı (pyglet'ten bağımsız, test edilebilir) |
| `crafting.py` | Tarif listesi + envanterden malzeme harcayıp ürün üretme mantığı (pyglet'ten bağımsız, test edilebilir) |
| `main.py` | Pencere, OpenGL kurulum, girdi, menü/HUD/envanter/crafting ekranı, kazma ilerlemesi, chunk yükleme |

`mesh.py`, `player.py`, `inventory.py` ve `crafting.py`'ı bilerek pyglet'e
bağımlı yapmadım; böylece mantık hatalarını pyglet kurulu olmayan bir
ortamda bile test edebildim (hepsini burada gerçekten çalıştırıp doğruladım
— world gen, mining hızı hesabı, envanter al/bırak/birleştir, 14 crafting
tarifi, düşme hasarı/açlık, hepsi gerçek sayılarla test edildi).

## Şu an eksik olan / bir sonraki adımlar
1. **Combat sistemi** (düşman mob'lar / basit AI, saldırı-hasar - kılıçlar zaten hazır, karşılarına çıkacak bir şey yok henüz)
2. **Fırın/smelting** (şu an demir cevheri direkt "ham demir" düşürüyor, gerçekte fırında pişirilmesi gerekir)
3. **Yiyecek/çiftçilik** (açlık şu an sadece azalıyor, geri dolduracak yiyecek yok - dikkat, uzun oynarsan açlıktan can kaybedebilirsin)
4. **Dünya kaydetme/yükleme** (chunk'ları diske yazma, birden fazla dünya slotu)
5. Chunk unload (şu an yüklenen chunk'lar hafızada kalıyor, sonsuz gezinme
   için bellek yönetimi gerekir)
6. Daha gelişmiş menü: kayıtlı dünyaları listeleme, oyuncu görünümü/adı ayarı

## Bilinen sınırlamalar
- Chunk mesh üretimi saf Python döngüleriyle yapılıyor (numpy vektörize
  değil) — çok yüksek görüş mesafesinde (8+) ilk yükleme biraz sürebilir.
- Su/yaprak gibi şeffaf bloklarda gerçek sıralı (sorted) saydamlık yok,
  basit alfa blend kullanılıyor.
- Chunk'lar hiç kaldırılmıyor (unload), uzun süre gezinirsen bellek kullanımı artar.
- Açlık barı geri dolmuyor (yiyecek/pişirme sistemi henüz yok) — survival'da
  uzun süre oynarsan açlıktan can kaybetmeye başlarsın, bu şu an beklenen bir durum.
