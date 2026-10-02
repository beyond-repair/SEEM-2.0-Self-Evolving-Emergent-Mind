"""Claim-0 pytest suite for SEEM 2.0 offline sketch."""
from __future__ import annotations

import numpy as np
import pytest

from banel import BaNEL
from dream_phase import DreamConfig, DreamPhase
from offline_guard import OfflineModeError, refuse_network_helpers, require_telegram_token, telegram_token
from resonator_vsa import ResonatorVSA, random_hv
import main as seem_main


DIM = 512  # fast tests; demo uses 16384


@pytest.fixture
def vsa():
    return ResonatorVSA(dim=DIM, k=64, max_iters=4, codebook_size=64, seed=0)


def test_random_hv_unit_magnitude(vsa):
    hv = random_hv(DIM)
    mags = np.abs(hv)
    assert np.allclose(mags, 1.0, atol=1e-5)


def test_bind_unbind_floor_high(vsa):
    floor = vsa.bind_unbind_floor()
    assert floor >= 0.99


def test_bind_unbind_floor_behavior_multiple(vsa):
    floors = [vsa.bind_unbind_floor() for _ in range(5)]
    assert min(floors) >= 0.99
    assert all(f <= 1.0 + 1e-6 for f in floors)


def test_unbind_returns_symbol_and_score(vsa):
    a = random_hv(DIM, vsa.rng)
    b = random_hv(DIM, vsa.rng)
    c = vsa.bind(a, b)
    sid, inv = vsa.unbind(c, b, verbose=False)
    assert sid.startswith("symbol_")
    assert 0.0 <= inv <= 1.0


def test_banel_record_failure_and_summary():
    banel = BaNEL(tau=9.0)
    banel.record_failure("r1", "convergence", 0.4)
    banel.record_failure("r1", "timeout", 0.3)
    summary = banel.get_failure_summary("r1")
    assert summary["count"] == 2
    assert summary["types"]["convergence"] == 1
    assert summary["avg_score"] == pytest.approx(0.35)


def test_banel_suppress_after_evidence():
    banel = BaNEL(tau=9.0)
    # weight 0.6 > 0.5 → flagged; likelihood_ratio = 0.1 / 0.06 ≈ 1.67 <= 9 → suppress
    banel.record_failure("bad", "convergence", 0.6)
    assert "bad" in banel.get_suppressed_routes()
    assert banel.should_suppress("bad", proposal_prob=0.1) is True


def test_banel_no_suppress_unknown_route():
    banel = BaNEL()
    assert banel.should_suppress("missing", 0.9) is False
    assert banel.get_failure_summary("missing")["count"] == 0


def test_banel_decay_reduces_weight():
    banel = BaNEL(decay_rate=0.5)
    banel.record_failure("r", "x", 1.0)
    before = banel.suppression_weights["r"]
    banel.apply_decay()
    assert banel.suppression_weights["r"] == pytest.approx(before * 0.5)


def test_banel_compute_route_quality_suppresses():
    banel = BaNEL(tau=9.0, min_invert=0.92)
    banel.record_failure("r", "x", 0.8)
    q = banel.compute_route_quality("r", base_fitness=0.1, inv_score=0.95)
    assert q == pytest.approx(0.05)


def test_micro_dream_promotion_path(vsa):
    banel = BaNEL()
    # Low parent fitness so mutated variants can beat parent+0.03
    config = DreamConfig(
        min_bind_floor=0.85,
        min_invertibility=0.0,
        micro_variant_count=8,
        batch_generations=2,
        batch_population_size=8,
    )
    dream = DreamPhase(vsa, banel, vsa_dim=DIM, config=config)
    a = random_hv(DIM, vsa.rng)
    b = random_hv(DIM, vsa.rng)
    composite = vsa.bind(a, b)
    dream.seed_route(
        "seed",
        {
            "hv": composite,
            "role": b,
            "filler": a,
            "role_b": b,
            "max_iters": 8,  # poor iters_saved → low fitness
            "k_lambda": 0.15,
            "old_iters": 10,
            "domain_match": 0.5,
            "fitness": 0.2,
        },
    )
    promoted = dream.micro_dream(
        {"route_id": "seed", "failure_type": "convergence", "evidence_score": 0.25}
    )
    # Promotion is stochastic; at least failure was recorded and path executed
    assert banel.get_failure_summary("seed")["count"] == 1
    assert dream.get_dream_summary()["routes_evolved"] >= 1
    if promoted:
        assert promoted in dream.memskill_routes


def test_batch_dream_promotion_path(vsa):
    banel = BaNEL()
    config = DreamConfig(
        min_bind_floor=0.85,
        min_invertibility=0.0,
        batch_population_size=8,
        batch_generations=3,
    )
    dream = DreamPhase(vsa, banel, vsa_dim=DIM, config=config)
    promoted = dream.batch_dream([{"grounding_bond": 0.9, "id": "c1"}], generations=3)
    assert promoted is not None
    assert promoted in dream.memskill_routes
    assert dream.get_dream_summary()["batch_dreams"] == 1


def test_batch_dream_skips_weak_clusters(vsa):
    dream = DreamPhase(vsa, BaNEL(), vsa_dim=DIM)
    assert dream.batch_dream([{"grounding_bond": 0.1, "id": "weak"}]) is None


def test_offline_refusal_without_telegram_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert telegram_token({}) is None
    with pytest.raises(OfflineModeError):
        require_telegram_token({})
    with pytest.raises(OfflineModeError):
        refuse_network_helpers({})


def test_offline_refusal_placeholder_token():
    with pytest.raises(OfflineModeError):
        require_telegram_token({"TELEGRAM_BOT_TOKEN": "YOUR_BOT_TOKEN_HERE"})


def test_main_offline_cycle_runs():
    # Smaller dim for test speed; production demo uses 16384 via CLI defaults
    result = seem_main.run_offline_cycle(dim=DIM, codebook_size=64)
    assert result["claim"] == 0
    assert result["lifecycle"] == "SUPERSEDED"
    assert result["successor"] == "sovereign-clean-room"
    assert result["bind_unbind_floor"] >= 0.85
    assert result["failures_logged"] >= 3
    assert "telegram" in result
