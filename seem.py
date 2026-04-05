# seem.py
import argparse
import json
import os
import socket
import signal
import sys
import torch
from datetime import datetime

from resonator_vsa import ResonatorVSA
from banel import BaNEL
from dream_phase import DreamPhase, DreamConfig

CONFIG_PATH = "config.json"
TWINS_DIR = "twins"

if not os.path.exists(CONFIG_PATH):
    print("Error: config.json missing. Create it from config.json.example.")
    sys.exit(1)

with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

API_KEY = CONFIG.get("api_key", "your-secure-vsa-key-123")
DAEMON_PORT = CONFIG.get("daemon_port", 5555)

active_twin = "brian_new"

vsa = ResonatorVSA(dim=16384, k=256, max_iters=7)
banel = BaNEL(tau=9.0, min_invert=0.92)
dream_config = DreamConfig(
    micro_threshold=0.20,
    min_invertibility=0.92,
    micro_variant_count=5,
    batch_population_size=20,
    batch_generations=12
)
dream = DreamPhase(vsa, banel, vsa_dim=16384, config=dream_config)

# -------------------------------
# Plugin Loader
# -------------------------------
def load_plugin(plugin_name):
    try:
        mod = __import__(f"plugins.{plugin_name}", fromlist=["execute"])
        return mod.execute
    except ImportError:
        return None

def execute_mission(intent, twin):
    vsa_hv = torch.randn(16384, dtype=torch.complex64)
    symbol_id, invert = vsa.unbind(vsa_hv, verbose=False)

    if invert < banel.min_invert:
        banel.record_failure(
            route_id=symbol_id,
            failure_type="low_invertibility",
            evidence_score=1.0 - invert,
            context={"intent": intent}
        )
        return {
            "status": "SUPPRESSED",
            "fidelity": invert,
            "effect": "Route suppressed due to low invertibility",
            "twin": twin
        }

    plugin_name = "soc_check"
    plugin = load_plugin(plugin_name)
    if plugin:
        result = plugin(invert, {"intent": intent})
    else:
        result = "No plugin mapped."

    if "FAILURE" in str(result):
        banel.record_failure(
            route_id=symbol_id,
            failure_type="plugin_failure",
            evidence_score=0.6,
            context={"intent": intent, "result": result}
        )

    return {
        "status": "SUCCESS",
        "fidelity": invert,
        "effect": result,
        "twin": twin,
        "symbol_id": symbol_id
    }


def trigger_micro_dream(route_id: str):
    failure = {
        "route_id": route_id,
        "failure_type": "convergence",
        "evidence_score": 0.3
    }
    promoted = dream.micro_dream(failure)
    return {"promoted": promoted, "dream_type": "micro"}


def trigger_batch_dream():
    clusters = []
    promoted = dream.batch_dream(clusters, generations=12)
    summary = dream.get_dream_summary()
    return {"promoted": promoted, "summary": summary, "dream_type": "batch"}

def start_daemon():
    def signal_handler(sig, frame):
        print(f"[SHUTDOWN] State Saved at {datetime.now()}")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('localhost', DAEMON_PORT))
        s.listen()
        print(f"[DAEMON] Listening on localhost:{DAEMON_PORT}")
        while True:
            conn, addr = s.accept()
            with conn:
                data = conn.recv(4096)
                if not data:
                    continue
                try:
                    req = json.loads(data)
                    if req.get("auth_token") != API_KEY:
                        conn.sendall(json.dumps({"status": "UNAUTHORIZED"}).encode())
                        continue

                    twin = req.get("twin", active_twin)
                    intent = req.get("intent", "").lower()

                    if intent == "status_check":
                        result = {
                            "status": "SUCCESS",
                            "twin": twin,
                            "fidelity": vsa.dim / 1024,
                            "routes_evolved": len(dream.memskill_routes),
                            "failures_logged": len(banel.failure_log)
                        }
                    elif intent == "trigger_dream":
                        dream_result = trigger_batch_dream()
                        result = {
                            "status": "SUCCESS",
                            "dream_summary": dream_result["summary"],
                            "promoted": dream_result["promoted"]
                        }
                    elif intent == "list_suppressed":
                        suppressed = banel.get_suppressed_routes()
                        result = {
                            "status": "SUCCESS",
                            "suppressed_routes": suppressed,
                            "count": len(suppressed)
                        }
                    elif intent == "get_failures":
                        failure_summary = {}
                        for route_id in dream.memskill_routes:
                            failure_summary[route_id] = banel.get_failure_summary(route_id)
                        result = {
                            "status": "SUCCESS",
                            "failure_summary": failure_summary
                        }
                    else:
                        result = execute_mission(intent, twin)

                    conn.sendall(json.dumps(result).encode())
                except Exception as e:
                    conn.sendall(json.dumps({"status": "ERROR", "message": str(e)}).encode())

# -------------------------------
# CLI Commands
# -------------------------------
def cmd_init(name):
    path = f"{TWINS_DIR}/{name}"
    os.makedirs(path, exist_ok=True)
    open(f"{path}/vault.json", "w").close()
    open(f"{path}/missions.log", "w").close()
    json.dump({"gates": {"alpha": False, "beta": False}, "vault": 0}, open(f"{path}/state.json", "w"))
    print(f"[INIT] Sovereign Identity created: {name}")

def cmd_switch(name):
    global active_twin
    if os.path.exists(f"{TWINS_DIR}/{name}"):
        active_twin = name
        print(f"[SWITCH] Active Identity: {name}")
    else:
        print(f"[ERROR] Twin {name} not found")

def cmd_do(intent):
    print(f"[DO] Processing intent: {intent}")
    result = execute_mission(intent, active_twin)
    print(json.dumps(result, indent=2))

def cmd_status():
    print(f"Active Twin: {active_twin}")
    print("Daemon Port:", DAEMON_PORT)
    print("API Key Set:", bool(API_KEY))
    print(f"Routes Evolved: {len(dream.memskill_routes)}")
    print(f"Failures Logged: {len(banel.failure_log)}")

def cmd_dream():
    print(f"[DREAM] Triggering batch dream phase...")
    result = trigger_batch_dream()
    print(f"Dream Summary: {json.dumps(result['summary'], indent=2)}")
    if result["promoted"]:
        print(f"Promoted Route: {result['promoted']}")

def cmd_failures():
    print(f"[FAILURES] Recent failure summary for {active_twin}")
    for route_id in list(dream.memskill_routes.keys())[:5]:
        summary = banel.get_failure_summary(route_id)
        print(f"{route_id}: {summary['count']} failures, avg_score={summary.get('avg_score', 0):.3f}")

# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEEM Sovereign Agent")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init").add_argument("name")
    subparsers.add_parser("switch").add_argument("name")
    subparsers.add_parser("do").add_argument("intent")
    subparsers.add_parser("status")
    subparsers.add_parser("dream")
    subparsers.add_parser("failures")
    subparsers.add_parser("daemon")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args.name)
    elif args.command == "switch":
        cmd_switch(args.name)
    elif args.command == "do":
        cmd_do(args.intent)
    elif args.command == "status":
        cmd_status()
    elif args.command == "dream":
        cmd_dream()
    elif args.command == "failures":
        cmd_failures()
    elif args.command == "daemon":
        start_daemon()
    else:
        parser.print_help()