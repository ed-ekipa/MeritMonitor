import os
import json
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
        self.translations = {}

        file_name = self.languages.get(language, "Srpski.json")
        full_path = os.path.join(self.translations_dir, file_name)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
            except Exception as e:
                get_logger().error(f"Greška pri učitavanju prevoda: {e}")

    def translate(self, text: str) -> str:
        return self.translations.get(text, text)

    def find_translation_files(self, directory: str):
        languages = {}
        for path in Path(directory).glob("*.json"):
            lang = path.stem
            languages[lang] = path.name
        return languages
