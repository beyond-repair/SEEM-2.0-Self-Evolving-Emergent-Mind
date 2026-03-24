import datetime
import os

def execute(fidelity, mission_context=None):
    if fidelity < 0.96:
        return "FAILURE: Fidelity too low for safe execution."

    output_path = os.path.expanduser("\~/seem_output.txt")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = (
        f"[{timestamp}] SEEM EFFECT: Action executed successfully\n"
        f"  Fidelity: {fidelity:.4f}\n"
        f"  Context: {mission_context.get('intent', 'N/A')}\n"
        "----------------------------------------\n"
    )

    with open(output_path, "a") as f:
        f.write(message)

    return f"SUCCESS: Logged to {output_path}"