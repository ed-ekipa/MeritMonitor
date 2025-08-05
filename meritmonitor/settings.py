import json
import os


def load_settings(file: str) -> dict[str, str]:
    if not os.path.exists(file):
        return {}
    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


class Settings:
    language = "Srpski"
    webhook_url = ""

    def __init__(self, file: str) -> None:
        settings = load_settings(file)
        if "language" in settings:
            self.set_language(settings["language"])
        if "webhook_url" in settings:
            self.set_webhook_url(settings["webhook_url"])

    def get_language(self) -> str:
        return self.language

    def set_language(self, language: str) -> None:
        self.language = language

    def get_webhook_url(self) -> str:
        return self.webhook_url

    def set_webhook_url(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def as_dict(self) -> dict[str, str]:
        return {
            "language": self.language,
            "webhook_url": self.webhook_url
        }

    def save_settings(self, file: str):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(self.as_dict(), f, indent=2)
