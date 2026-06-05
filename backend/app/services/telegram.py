import httpx

from app.config import get_settings


class TelegramNotifier:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def send(self, message: str) -> tuple[bool, str | None]:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return False, "Telegram bot token or chat id is not configured."
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": message,
            "disable_web_page_preview": False,
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            return True, None
        except Exception as exc:
            return False, str(exc)

