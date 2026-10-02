#!/usr/bin/env python3
"""
Integrated demo showing Resonator VSA, BaNEL, and Dream Phase working together.
Claim-0 offline path — no Telegram token, no torch, no network required.

Run: python demo_integrated.py
     python main.py
"""
from __future__ import annotations

import json

import numpy as np

from banel import BaNEL
from dream_phase import DreamConfig, DreamPhase
from resonator_vsa import ResonatorVSA, random_hv

print("=" * 70)
print("SEEM 2.0: Integrated Demo (VSA + BaNEL + Dream Phase) — Claim-0 offline")
print("SUPERSEDED → sovereign-clean-room | not AGI")
print("=" * 70)

DIM = 16384
vsa = ResonatorVSA(dim=DIM, k=256, max_iters=5, codebook_size=256, seed=1)
banel = BaNEL(tau=9.0, min_invert=0.92, decay_rate=0.95)

config = DreamConfig(
    micro_threshold=0.20,
    min_invertibility=0.0,
    min_bind_floor=0.85,
    micro_variant_count=5,
    batch_population_size=12,
    batch_generations=4,
)

dream = DreamPhase(vsa, banel, vsa_dim=DIM, config=config)

print("\n[1] RESONATOR VSA: Generate composite hypervector")
print("-" * 70)

rng = np.random.default_rng(7)
hv1 = random_hv(DIM, rng)
hv2 = random_hv(DIM, rng)

composite = vsa.bind(hv1, hv2)
floor = vsa.bind_unbind_floor(hv1, hv2)
symbol_id, inv_score = vsa.unbind(composite, hv2, verbose=True)

print(f"Symbol ID: {symbol_id}")
print(f"Bind/unbind floor (recover a via *b): {floor:.4f}")
print(f"Resonator inv_score (toy metric): {inv_score:.4f}")
print(f"Floor passed (>= 0.85): {floor >= 0.85}")

print("\n[2] BANEL: Record failures and suppress bad routes")
print("-" * 70)

banel.record_failure(symbol_id, "convergence", 0.15, {"attempt": 1})
print(f"Recorded failure: route={symbol_id}, evidence=0.15")
banel.record_failure(symbol_id, "convergence", 0.18, {"attempt": 2})
print(f"Recorded failure: route={symbol_id}, evidence=0.18")
banel.record_failure(symbol_id, "convergence", 0.30, {"attempt": 3})
print(f"Recorded failure: route={symbol_id}, evidence=0.30")

suppressed = banel.get_suppressed_routes()
print(f"Routes flagged for suppression: {suppressed}")
summary = banel.get_failure_summary(symbol_id)
print(f"Failure summary: {json.dumps(summary, indent=2)}")

print("\n[3] DREAM PHASE: Micro-dream (failure recovery)")
print("-" * 70)

dream.seed_route(
    symbol_id,
    {
        "hv": composite,
        "role": hv2,
        "filler": hv1,
        "role_b": hv2,
        "max_iters": 5,
        "k_lambda": 0.15,
        "old_iters": 10,
        "domain_match": 0.85,
        "fitness": floor,
    },
)

failure = {"route_id": symbol_id, "failure_type": "convergence", "evidence_score": 0.2}
promoted = dream.micro_dream(failure)
print(f"Micro-dream triggered on {symbol_id}")
if promoted:
    print(f"Promoted new route: {promoted}")
    new_route = dream.memskill_routes[promoted]
    print(f"New fitness: {new_route.get('fitness', 0):.4f}")
else:
    print("No improvement found in variants (acceptable for Claim-0 sketch)")

print("\n[4] DREAM PHASE: Batch dream (population evolution)")
print("-" * 70)

clusters = [{"grounding_bond": 0.88, "id": "cluster_1"}]
promoted_batch = dream.batch_dream(clusters, generations=4)
print("Batch dream executed over 4 generations")
if promoted_batch:
    print(f"Promoted route: {promoted_batch}")

dream_summary = dream.get_dream_summary()
print("\nDream Summary:")
for key, val in dream_summary.items():
    print(f"  {key}: {val}")

print("\n[5] INTEGRATED WORKFLOW: Full cycle")
print("-" * 70)

banel.apply_decay(factor=0.95)
print("Applied decay to suppression weights")

print("\nFinal State:")
print(f"  Total routes evolved: {len(dream.memskill_routes)}")
print(f"  Total failures logged: {len(banel.failure_log)}")
print(f"  Suppressed routes: {banel.get_suppressed_routes()}")
print(f"  Total dreams: {dream_summary['total_dreams']}")

print("\n" + "=" * 70)
print("Demo complete. Offline Claim-0 sketch OK (not AGI; SUPERSEDED).")
print("=" * 70)
