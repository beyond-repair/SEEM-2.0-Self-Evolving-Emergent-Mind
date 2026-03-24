#!/usr/bin/env bash
# bootstrap.sh - SEEM Sovereign Agent One-Command Installer
# Usage: bash bootstrap.sh [--dry-run] [--no-daemon]

set -euo pipefail

DRY_RUN=false
NO_DAEMON=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)   DRY_RUN=true; shift ;;
        --no-daemon) NO_DAEMON=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "SEEM 2.0 Sovereign Agent Bootstrap (Genesis v1.0.0)"
echo "Date: $(date)"
echo "Dry run: $DRY_RUN"

# 1. Environment check
command -v python3 >/dev/null || { echo "Python3 required"; exit 1; }
command -v git >/dev/null     || { echo "git required"; exit 1; }
command -v jq >/dev/null      || { echo "jq required – installing..."; sudo apt-get update && sudo apt-get install -y jq; }

PY_VER=$(python3 -c 'import sys; print(sys.version_info.minor)')
(( PY_VER >= 10 )) || { echo "Python 3.10+ required"; exit 1; }

# 2. Clone or update repo
REPO_URL="https://github.com/beyond-repair/SEEM-2.0-Self-Evolving-Emergent-Mind.git"

if [[ ! -f "seem.py" ]]; then
    echo "Cloning SEEM repo..."
    $DRY_RUN || git clone "$REPO_URL" .
else
    echo "Repo already present. Pulling latest..."
    $DRY_RUN || git pull
fi

# 3. Install Python dependencies
echo "Installing Python dependencies..."
$DRY_RUN || pip3 install --user -r requirements.txt

# 4. Create config if missing
if [[ ! -f "config.json" ]]; then
    echo "Creating config.json template..."
    $DRY_RUN || cat > config.json <<'EOF'
{
  "api_key": "your-secure-vsa-key-123",
  "daemon_port": 5555,
  "cloud_remote": "dropbox:SEEM-backups",
  "rclone_path": "~/.config/rclone/rclone.conf"
}
EOF
    echo "→ IMPORTANT: Edit config.json with your real API key!"
fi

# 5. Setup systemd service (dynamic path)
INSTALL_DIR=$(pwd)
USER_NAME=$(whoami)
echo "Generating systemd unit file..."
$DRY_RUN || cat > /tmp/seem-agent.service <<EOF
[Unit]
Description=SEEM Sovereign Cognitive Microservice
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/seem.py daemon
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=5
User=$USER_NAME
Environment="API_KEY=$(jq -r .api_key config.json 2>/dev/null || echo 'your-secure-vsa-key-123')"
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

$DRY_RUN || sudo mv /tmp/seem-agent.service /etc/systemd/system/
$DRY_RUN || sudo systemctl daemon-reload

if ! $NO_DAEMON; then
    echo "Enabling & starting daemon..."
    $DRY_RUN || sudo systemctl enable --now seem-agent.service
fi

# 6. rclone check
if [[ ! -f "$HOME/.config/rclone/rclone.conf" ]]; then
    echo "rclone not configured yet."
    echo "Run: rclone config   (create remote matching config.json 'cloud_remote')"
else
    echo "rclone found. Latest backups:"
    $DRY_RUN || rclone ls "$(jq -r .cloud_remote config.json)"
fi

echo ""
echo "Genesis complete!"
echo ""
echo "Next steps:"
echo "  1. Edit config.json with your real API key"
echo "  2. Configure rclone if using cloud backup"
echo "  3. Run: python telegram_bot.py  (in another terminal)"
echo "  4. Text your bot: /start"
echo "  5. Create first twin: seem init brian_new"
echo "  6. (Optional) sudo systemctl status seem-agent.service"
