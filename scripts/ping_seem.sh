#!/usr/bin/env bash
# scripts/ping_seem.sh - Hourly SEEM daemon heartbeat & SOC alert dispatcher
# Add to crontab: 0 * * * * /path/to/scripts/ping_seem.sh

set -euo pipefail

# =============================================================================
# CONFIGURATION - EDIT THESE VALUES
# =============================================================================

DAEMON_URL="http://localhost:5555/ping"
API_KEY="your-secure-vsa-key-123"          # Must match your config.json
TWIN="brian_new"                           # Your active twin name

# ntfy.sh topic (create a private topic at ntfy.sh)
NTFY_TOPIC="brian_seem_alerts"

# Log files
HEALTH_LOG="$HOME/seem_health.log"

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
# Parse and handle response
# =============================================================================

STATUS=$(echo "$RESPONSE" | jq -r '.status // "UNKNOWN"' 2>/dev/null || echo "UNKNOWN")
FIDELITY=$(echo "$RESPONSE" | jq -r '.fidelity // "unknown"' 2>/dev/null || echo "unknown")
EFFECT=$(echo "$RESPONSE" | jq -r '.effect // "No effect reported"' 2>/dev/null || echo "No effect reported")

LOG_LINE="[$(date '+%Y-%m-%d %H:%M:%S')] SEEM $STATUS | Fidelity: $FIDELITY | $EFFECT"

echo "$LOG_LINE" >> "$HEALTH_LOG"

if [[ "$STATUS" == "SUCCESS" ]]; then
    # Normal operation - quiet log only
    true

elif [[ "$RESPONSE" == *"ALERT: SECURITY"* || "$RESPONSE" == *"CRITICAL"* ]]; then
    # Critical security or resource alert - escalate
    notify-send -u critical "SEEM SECURITY ALERT" "$EFFECT"
    curl -s -d "SEEM CRITICAL ALERT: $EFFECT (fidelity $FIDELITY)" "ntfy.sh/$NTFY_TOPIC" >/dev/null || true
    echo "$LOG_LINE – ALERT ESCALATED" >> "$HEALTH_LOG"

elif [[ "$FIDELITY" != "unknown" && $(echo "$FIDELITY < 0.96" | bc -l 2>/dev/null