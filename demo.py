#!/usr/bin/env python3
"""
SEEM 1.7 Demo – Toy Micro-Dream Cycle
Run with: python demo.py

Demonstrates:
- Mock resonator unbind with cosine simulation
- Failure trigger → micro_dream
- Route mutation, fitness computation, SHACL mock validation
- Promotion and supersede graph update
"""

import torch
import random
from typing import Dict, List, Optional
from networkx import DiGraph
from dataclasses import dataclass

# ──────────────────────────────────────────────────────────────────────────────
# Mock Constants (from blueprint)
# ──────────────────────────────────────────────────────────────────────────────

MIN_INVERTIBILITY = 0.92
MICRO_THRESHOLD = 0.20

FITNESS_WEIGHTS = {
    'unbind_cosine': 0.6,
    'iters_saved': 0.3,
    'domain_match': 0.1
}

VSA_DIM = 16384  # blueprint default


# ──────────────────────────────────────────────────────────────────────────────
# Mock Resonator (real version would use FAISS + sparsity loop)
# ──────────────────────────────────────────────────────────────────────────────

class MockResonator:
    @staticmethod
    def unbind(hv: torch.Tensor, role: torch.Tensor, route: Dict, verbose: bool = False) -> tuple[str, float]:
        # Simulate noisy unbinding → cosine between 0.75–0.98
        cosine = random.uniform(0.75, 0.98)
        if verbose:
            print(f"  [Resonator] Simulated unbind cosine: {cosine:.3f}")
        return "mock_symbol_id", cosine


# ──────────────────────────────────────────────────────────────────────────────
# Mock SHACL Validator (real version uses pyshacl + RDF triples)
# ──────────────────────────────────────────────────────────────────────────────

def mock_validate_shacl(route: Dict, inv: float) -> bool:
    # Simple rule: pass if invertibility ≥ threshold and iters reasonable
    passes = (
        inv >= MIN_INVERTIBILITY and
        route.get("max_iters", 10) <= 7
    )
    print(f"  [SHACL mock] Invertibility {inv:.3f}, max_iters {route.get('max_iters', '?')}: {'PASS' if passes else 'FAIL'}")
    return passes


# ──────────────────────────────────────────────────────────────────────────────
# SEEMEngine – stripped-down version from blueprint pseudocode
# ──────────────────────────────────────────────────────────────────────────────

class SEEMEngine:
    def __init__(self, vsa_dim: int = VSA_DIM):
        self.vsa_dim = vsa_dim
        self.resonator = MockResonator()
        self.memskill_routes: Dict[str, Dict] = {}
        self.supersede_graph = DiGraph()

    def micro_dream(self, failure: Dict) -> Optional[str]:
        route_id = failure.get("route_id")
        if not route_id or route_id not in self.memskill_routes:
            print("[Micro-Dream] No valid route_id in failure → skipping")
            return None

        parent = self.memskill_routes[route_id]
        print(f"[Micro-Dream] Triggered on route {route_id} (fitness: {parent.get('fitness', 'N/A'):.3f})")

        variants = self._mutate_routes(parent, num_variants=5)
        best, best_fitness = None, -float('inf')

        for i, v in enumerate(variants, 1):
            fitness = self._compute_fitness(v)
            inv = self.resonator.unbind(v["hv"], v.get("role", torch.zeros(self.vsa_dim)), v, verbose=True)[1]

            if inv < MIN_INVERTIBILITY:
                print(f"  Variant {i}: invertibility {inv:.3f} < {MIN_INVERTIBILITY} → discarded")
                continue

            if not mock_validate_shacl(v, inv):
                print(f"  Variant {i}: SHACL fail → discarded")
                continue

            print(f"  Variant {i}: fitness {fitness:.3f}, inv {inv:.3f} → candidate")
            if fitness > best_fitness:
                best_fitness = fitness
                best = v

        if best and best_fitness > parent.get("fitness", 0) + 0.03:
            print(f"[Promotion] Winner fitness {best_fitness:.3f} > parent + 0.03 → promoting")
            return self._promote(best, parent.get("id"))
        else:
            print("[Micro-Dream] No sufficient improvement → no promotion")
            return None

    def _mutate_routes(self, parent: Dict, num_variants: int) -> List[Dict]:
        variants = []
        for _ in range(num_variants):
            v = parent.copy()
            v["hv"] = v["hv"] + torch.randn_like(v["hv"]) * 0.08
            v["max_iters"] = max(3, v.get("max_iters", 5) + random.choice([-1, 0, 1]))
            v["k_lambda"] = v.get("k_lambda", 0.15) + random.uniform(-0.05, 0.05)
            variants.append(v)
        return variants

    def _compute_fitness(self, route: Dict) -> float:
        cosine = self.resonator.unbind(route["hv"], route.get("role", torch.zeros(self.vsa_dim)), route)[1]
        saved = (route.get("old_iters", 10) - route.get("max_iters", 5)) / 10.0
        match = route.get("domain_match", 0.8)
        fitness = (
            FITNESS_WEIGHTS['unbind_cosine'] * cosine +
            FITNESS_WEIGHTS['iters_saved'] * saved +
            FITNESS_WEIGHTS['domain_match'] * match
        )
        return max(0.0, min(1.0, fitness))  # clamp

    def _promote(self, route: Dict, parent_id: Optional[str] = None) -> str:
        new_id = f"ROUTE_{len(self.memskill_routes) + 1}"
        self.memskill_routes[new_id] = route
        route["id"] = new_id
        route["fitness"] = self._compute_fitness(route)
        if parent_id:
            self.supersede_graph.add_edge(parent_id, new_id, type="superseded_by")
            print(f"[Supersede] {parent_id} → {new_id}")
        print(f"[Promoted] New route {new_id} (fitness: {route['fitness']:.3f})")
        return new_id


# ──────────────────────────────────────────────────────────────────────────────
# Demo Run
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== SEEM 1.7 Toy Demo: Micro-Dream on Simulated Failure ===\n")

    engine = SEEMEngine()

    # Seed an initial "bad" route
    initial_route = {
        "hv": torch.randn(VSA_DIM),
        "role": torch.zeros(VSA_DIM),
        "max_iters": 10,
        "k_lambda": 0.15,
        "old_iters": 10,
        "domain_match": 0.75,
        "fitness": 0.68  # mediocre
    }
    engine.memskill_routes["ROUTE_0"] = initial_route

    # Simulate a failure event (e.g., binding error + low cosine)
    failure_event = {
        "route_id": "ROUTE_0",
        "held_out": [],  # would be real L0 slice in prod
        "failure_type": "binding_cos < 0.92",
        "timestamp": "2026-03-21T10:18:00"
    }

    print("Initial route fitness:", initial_route["fitness"])
    print("Triggering micro-dream...\n")

    new_route_id = engine.micro_dream(failure_event)

    if new_route_id:
        print(f"\nSuccess! New evolved route created: {new_route_id}")
        print("Current supersede graph edges:", list(engine.supersede_graph.edges(data=True)))
    else:
        print("\nNo promotion this time — try again or adjust mutation noise.")

    print("\nDemo complete. Extend with real FAISS resonator, SHACL RDF, L0 logging, etc.")
