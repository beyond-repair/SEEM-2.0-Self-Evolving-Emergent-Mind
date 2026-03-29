import torch
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from resonator_vsa import ResonatorVSA
from banel import BaNEL


@dataclass
class DreamConfig:
    micro_threshold: float = 0.20
    min_invertibility: float = 0.92
    micro_variant_count: int = 5
    batch_population_size: int = 20
    batch_generations: int = 12
    fitness_weights: Dict[str, float] = field(default_factory=lambda: {
        'unbind_cosine': 0.6,
        'iters_saved': 0.3,
        'domain_match': 0.1
    })


class DreamPhase:
    def __init__(
        self,
        resonator: ResonatorVSA,
        banel: BaNEL,
        vsa_dim: int = 16384,
        config: Optional[DreamConfig] = None
    ):
        self.resonator = resonator
        self.banel = banel
        self.vsa_dim = vsa_dim
        self.config = config or DreamConfig()

        self.memskill_routes: Dict[str, Dict] = {}
        self.dream_log: List[Dict] = []

    def micro_dream(self, failure: Dict) -> Optional[str]:
        route_id = failure.get("route_id")
        if not route_id or route_id not in self.memskill_routes:
            return None

        parent = self.memskill_routes[route_id]

        evidence_score = failure.get("evidence_score", 0.5)
        self.banel.record_failure(
            route_id=route_id,
            failure_type=failure.get("failure_type", "unknown"),
            evidence_score=evidence_score,
            context=failure
        )

        variants = self._mutate_routes(parent, num_variants=self.config.micro_variant_count)
        best, best_fitness = None, -float('inf')

        for variant in variants:
            fitness = self._compute_fitness(variant)
            _, inv = self.resonator.unbind(variant["hv"], variant.get("role"), variant, verbose=False)

            if inv < self.config.min_invertibility:
                continue

            adjusted_fitness = self.banel.compute_route_quality(route_id, fitness, inv)

            if adjusted_fitness > best_fitness:
                best_fitness = adjusted_fitness
                best = variant

        improvement_threshold = parent.get("fitness", 0) + 0.03
        if best and best_fitness > improvement_threshold:
            dream_record = {
                "type": "micro_dream",
                "timestamp": datetime.now().isoformat(),
                "parent_id": route_id,
                "parent_fitness": parent.get("fitness", 0),
                "new_fitness": best_fitness,
                "improvement": best_fitness - parent.get("fitness", 0)
            }
            self.dream_log.append(dream_record)
            return self._promote(best, route_id)

        return None

    def batch_dream(self, clusters: List[Dict], generations: Optional[int] = None) -> Optional[str]:
        if generations is None:
            generations = self.config.batch_generations

        candidates = [c for c in clusters if c.get("grounding_bond", 0) > 0.85]
        if not candidates:
            return None

        population = list(self.memskill_routes.values())[:self.config.batch_population_size - 6]
        population += [
            self._random_route_from_cluster(candidates[0])
            for _ in range(min(6, self.config.batch_population_size - len(population)))
        ]

        for gen in range(generations):
            fitnesses = [self._compute_fitness(r) for r in population]

            sorted_pop = sorted(zip(fitnesses, population), key=lambda x: x[0], reverse=True)
            elite = [p for _, p in sorted_pop[:len(population)//2]]

            offspring = []
            for i in range(len(elite)):
                p1 = elite[i]
                p2 = elite[(i + 1) % len(elite)]
                child = self._crossover_routes(p1, p2)
                child = self._mutate_route(child, rate=0.12)
                offspring.append(child)

            population = elite + offspring

        fitnesses = [self._compute_fitness(r) for r in population]
        best_idx = fitnesses.index(max(fitnesses))
        best = population[best_idx]

        _, inv = self.resonator.unbind(best["hv"], best.get("role"), best, verbose=False)

        if inv >= self.config.min_invertibility:
            dream_record = {
                "type": "batch_dream",
                "timestamp": datetime.now().isoformat(),
                "generations": generations,
                "final_fitness": self._compute_fitness(best),
                "invertibility": inv
            }
            self.dream_log.append(dream_record)
            return self._promote(best)

        return None

    def _mutate_routes(self, parent: Dict, num_variants: int) -> List[Dict]:
        variants = []
        for _ in range(num_variants):
            v = {
                "hv": parent["hv"].clone() + torch.randn_like(parent["hv"]) * 0.08,
                "role": parent.get("role", torch.zeros(self.vsa_dim)).clone(),
                "max_iters": max(3, parent.get("max_iters", 5) + random.choice([-1, 0, 1])),
                "k_lambda": parent.get("k_lambda", 0.15) + random.uniform(-0.05, 0.05),
                "old_iters": parent.get("old_iters", 10),
                "domain_match": parent.get("domain_match", 0.8) + random.uniform(-0.05, 0.05)
            }
            v["domain_match"] = max(0.0, min(1.0, v["domain_match"]))
            variants.append(v)
        return variants

    def _mutate_route(self, route: Dict, rate: float) -> Dict:
        route["hv"] = route["hv"].clone() + torch.randn_like(route["hv"]) * rate
        return route

    def _crossover_routes(self, p1: Dict, p2: Dict) -> Dict:
        child = {
            "hv": (p1["hv"] + p2["hv"]) / 2,
            "role": p1.get("role", torch.zeros(self.vsa_dim)).clone(),
            "max_iters": random.choice([p1.get("max_iters", 5), p2.get("max_iters", 5)]),
            "k_lambda": (p1.get("k_lambda", 0.15) + p2.get("k_lambda", 0.15)) / 2,
            "old_iters": p1.get("old_iters", 10),
            "domain_match": (p1.get("domain_match", 0.8) + p2.get("domain_match", 0.8)) / 2
        }
        return child

    def _random_route_from_cluster(self, cluster: Dict) -> Dict:
        return {
            "hv": torch.randn(self.vsa_dim, dtype=torch.complex64),
            "role": torch.zeros(self.vsa_dim, dtype=torch.complex64),
            "max_iters": random.randint(4, 8),
            "k_lambda": random.uniform(0.1, 0.2),
            "old_iters": 10,
            "domain_match": random.uniform(0.7, 0.95),
            "fitness": 0.0
        }

    def _compute_fitness(self, route: Dict) -> float:
        _, cosine = self.resonator.unbind(route["hv"], route.get("role"), route, verbose=False)
        saved = (route.get("old_iters", 10) - route.get("max_iters", 5)) / 10.0
        match = route.get("domain_match", 0.8)

        weights = self.config.fitness_weights
        fitness = (
            weights['unbind_cosine'] * cosine +
            weights['iters_saved'] * saved +
            weights['domain_match'] * match
        )
        return max(0.0, min(1.0, fitness))

    def _promote(self, route: Dict, parent_id: Optional[str] = None) -> str:
        new_id = f"ROUTE_{len(self.memskill_routes)}"
        route["id"] = new_id
        route["fitness"] = self._compute_fitness(route)
        route["promoted_at"] = datetime.now().isoformat()

        self.memskill_routes[new_id] = route

        return new_id

    def seed_route(self, route_id: str, route: Dict):
        self.memskill_routes[route_id] = route

    def get_dream_summary(self) -> Dict:
        micro_dreams = [d for d in self.dream_log if d["type"] == "micro_dream"]
        batch_dreams = [d for d in self.dream_log if d["type"] == "batch_dream"]

        total_improvement = sum(d.get("improvement", 0) for d in micro_dreams)

        return {
            "total_dreams": len(self.dream_log),
            "micro_dreams": len(micro_dreams),
            "batch_dreams": len(batch_dreams),
            "total_improvement": total_improvement,
            "avg_improvement": total_improvement / len(micro_dreams) if micro_dreams else 0.0,
            "routes_evolved": len(self.memskill_routes)
        }
