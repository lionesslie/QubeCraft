"""
Saf numpy ile seed'lenebilir 2D Perlin noise + FBM (fractal brownian motion).
`noise` / `opensimplex` gibi harici paketlere ihtiyaç duymaz.

Kullanım:
    n = PerlinNoise2D(seed=1234)
    value = n.fbm(x, z, octaves=4, persistence=0.5, lacunarity=2.0, scale=64.0)
    # value yaklaşık -1..1 aralığında
"""
import numpy as np


class PerlinNoise2D:
    def __init__(self, seed: int = 0):
        rng = np.random.default_rng(seed)
        perm = np.arange(256, dtype=np.int32)
        rng.shuffle(perm)
        self.perm = np.concatenate([perm, perm]).astype(np.int32)  # 512 uzunluk, taşma olmasın diye

        # 8 yön için gradyan vektörleri (basit ve hızlı, klasik Perlin'e yakın sonuç verir)
        angles = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        self.grads = np.stack([np.cos(angles), np.sin(angles)], axis=1)  # (8,2)

    @staticmethod
    def _fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    @staticmethod
    def _lerp(a, b, t):
        return a + t * (b - a)

    def _grad_index(self, xi, yi):
        h = self.perm[(self.perm[xi & 255] + yi) & 255]
        return h & 7

    def _dot_grad(self, xi, yi, x, y):
        idx = self._grad_index(xi, yi)
        g = self.grads[idx]
        return g[0] * x + g[1] * y

    def noise(self, x: float, y: float) -> float:
        """Tek koordinat için Perlin noise değeri, yaklaşık -1..1 aralığında."""
        x0 = int(np.floor(x))
        y0 = int(np.floor(y))
        x1, y1 = x0 + 1, y0 + 1

        sx = x - x0
        sy = y - y0

        n00 = self._dot_grad(x0, y0, sx, sy)
        n10 = self._dot_grad(x1, y0, sx - 1, sy)
        n01 = self._dot_grad(x0, y1, sx, sy - 1)
        n11 = self._dot_grad(x1, y1, sx - 1, sy - 1)

        u = self._fade(sx)
        v = self._fade(sy)

        nx0 = self._lerp(n00, n10, u)
        nx1 = self._lerp(n01, n11, u)
        return self._lerp(nx0, nx1, v)

    def fbm(self, x: float, y: float, octaves: int = 4, persistence: float = 0.5,
            lacunarity: float = 2.0, scale: float = 64.0) -> float:
        """Birden fazla oktavı üst üste bindirip daha doğal görünen arazi gürültüsü üretir."""
        total = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_amp = 0.0
        for _ in range(octaves):
            total += self.noise(x / scale * frequency, y / scale * frequency) * amplitude
            max_amp += amplitude
            amplitude *= persistence
            frequency *= lacunarity
        return total / max_amp if max_amp > 0 else 0.0

    def fbm_grid(self, x0: int, z0: int, size: int, octaves=4, persistence=0.5,
                 lacunarity=2.0, scale=64.0) -> np.ndarray:
        """size x size'lık bir alan için fbm değerlerini hesaplar (chunk üretimi için)."""
        out = np.empty((size, size), dtype=np.float64)
        for i in range(size):
            for j in range(size):
                out[i, j] = self.fbm(x0 + i, z0 + j, octaves, persistence, lacunarity, scale)
        return out
