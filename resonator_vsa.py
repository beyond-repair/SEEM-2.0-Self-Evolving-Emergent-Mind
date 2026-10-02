"""Resonator VSA — Claim-0 offline sketch (numpy complex hypervectors).

SUPERSEDED by sovereign-clean-room. This is a historical bind/unbind sketch,
not AGI or consciousness. Invertibility scores are toy metrics for the demo.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np


def _unitize(x: np.ndarray) -> np.ndarray:
    return x / (np.abs(x) + 1e-8)


def random_hv(dim: int, rng: Optional[np.random.Generator] = None) -> np.ndarray:
    """Unit-magnitude complex hypervector (FHRR-style sketch)."""
    rng = rng or np.random.default_rng()
    phases = rng.uniform(0.0, 2.0 * np.pi, size=dim)
    return np.exp(1j * phases).astype(np.complex64)


class ResonatorVSA:
    def __init__(
        self,
        dim: int = 16384,
        k: int = 256,
        max_iters: int = 7,
        codebook_size: int = 256,
        seed: Optional[int] = 0,
    ):
        self.dim = dim
        self.k = k
        self.max_iters = max_iters
        self.codebook_size = codebook_size
        self.rng = np.random.default_rng(seed)
        self.codebook = self._init_codebook(codebook_size, dim)

    def _init_codebook(self, size: int, dim: int) -> np.ndarray:
        # Claim-0 default codebook is small so clean-clone demos fit in memory.
        # Blueprint mentioned ~10k; successor sovereign-clean-room owns the real engine.
        cb = self.rng.normal(size=(size, dim)) + 1j * self.rng.normal(size=(size, dim))
        cb = cb.astype(np.complex64)
        return _unitize(cb)

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a = _unitize(a.astype(np.complex64))
        b = _unitize(b.astype(np.complex64))
        return a * np.conj(b)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a = _unitize(a.astype(np.complex64))
        b = _unitize(b.astype(np.complex64))
        # Real part of normalized Hermitian inner product in [0, 1] after abs clamp.
        raw = np.vdot(a, b) / self.dim
        return float(min(1.0, abs(raw)))

    def unbind(
        self,
        composite: np.ndarray,
        role: Optional[np.ndarray] = None,
        route: Optional[Dict] = None,
        verbose: bool = False,
    ) -> Tuple[str, float]:
        composite = _unitize(composite.astype(np.complex64))

        if role is not None:
            role = _unitize(role.astype(np.complex64))
            # With bind(a,b)=a*conj(b), multiply by role=b recovers ~a when |b_i|=1.
            h = composite * role
        else:
            h = composite.copy()

        max_iters = self.max_iters
        if route and "max_iters" in route:
            max_iters = min(int(route["max_iters"]), self.max_iters)

        k = self.k
        if route and "k_lambda" in route:
            k = max(16, int(self.k * float(route["k_lambda"]) / 0.15))
        k = min(k, self.dim)

        best_inv = 0.0
        for t in range(max_iters):
            h_magnitude = np.abs(h)
            if k < self.dim:
                top_indices = np.argpartition(h_magnitude, -k)[-k:]
                h_sparse = np.zeros_like(h)
                h_sparse[top_indices] = h[top_indices]
            else:
                h_sparse = h

            peak = np.abs(h_sparse).max() + 1e-8
            h_normalized = h_sparse / peak

            # |<h, codebook_row>| for each row
            cb_similarity = np.abs(self.codebook.conj() @ h_normalized)
            # Softmax over codebook scores
            shifted = cb_similarity - cb_similarity.max()
            scores = np.exp(shifted)
            scores = scores / (scores.sum() + 1e-8)
            h = scores @ self.codebook

            inv_score = float(min(1.0, abs(np.vdot(h, composite)) / (self.dim ** 0.5)))

            if verbose and t == max_iters - 1:
                print(f"    [Resonator iter {t+1}/{max_iters}] inv_score: {inv_score:.4f}")

            if inv_score > 0.95 or (best_inv > 0 and inv_score < best_inv * 0.98):
                break
            best_inv = max(best_inv, inv_score)

        final_inv = float(min(1.0, abs(np.vdot(h, composite)) / (self.dim ** 0.5)))
        # Deterministic-ish id from first few components (hash of bytes)
        head = composite[:8].tobytes()
        symbol_id = f"symbol_{hash(head) & 0x7fffffff}"
        return symbol_id, final_inv

    def bind_unbind_floor(
        self,
        a: Optional[np.ndarray] = None,
        b: Optional[np.ndarray] = None,
    ) -> float:
        """Round-trip floor: bind(a,b) then * b should recover a (unit FHRR sketch)."""
        if a is None:
            a = random_hv(self.dim, self.rng)
        if b is None:
            b = random_hv(self.dim, self.rng)
        composite = self.bind(a, b)
        recovered = _unitize(composite * b)  # recovers a when |b_i|=1
        return self.similarity(recovered, a)
