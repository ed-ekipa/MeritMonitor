class Settings:
    language = "Srpski"
    webhook_url = ""

    def __init__(self, settings: dict) -> None:
        if "language" in settings:
            self.set_language(settings["language"])
        if "webhook_url" in settings:
            self.set_webhook_url(settings["webhook_url"])

    def get_language(self) -> str:
        return self.language

    def get_webhook_url(self) -> str:
        return self.webhook_url

    def set_language(self, language: str) -> None:
        self.language = language

    def set_webhook_url(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "webhook_url": self.webhook_url
        }
