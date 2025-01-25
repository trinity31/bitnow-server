import aiohttp
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


class SlackService:
    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    async def send_message(self, message: str):
        if not self.webhook_url:
            return

        payload = {"text": message}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status != 200:
                        print(f"Failed to send Slack message: {await response.text()}")
            except Exception as e:
                print(f"Error sending Slack message: {str(e)}")
