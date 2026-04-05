# SEEM 2.0: Integration Guide

## Overview

Three core modules have been implemented and integrated into the SEEM architecture:

### 1. **Resonator VSA** (`resonator_vsa.py`)

**Purpose**: Hyperdimensional semantic binding and invertibility scoring.

**Key Features**:
- Complex-valued hypervectors (16384-dim by default)
- Bind operation: `a * conj(b)` for semantic composition
- Unbind with iterative refinement (up to 7 iterations)
- FAISS-like codebook projection for convergence
- Invertibility scoring (target ≥ 0.92)

**API**:
```python
from resonator_vsa import ResonatorVSA

vsa = ResonatorVSA(dim=16384, k=256, max_iters=7)
composite = vsa.bind(hv1, hv2)
symbol_id, inv_score = vsa.unbind(composite, role_hv)
```

---

### 2. **BaNEL** (`banel.py`)

**Purpose**: Bayesian Negative Evidence Learning - track failures and suppress bad routes.

**Key Features**:
- Failure recording with evidence scores
- Suppression weight accumulation (Bayesian rejection at tau=9.0)
- Route quality adjustment based on invertibility
- Decay mechanism for time-decayed belief updates
- Failure summaries per route

**API**:
```python
from banel import BaNEL

banel = BaNEL(tau=9.0, min_invert=0.92)

# Record a failure
banel.record_failure(
    route_id="symbol_123",
    failure_type="convergence",
    evidence_score=0.3,
    context={"attempt": 1}
)

# Check if route should be suppressed
should_suppress = banel.should_suppress(route_id, proposal_prob=0.5)

# Get failure summary
summary = banel.get_failure_summary(route_id)
# Returns: {count, types, avg_score, suppression_weight}

# Decay suppression weights over time
banel.apply_decay(factor=0.95)
```

---

### 3. **Dream Phase** (`dream_phase.py`)

**Purpose**: Autonomous learning through failure-driven route evolution.

**Two-tier Learning**:

#### Micro-Dreams (< 50ms inline recovery)
- Triggered by failure detection
- Generates 5 route variants via mutation
- Selects best variant if fitness improves
- BaNEL integration: suppressed routes get 50% fitness penalty

#### Batch Dreams (background consolidation)
- Population-based evolution over 12 generations
- Elite selection + random crossover + mutation
- Fitness: 0.6×unbind_cosine + 0.3×iters_saved + 0.1×domain_match
- Promotes winners to memskill vault

**API**:
```python
from dream_phase import DreamPhase, DreamConfig

config = DreamConfig(
    micro_threshold=0.20,
    min_invertibility=0.92,
    micro_variant_count=5,
    batch_population_size=20,
    batch_generations=12
)

dream = DreamPhase(vsa, banel, vsa_dim=16384, config=config)

# Seed a route
dream.seed_route("route_123", {
    "hv": hypervector,
    "role": role_hv,
    "max_iters": 5,
    "k_lambda": 0.15,
    "old_iters": 10,
    "domain_match": 0.85,
    "fitness": 0.88
})

# Trigger micro-dream on failure
failure = {"route_id": "route_123", "failure_type": "convergence", "evidence_score": 0.2}
promoted = dream.micro_dream(failure)

# Trigger batch dream
clusters = [{"grounding_bond": 0.88}]
promoted = dream.batch_dream(clusters, generations=12)

# Get dream statistics
summary = dream.get_dream_summary()
# Returns: {total_dreams, micro_dreams, batch_dreams, total_improvement, routes_evolved}
```

---

## Integration in `seem.py`

All three modules are instantiated at startup:

```python
vsa = ResonatorVSA(dim=16384, k=256, max_iters=7)
banel = BaNEL(tau=9.0, min_invert=0.92)
dream = DreamPhase(vsa, banel, vsa_dim=16384, config=dream_config)
```

### Mission Execution Flow

1. **execute_mission(intent, twin)**
   - Generate random hypervector
   - Call `vsa.unbind()` to extract symbol
   - Check invertibility against `banel.min_invert`
   - If too low, record failure + suppress
   - If OK, execute plugin (e.g., soc_check)
   - Record failure if plugin fails
   - Return fidelity score

### Daemon Commands

The socket daemon (`start_daemon()`) now accepts:

- `intent="status_check"`: Returns twin status + routes + failures
- `intent="trigger_dream"`: Runs batch dream, returns summary
- `intent="list_suppressed"`: Lists all suppressed routes
- `intent="get_failures"`: Returns failure summaries per route
- `intent=<custom>`: Executes mission

### CLI Commands

```bash
python seem.py status          # Show active twin + metrics
python seem.py do "check system"  # Execute a mission
python seem.py dream           # Trigger batch dream phase
python seem.py failures        # Show recent failures
python seem.py daemon          # Start daemon on port 5555
```

---

## Telegram Bot Integration

Telegram bot (`telegram_bot.py`) now provides full remote control:

```bash
/status      # Twin status + routes + failures
/dream       # Trigger dream phase
/suppress    # List suppressed routes
/do <intent> # Execute mission
/switch <name> # Switch active twin
/failures    # Show recent failures
```

**Setup**:
```bash
export TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
export YOUR_TELEGRAM_ID="123456789"
export SEEM_API_KEY="your-key"
export DAEMON_HOST="localhost"
export DAEMON_PORT="5555"

python telegram_bot.py
```

---

## Demo

Run the integrated demo:

```bash
pip install -r requirements.txt
python demo_integrated.py
```

This shows:
1. VSA hypervector binding/unbinding
2. BaNEL failure tracking and suppression
3. Micro-dream variant selection
4. Batch-dream population evolution
5. Full dream summary statistics

---

## Architecture Summary

```
Twin (Agent Identity)
├── Resonator VSA (hypervector semantics)
│   └── Unbind: extract symbols, compute invertibility
├── BaNEL (failure tracking + suppression)
│   └── Routes: record failures, adjust quality
└── Dream Phase (autonomous learning)
    ├── Micro-dreams: failure → variant selection (<50ms)
    └── Batch dreams: background evolution (12 gen)

Socket Daemon
├── Accept remote requests
├── Route to execute_mission or dream triggers
└── Return JSON results

Telegram Bot
├── Remote mission control
├── Dream phase triggering
├── Status queries
└── Failure inspection
```

---

## Configuration

Edit `config.json`:

```json
{
  "api_key": "your-secure-vsa-key-123",
  "daemon_port": 5555,
  "cloud_remote": "dropbox:SEEM-backups",
  "rclone_path": "~/.config/rclone/rclone.conf"
}
```

Or use environment variables in Telegram bot setup.

---

## Next Steps

1. **L0 Evidence Base**: Wire PostgreSQL + Git for immutable logging
2. **HDDL Planning**: Integrate hierarchical task decomposition
3. **SHACL Governance**: Add RDF constraint validation
4. **Multi-twin Orchestration**: Support team coordination
5. **Performance Tuning**: Batch dreams on GPU via vLLM

---

**Status**: Core VSA, BaNEL, and Dream Phase fully integrated. Ready for autonomous operation.
