#!/usr/bin/env python3
"""
Integrated demo showing Resonator VSA, BaNEL, and Dream Phase working together.
Run: python demo_integrated.py
"""

import torch
import json
from resonator_vsa import ResonatorVSA
from banel import BaNEL
from dream_phase import DreamPhase, DreamConfig

print("=" * 70)
print("SEEM 2.0: Integrated Demo (VSA + BaNEL + Dream Phase)")
print("=" * 70)

vsa = ResonatorVSA(dim=16384, k=256, max_iters=7)
banel = BaNEL(tau=9.0, min_invert=0.92, decay_rate=0.95)

config = DreamConfig(
    micro_threshold=0.20,
    min_invertibility=0.92,
    micro_variant_count=5,
    batch_population_size=15,
    batch_generations=8
)

dream = DreamPhase(vsa, banel, vsa_dim=16384, config=config)

print("\n[1] RESONATOR VSA: Generate composite hypervector")
print("-" * 70)

hv1 = torch.randn(16384, dtype=torch.complex64)
hv2 = torch.randn(16384, dtype=torch.complex64)

composite = vsa.bind(hv1, hv2)
symbol_id, inv_score = vsa.unbind(composite, hv1, verbose=True)

print(f"Symbol ID: {symbol_id}")
print(f"Invertibility Score: {inv_score:.4f}")
print(f"Passed threshold (>= 0.92): {inv_score >= 0.92}")

print("\n[2] BANEL: Record failures and suppress bad routes")
print("-" * 70)

banel.record_failure(
    route_id=symbol_id,
    failure_type="convergence",
    evidence_score=0.15,
    context={"attempt": 1}
)
print(f"Recorded failure: route={symbol_id}, evidence=0.15")

banel.record_failure(
    route_id=symbol_id,
    failure_type="convergence",
    evidence_score=0.18,
    context={"attempt": 2}
)
print(f"Recorded failure: route={symbol_id}, evidence=0.18")

suppressed = banel.get_suppressed_routes()
print(f"Routes flagged for suppression: {suppressed}")

summary = banel.get_failure_summary(symbol_id)
print(f"Failure summary: {json.dumps(summary, indent=2)}")

print("\n[3] DREAM PHASE: Micro-dream (failure recovery)")
print("-" * 70)

dream.seed_route(symbol_id, {
    "hv": composite,
    "role": hv1,
    "max_iters": 5,
    "k_lambda": 0.15,
    "old_iters": 10,
    "domain_match": 0.85,
    "fitness": inv_score
})

failure = {
    "route_id": symbol_id,
    "failure_type": "convergence",
    "evidence_score": 0.2
}

promoted = dream.micro_dream(failure)
print(f"Micro-dream triggered on {symbol_id}")
if promoted:
    print(f"Promoted new route: {promoted}")
    new_route = dream.memskill_routes[promoted]
    print(f"New fitness: {new_route.get('fitness', 0):.4f}")
else:
    print("No improvement found in variants")

print("\n[4] DREAM PHASE: Batch dream (population evolution)")
print("-" * 70)

clusters = [
    {"grounding_bond": 0.88, "id": "cluster_1"}
]

promoted_batch = dream.batch_dream(clusters, generations=8)
print(f"Batch dream executed over 8 generations")
if promoted_batch:
    print(f"Promoted route: {promoted_batch}")

dream_summary = dream.get_dream_summary()
print(f"\nDream Summary:")
for key, val in dream_summary.items():
    print(f"  {key}: {val}")

print("\n[5] INTEGRATED WORKFLOW: Full cycle")
print("-" * 70)

banel.apply_decay(factor=0.95)
print("Applied decay to suppression weights")

print(f"\nFinal State:")
print(f"  Total routes evolved: {len(dream.memskill_routes)}")
print(f"  Total failures logged: {len(banel.failure_log)}")
print(f"  Suppressed routes: {banel.get_suppressed_routes()}")
print(f"  Total dreams: {dream_summary['total_dreams']}")

print("\n" + "=" * 70)
print("Demo complete. SEEM is working!")
print("=" * 70)
