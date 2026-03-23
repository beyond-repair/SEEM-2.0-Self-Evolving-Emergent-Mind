#!/usr/bin/env bash
# ping_seem.sh - Hourly SEEM daemon heartbeat & SOC alert dispatcher
# Place in crontab: 0 * * * * /path/to/scripts/ping_seem.sh

set -euo pipefail

# =============================================================================
# CONFIG – Customize these values
# =============================================================================

DAEMON_URL="http://localhost:5555/ping"          # Daemon socket endpoint
API_KEY="your-secure-vsa-key-123"                # Must match config.json
TWIN="brian_new"                                 # Active twin name

# ntfy.sh topic (create at ntfy.sh – keep private!)
NTFY_TOPIC="brian_seem_alerts"                   # Change to your private topic

# Log files
HEALTH_LOG="$HOME/seem_health.log"
MISSION_LOG="twins/$TWIN/missions.log"           # Relative to repo root

# =============================================================================
# Build authenticated JSON payload
# =============================================================================

PAYLOAD=$(cat <<EOF
{
  "auth_token": "$API_KEY",
  "intent": "monitor security logs and critical system resources",
  "twin": "$TWIN"
}
EOF
)

# =============================================================================
# Send request to daemon
# =============================================================================

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pinging SEEM daemon..." >> "$HEALTH_LOG"

RESPONSE=$(curl -s --max-time 15 -H "Content-Type: application/json" -d "$PAYLOAD" "$DAEMON_URL") || {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Daemon unreachable" >> "$HEALTH_LOG"
    notify-send -u critical "SEEM ERROR" "Daemon unreachable – check service"
    exit 1
}

# =============================================================================
# Parse & handle response
# =============================================================================

STATUS=$(echo "$RESPONSE" | jq -r '.status // "UNKNOWN"')
FIDELITY=$(echo "$RESPONSE" | jq -r '.fidelity // "unknown"')
EFFECT=$(echo "$RESPONSE" | jq -r '.effect // "No effect reported"')

LOG_LINE="[$(date '+%Y-%m-%d %H:%M:%S')] SEEM $STATUS | Fidelity: $FIDELITY | $EFFECT"

echo "$LOG_LINE" >> "$HEALTH_LOG"

if [[ "$STATUS" == "SUCCESS" ]]; then
    # Nominal – silent unless you want verbose logging
    true
elif [[ "$RESPONSE" == *"ALERT: SECURITY"* || "$RESPONSE" == *"CRITICAL"* ]]; then
    # CRITICAL SECURITY / RESOURCE EVENT – escalate
    notify-send -u critical "SEEM SECURITY ALERT" "$EFFECT"
    curl -s -d "SEEM CRITICAL ALERT: $EFFECT (fidelity $FIDELITY)" "ntfy.sh/$NTFY_TOPIC" >/dev/null
    echo "$LOG_LINE – ALERT ESCALATED" >> "$HEALTH_LOG"
elif [[ "$FIDELITY" != "unknown" && $(echo "$FIDELITY < 0.96" | bc -l) -eq 1 ]]; then
    # WARNING: Cognitive drift
    notify-send -u normal "SEEM Warning" "Cognitive Drift Detected\nFidelity: $FIDELITY\n$EFFECT"
    echo "$LOG_LINE – DRIFT WARNING" >> "$HEALTH_LOG"
else
    # Generic failure
    notify-send -u normal "SEEM Failure" "Unexpected response:\n$RESPONSE"
    echo "$LOG_LINE – GENERIC FAILURE" >> "$HEALTH_LOG"
fi

exit 0
