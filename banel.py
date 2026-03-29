import torch
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FailureRecord:
    route_id: str
    failure_type: str
    timestamp: str
    evidence_score: float
    context: Dict = field(default_factory=dict)


class BaNEL:
    def __init__(self, tau: float = 9.0, min_invert: float = 0.92, decay_rate: float = 0.95):
        self.tau = tau
        self.min_invert = min_invert
        self.decay_rate = decay_rate

        self.routes = {}
        self.failure_log: List[FailureRecord] = []
        self.suppression_weights = {}

    def record_failure(
        self,
        route_id: str,
        failure_type: str,
        evidence_score: float,
        context: Optional[Dict] = None
    ) -> FailureRecord:
        record = FailureRecord(
            route_id=route_id,
            failure_type=failure_type,
            timestamp=datetime.now().isoformat(),
            evidence_score=evidence_score,
            context=context or {}
        )
        self.failure_log.append(record)

        if route_id not in self.suppression_weights:
            self.suppression_weights[route_id] = 0.0

        self.suppression_weights[route_id] += evidence_score

        return record

    def should_suppress(self, route_id: str, proposal_prob: float) -> bool:
        if route_id not in self.suppression_weights:
            return False

        suppression_weight = self.suppression_weights[route_id]
        failure_prob = min(suppression_weight / 10.0, 1.0)

        if failure_prob == 0:
            return False

        likelihood_ratio = proposal_prob / (failure_prob + 1e-8)

        return likelihood_ratio <= self.tau

    def get_suppressed_routes(self) -> List[str]:
        return [
            route_id
            for route_id, weight in self.suppression_weights.items()
            if weight > 0.5
        ]

    def apply_decay(self, factor: float = None):
        if factor is None:
            factor = self.decay_rate

        for route_id in self.suppression_weights:
            self.suppression_weights[route_id] *= factor

    def get_failure_summary(self, route_id: str) -> Dict:
        route_failures = [f for f in self.failure_log if f.route_id == route_id]

        if not route_failures:
            return {"count": 0, "types": [], "avg_score": 0.0}

        failure_types = {}
        total_score = 0.0

        for failure in route_failures:
            failure_types[failure.failure_type] = failure_types.get(failure.failure_type, 0) + 1
            total_score += failure.evidence_score

        return {
            "count": len(route_failures),
            "types": failure_types,
            "avg_score": total_score / len(route_failures),
            "suppression_weight": self.suppression_weights.get(route_id, 0.0)
        }

    def compute_route_quality(self, route_id: str, base_fitness: float, inv_score: float) -> float:
        if self.should_suppress(route_id, base_fitness):
            return base_fitness * 0.5

        return base_fitness * (inv_score / self.min_invert)

    def reset_route(self, route_id: str):
        if route_id in self.suppression_weights:
            self.suppression_weights[route_id] = 0.0
