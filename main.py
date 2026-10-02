#!/usr/bin/env python3
"""Claim-0 offline entrypoint for SEEM 2.0 (historical archive).

SUPERSEDED by https://github.com/beyond-repair/sovereign-clean-room
Not AGI / not consciousness — offline VSA→BaNEL→Dream sketch only.
"""
from __future__ import annotations

import json
import sys

import numpy as np

from banel import BaNEL
from dream_phase import DreamConfig, DreamPhase
from offline_guard import OfflineModeError, refuse_network_helpers, telegram_token
from resonator_vsa import ResonatorVSA, random_hv


def run_offline_cycle(dim: int = 16384, codebook_size: int = 256) -> dict:
    # Document offline refusal of Telegram when no token is configured.
    if telegram_token() is not None:
        telegram_status = "token present but bot not started (Claim-0 offline path)"
    else:
        try:
            refuse_network_helpers()
            telegram_status = "offline (no Telegram token)"
        except OfflineModeError as exc:
            telegram_status = str(exc)

    rng = np.random.default_rng(42)
    vsa = ResonatorVSA(dim=dim, k=min(256, dim), max_iters=5, codebook_size=codebook_size, seed=42)
    banel = BaNEL(tau=9.0, min_invert=0.92, decay_rate=0.95)
    config = DreamConfig(
        micro_variant_count=5,
        batch_population_size=12,
        batch_generations=4,
        min_bind_floor=0.85,
        min_invertibility=0.0,
    )
    dream = DreamPhase(vsa, banel, vsa_dim=dim, config=config)

    a = random_hv(dim, rng)
    b = random_hv(dim, rng)
    composite = vsa.bind(a, b)
    floor = vsa.bind_unbind_floor(a, b)
    symbol_id, inv_score = vsa.unbind(composite, b, verbose=False)

    banel.record_failure(symbol_id, "convergence", 0.15, {"attempt": 1})
    banel.record_failure(symbol_id, "convergence", 0.18, {"attempt": 2})
    banel.record_failure(symbol_id, "convergence", 0.25, {"attempt": 3})

    dream.seed_route(
        symbol_id,
        {
            "hv": composite,
            "role": b,
            "filler": a,
            "role_b": b,
            "max_iters": 5,
            "k_lambda": 0.15,
            "old_iters": 10,
            "domain_match": 0.85,
            "fitness": floor,
        },
    )
    promoted_micro = dream.micro_dream(
        {"route_id": symbol_id, "failure_type": "convergence", "evidence_score": 0.2}
    )
    promoted_batch = dream.batch_dream(
        [{"grounding_bond": 0.88, "id": "cluster_1"}], generations=4
    )
    banel.apply_decay(0.95)
    summary = dream.get_dream_summary()

    return {
        "claim": 0,
        "lifecycle": "SUPERSEDED",
        "successor": "sovereign-clean-room",
        "dim": dim,
        "bind_unbind_floor": floor,
        "resonator_inv_score": inv_score,
        "symbol_id": symbol_id,
        "suppressed_routes": banel.get_suppressed_routes(),
        "failures_logged": len(banel.failure_log),
        "promoted_micro": promoted_micro,
        "promoted_batch": promoted_batch,
        "dream_summary": summary,
        "telegram": telegram_status,
        "note": "Claim-0 sketch only — not AGI; canonical work is sovereign-clean-room",
    }


def main() -> int:
    print("=" * 70)
    print("SEEM 2.0 — Claim-0 offline demo (SUPERSEDED → sovereign-clean-room)")
    print("=" * 70)
    result = run_offline_cycle()
    print(json.dumps({k: v for k, v in result.items() if k != "dream_summary"}, indent=2))
    print("Dream summary:")
    for k, v in result["dream_summary"].items():
        print(f"  {k}: {v}")
    print(f"Telegram/remote: {result['telegram']}")
    print("=" * 70)
    print("Demo complete (offline Claim-0 sketch).")
    print("=" * 70)
    # Soft success criteria: floor is high; resonator inv is informational
    if result["bind_unbind_floor"] < 0.85:
        print("WARNING: bind/unbind floor below 0.85", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
