from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import socket
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
YOUR_TELEGRAM_ID = int(os.getenv("YOUR_TELEGRAM_ID", "123456789"))

API_KEY = os.getenv("SEEM_API_KEY", "your-secure-vsa-key-123")
DAEMON_HOST = os.getenv("DAEMON_HOST", "localhost")
DAEMON_PORT = int(os.getenv("DAEMON_PORT", "5555"))

ACTIVE_TWIN = "brian_new"


def _send_daemon_request(payload: dict) -> dict:
    payload["auth_token"] = API_KEY
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((DAEMON_HOST, DAEMON_PORT))
            s.sendall(json.dumps(payload).encode())
            resp = json.loads(s.recv(4096).decode())
        return resp
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(
        "SEEM Agent Online\n\n"
        "/status - Twin status\n"
        "/dream - Trigger dream phase\n"
        "/suppress - View suppressed routes\n"
        "/do <intent> - Execute mission\n"
        "/switch <name> - Switch twin\n"
        "/failures - Recent failures"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    request = {"intent": "status_check", "twin": ACTIVE_TWIN}
    resp = _send_daemon_request(request)

    if resp.get("status") == "SUCCESS":
        msg = (
            f"Twin: {resp.get('twin')}\n"
            f"Status: {resp.get('status')}\n"
            f"Fidelity: {resp.get('fidelity', 'N/A'):.4f}\n"
            f"Effect: {resp.get('effect', 'N/A')}"
        )
    else:
        msg = f"Error: {resp.get('message', 'Unknown error')}"

    await update.message.reply_text(msg)


async def dream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text("Initiating dream phase...")

    request = {"intent": "trigger_dream", "twin": ACTIVE_TWIN}
    resp = _send_daemon_request(request)

    if resp.get("status") == "SUCCESS":
        dream_info = resp.get("dream_summary", {})
        msg = (
            f"Dream Phase Complete\n\n"
            f"Total Dreams: {dream_info.get('total_dreams', 0)}\n"
            f"Micro Dreams: {dream_info.get('micro_dreams', 0)}\n"
            f"Batch Dreams: {dream_info.get('batch_dreams', 0)}\n"
            f"Total Improvement: {dream_info.get('total_improvement', 0):.4f}\n"
            f"Routes Evolved: {dream_info.get('routes_evolved', 0)}"
        )
    else:
        msg = f"Dream failed: {resp.get('message', 'Unknown error')}"

    await update.message.reply_text(msg)


async def suppress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    request = {"intent": "list_suppressed", "twin": ACTIVE_TWIN}
    resp = _send_daemon_request(request)

    if resp.get("status") == "SUCCESS":
        suppressed = resp.get("suppressed_routes", [])
        if not suppressed:
            msg = "No suppressed routes."
        else:
            msg = "Suppressed Routes:\n" + "\n".join(suppressed[:10])
    else:
        msg = f"Error: {resp.get('message', 'Unknown error')}"

    await update.message.reply_text(msg)


async def do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /do <intent>")
        return

    intent = " ".join(context.args)
    await update.message.reply_text(f"Executing: {intent}")

    request = {"intent": intent, "twin": ACTIVE_TWIN}
    resp = _send_daemon_request(request)

    if resp.get("status") == "SUCCESS":
        msg = (
            f"Mission Result:\n"
            f"Fidelity: {resp.get('fidelity', 'N/A'):.4f}\n"
            f"Effect: {resp.get('effect', 'N/A')}"
        )
    else:
        msg = f"Mission failed: {resp.get('message', 'Unknown error')}"

    await update.message.reply_text(msg)


async def switch_twin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /switch <twin_name>")
        return

    global ACTIVE_TWIN
    ACTIVE_TWIN = context.args[0]
    await update.message.reply_text(f"Switched to twin: {ACTIVE_TWIN}")


async def failures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return

    request = {"intent": "get_failures", "twin": ACTIVE_TWIN}
    resp = _send_daemon_request(request)

    if resp.get("status") == "SUCCESS":
        failure_summary = resp.get("failure_summary", {})
        if not failure_summary:
            msg = "No recent failures."
        else:
            lines = []
            for route_id, info in list(failure_summary.items())[:5]:
                lines.append(
                    f"{route_id}: {info.get('count', 0)} failures, "
                    f"avg_score={info.get('avg_score', 0):.3f}"
                )
            msg = "Recent Failures:\n" + "\n".join(lines)
    else:
        msg = f"Error: {resp.get('message', 'Unknown error')}"

    await update.message.reply_text(msg)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("dream", dream))
    app.add_handler(CommandHandler("suppress", suppress))
    app.add_handler(CommandHandler("do", do))
    app.add_handler(CommandHandler("switch", switch_twin))
    app.add_handler(CommandHandler("failures", failures))

    logger.info("SEEM Telegram Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()