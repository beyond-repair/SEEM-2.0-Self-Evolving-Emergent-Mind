#!/usr/bin/env bash
# bootstrap.sh - SEEM Sovereign Agent One-Command Installer
# Run: bash bootstrap.sh [--dry-run] [--no-daemon]

set -euo pipefail

DRY_RUN=false
NO_DAEMON=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --no-daemon) NO_DAEMON=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "SEEM Sovereign Agent Bootstrap (Genesis)"
echo "Date: $(date)"
echo "Dry run: $DRY_RUN"

# 1. Environment check
command -v python3 >/dev/null || { echo "Python3 required"; exit 1; }
command -v git >/dev/null || { echo "git required"; exit 1; }

PY_VER=$(python3 -c 'import sys; print(sys.version_info.minor)')
(( PY_VER >= 10 )) || { echo "Python 3.10+ required"; exit 1; }

# 2. Clone or update repo (if not already here)
if [[ ! -f "seem.py" ]]; then
    echo "Cloning SEEM repo..."
    $DRY_RUN || git clone https://github.com/beyond-repair/SEEM-2.0-Self-Evolving-Emergent-Mind.git .
fi

# 3. Install dependencies
echo "Installing Python deps..."
$DRY_RUN || pip3 install --user torch numpy python-telegram-bot requests rclone

# 4. Create config if missing
if [[ ! -f "config.json" ]]; then
    echo "Creating config.json template..."
    $DRY_RUN || cat > config.json <<EOF
{
  "api_key": "your-secure-vsa-key-123",
  "daemon_port": 5555,
  "cloud_remote": "dropbox:SEEM-backups",
  "rclone_path": "~/.config/rclone/rclone.conf"
}
EOF
    echo "→ Edit config.json with your API key and cloud remote!"
fi

# 5. Setup systemd service
echo "Generating systemd unit..."
$DRY_RUN || cat > /tmp/seem-agent.service <<EOF
[Unit]
Description=SEEM Sovereign Cognitive Microservice
After=network.target

[Service]
ExecStart=/usr/bin/python3 $(pwd)/seem.py daemon
WorkingDirectory=$(pwd)
Restart=always
User=$(whoami)
Environment="API_KEY=$(jq -r .api_key config.json)"

[Install]
WantedBy=multi-user.target
EOF

$DRY_RUN || sudo mv /tmp/seem-agent.service /etc/systemd/system/
$DRY_RUN || sudo systemctl daemon-reload

if ! $NO_DAEMON; then
    echo "Enabling & starting daemon..."
    $DRY_RUN || sudo systemctl enable --now seem-agent.service
fi

# 6. Pull latest backup (optional)
echo "Checking for cloud sync..."
if [[ -f "$HOME/.config/rclone/rclone.conf" ]]; then
    $DRY_RUN || rclone ls $(jq -r .cloud_remote config.json)
    echo "To restore latest: python seem.py sync --latest"
else
    echo "rclone not configured. Run: rclone config"
fi

echo "Genesis complete!"
echo "Next steps:"
echo "  1. Edit config.json with your real API key"
echo "  2. Run: python telegram_bot.py (in another terminal)"
echo "  3. Text your bot: /start"
echo "  4. Enjoy your sovereign twin."
