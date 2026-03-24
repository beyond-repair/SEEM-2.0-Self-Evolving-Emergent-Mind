import subprocess

def execute(fidelity, mission_context=None):
    if fidelity < 0.96:
        return "FAILURE: Insufficient symbolic clarity for SOC check."

    reports = []

    # Disk check
    try:
        disk_usage = subprocess.getoutput("df / | tail -1 | awk '{print $5}'").strip('%')
        if int(disk_usage) > 90:
            reports.append(f"DISK CRITICAL: {disk_usage}% full")
    except:
        pass

    # Failed logins check
    try:
        failed = subprocess.getoutput("journalctl _SYSTEMD_UNIT=sshd.service --since '1 hour ago' | grep -i 'failed' | wc -l")
        if int(failed) > 0:
            reports.append(f"SECURITY: {failed} failed SSH attempts detected")
    except:
        pass

    if not reports:
        return "SUCCESS: Resources and Security nominal."

    return "ALERT: " + " | ".join(reports)