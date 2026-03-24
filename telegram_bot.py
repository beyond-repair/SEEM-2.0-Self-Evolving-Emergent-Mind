from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import socket
import json

YOUR_TELEGRAM_ID = 123456789   # ← CHANGE TO YOUR ACTUAL TELEGRAM USER ID
API_KEY = "your-secure-vsa-key-123"
DAEMON_HOST = "localhost"
DAEMON_PORT = 5555

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != YOUR_TELEGRAM_ID:
        await update.message.reply_text("Unauthorized.")
        return
    request = {"auth_token": API_KEY, "intent": "status_check", "twin": "new_twin"}
    try:
        with socket.socket() as s:
            s.connect((DAEMON_HOST, DAEMON_PORT))
            s.sendall(json.dumps(request).encode())
            resp = json.loads(s.recv(1024).decode())
        await update.message.reply_text(f"🛡️ Status:\nFidelity: {resp.get('fidelity', 'N/A')}\nTwin: {resp.get('twin')}")
    except Exception as e:
        await update.message.reply_text(f"Daemon error: {str(e)}")

def main():
    app = Application.builder().token("YOUR_BOT_TOKEN_HERE").build()
    app.add_handler(CommandHandler("status", status))
    # Add more handlers as needed: /patrol, /alerts, voice handler, etc.
    app.run_polling()

if __name__ == "__main__":
    main()