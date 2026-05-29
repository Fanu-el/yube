from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Bot, Update, BotCommand

from app.settings import settings
from app.services.telegram import handle_channel, handle_callback_query, handle_inline_query

app = FastAPI(title="yube Telegram bot")
bot = Bot(token=settings.telegram_token)


def build_webhook_target() -> str:
    if not settings.webhook_url:
        raise HTTPException(400, detail="WEBHOOK_URL is required to register a webhook")

    target = settings.webhook_url.strip()
    if target.endswith(settings.webhook_path):
        return target.rstrip("/")
    return f"{target.rstrip('/')}{settings.webhook_path}"


@app.post("/webhook")
async def telegram_webhook(request: Request) -> JSONResponse:
    payload = await request.json()
    update = Update.de_json(payload, bot)
    
    if update.message:
        await handle_channel(update)
    elif update.callback_query:
        await handle_callback_query(update)
    elif update.inline_query:
        await handle_inline_query(update)
    
    return JSONResponse({"ok": True})


@app.get("/set_commands")
async def set_commands() -> dict[str, str]:
    """Register bot commands with Telegram."""
    commands = [
        BotCommand("start", "Welcome message and how to use the bot"),
        BotCommand("help", "Show search methods and usage instructions"),
        BotCommand("about", "About yube bot"),
    ]
    result = await bot.set_my_commands(commands)
    if not result:
        raise HTTPException(500, detail="Failed to set bot commands")
    return {"status": "commands registered"}


@app.get("/set_webhook")
async def set_webhook() -> dict[str, str]:
    webhook_target = build_webhook_target()
    result = await bot.set_webhook(webhook_target)
    if not result:
        raise HTTPException(500, detail="Failed to register webhook")
    return {"webhook": webhook_target}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
