import torch
import numpy as np
from typing import Tuple, Optional, Dict, List


class ResonatorVSA:
    def __init__(self, dim: int = 16384, k: int = 256, max_iters: int = 7, codebook_size: int = 10000):
        self.dim = dim
        self.k = k
        self.max_iters = max_iters
        self.codebook_size = codebook_size

        self.codebook = self._init_codebook(codebook_size, dim)

    def _init_codebook(self, size: int, dim: int) -> torch.Tensor:
        cb = torch.randn(size, dim, dtype=torch.complex64)
        cb = cb / (torch.abs(cb).unsqueeze(-1) + 1e-8)
        return cb

    def bind(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        a = a / (torch.abs(a) + 1e-8)
        b = b / (torch.abs(b) + 1e-8)
        return a * torch.conj(b)

    def unbind(
        self,
        composite: torch.Tensor,
        role: Optional[torch.Tensor] = None,
        route: Optional[Dict] = None,
        verbose: bool = False
    ) -> Tuple[str, float]:
        composite = composite / (torch.abs(composite) + 1e-8)

        if role is not None:
            role = role / (torch.abs(role) + 1e-8)
            h = composite * role
        else:
            h = composite

        max_iters = self.max_iters
        if route and "max_iters" in route:
            max_iters = min(route["max_iters"], self.max_iters)

        k = self.k
        if route and "k_lambda" in route:
            k = max(16, int(self.k * route["k_lambda"] / 0.15))

        best_inv = 0.0
        for t in range(max_iters):
            h_magnitude = torch.abs(h)
            _, top_indices = torch.topk(h_magnitude, min(k, self.dim), largest=True)

            h_sparse = h.clone()
            mask = torch.ones(self.dim, dtype=torch.bool)
            mask[top_indices] = False
            h_sparse[mask] = 0

            h_normalized = h_sparse / (torch.abs(h_sparse).max() + 1e-8)

            cb_similarity = torch.abs(torch.inner(h_normalized, self.codebook.conj()))
            scores = torch.nn.functional.softmax(cb_similarity, dim=-1)

            h = torch.sum(scores.unsqueeze(-1) * self.codebook, dim=0)

            inv_score = torch.abs(torch.inner(h, torch.conj(composite))).item() / (self.dim ** 0.5)
            inv_score = min(inv_score, 1.0)

            if verbose and t == max_iters - 1:
                print(f"    [Resonator iter {t+1}/{max_iters}] inv_score: {inv_score:.4f}")

            if inv_score > 0.95 or (best_inv > 0 and inv_score < best_inv * 0.98):
                break

            best_inv = max(best_inv, inv_score)

        final_inv = torch.abs(torch.inner(h, torch.conj(composite))).item() / (self.dim ** 0.5)
        final_inv = min(final_inv, 1.0)

        symbol_id = f"symbol_{hash(str(composite[:10].tolist())) & 0x7fffffff}"

        return symbol_id, final_inv
