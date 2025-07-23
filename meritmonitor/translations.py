import os
from pathlib import Path

from meritmonitor.logger import get_logger

class Translations:

    languages = {}
    translations = {}

    def __init__(self, lang_dir: str):
        self.translations_dir = lang_dir
        self.languages = self.find_translation_files(lang_dir)

    def all_languages(self):
        return self.languages.keys()

    def load(self, language: str) -> None:
        self.translations = {
            "Prikaži izveštaj": "Prikaži izveštaj",
            "Webhook": "Webhook",
            "Učitaj ceo PP ciklus": "Učitaj ceo PP ciklus",
            "Webhook URL sačuvan.": "Webhook URL sačuvan.",
            "Podešavanje Discord Webhook-a": "Podešavanje Discord Webhook-a",
            "Sačuvaj": "Sačuvaj",
            "Pregled Discord izveštaja": "Pregled Discord izveštaja",
            "Pošalji na Discord": "Pošalji na Discord",
            "Otkaži": "Otkaži",
            "Sistemski meriti po sistemima:": "Sistemski meriti po sistemima:",
            "Jezik": "Jezik"
        }

        file_name = self.languages.get(language, "Srpski.conf")
        full_path = os.path.join(self.translations_dir, file_name)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            key, val = line.strip().split(":", 1)
                            self.translations[key.strip()] = val.strip()
            except Exception as e:
                get_logger().error(f"Greška pri učitavanju prevoda: {e}")

    def translate(self, text: str) -> str:
        return self.translations.get(text, text)

    def find_translation_files(self, directory: str):
        languages = {}
        for path in Path(directory).glob("*.conf"):
            lang = path.stem
            languages[lang] = path.name
        return languages
