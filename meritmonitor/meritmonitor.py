import glob
import os
import json
from datetime import datetime, timezone, timedelta
import hashlib

from semantic_version import Version
import requests
import tkinter as tk
from tkinter import StringVar, Toplevel, PhotoImage, Text
import myNotebook as nb

from queue import Queue, Empty
from threading import Thread

from meritmonitor.settings import Settings
from meritmonitor.translations import Translations
from meritmonitor.database import Database

from meritmonitor.logger import get_logger, set_global_log_file


class MeritMonitor:
    webhook_entry = None
    settings = Settings({})
    lang_var = StringVar(value=settings.get_language())
    webhook_entry_var = StringVar(value=settings.get_webhook_url())

    state_table = {
        "Unoccupied": 1.00,
        "Exploited": 0.65,
        "Fortified": 0.65,
        "Stronghold": 0.65,
        "Controlled": 0.65
    }

    personal_total = 0
    live_personal_by_system = {}
    live_control_points_by_system = {}
    last_seen_system = "Nepoznato"
    last_seen_system_state = "Unoccupied"
    last_frame = None
    status_text = StringVar(value="Status: učitavanje...")
    plugin_dir = None
    logger = None
    translations = None
    db = None

    journal_queue: Queue = Queue()
    should_run: bool = True

    def __init__(self, plugin_name: str, version: Version) -> None:
        self.plugin_name: str = plugin_name
        self.version: Version = version

        self.worker_thread = Thread(target=self.worker, name='MeritMonitor worker')
        self.worker_thread.daemon = True

    def plugin_start(self, plugin_dir: str) -> None:
        self.plugin_dir = plugin_dir
        self.translations = Translations(os.path.join(plugin_dir, "lang"))
        self.init_files(plugin_dir)
        set_global_log_file(self.log_file)
        self.logger = get_logger()
        try:
            self.settings = Settings(self.load_settings())
            self.lang_var.set(self.settings.get_language())
            self.webhook_entry_var.set(self.settings.get_webhook_url())

            self.translations.load(self.settings.get_language())

            self.db = Database(os.path.join(plugin_dir, "merits.db"))

            self.logger.info("Pokrećem I/O nit")
            try:
                self.worker_thread.start()
            except RuntimeError as re:
                self.logger.critical(f"Greška pri pokretanju I/O niti: {re}")

            self.logger.info("Plugin MeritMonitor pokrenut")
        except Exception as e:
            self.logger.error(f"Greška pri pokretanju plugina: {e}")

    def init_files(self, plugin_dir: str) -> None:
        self.log_file = os.path.join(plugin_dir, "meritmonitor.log")
        self.settings_file = os.path.join(plugin_dir, "settings.json")
        self.report_data_file = os.path.join(plugin_dir, "report_data.json")
        self.lang_file = os.path.join(plugin_dir, "language.conf")

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump({"webhook_url": ""}, f, indent=2)
        with open(self.settings_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_settings(self, data):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_previous_report_data(self):
        if os.path.exists(self.report_data_file):
            with open(self.report_data_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_current_report_data(self, data):
        with open(self.report_data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_journal_dir(self):
        user_dir = os.environ.get('USERPROFILE')
        return os.path.join(user_dir, "Saved Games", "Frontier Developments", "Elite Dangerous")

    def get_last_thursday(self):
        now = datetime.utcnow()
        thursday = now - timedelta(days=(now.weekday() + 4) % 7)
        thursday = thursday.replace(hour=7, minute=0, second=0, microsecond=0)
        return thursday

    def load_merits_since(self, timestamp):
        self.live_personal_by_system = {}
        self.live_control_points_by_system = {}
        journal_dir = self.get_journal_dir()

        for filename in sorted(glob.glob(os.path.join(journal_dir, "Journal.*.log*"))):
            try:
                if filename.endswith('.lnk'):
                    continue
                with open(filename, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            ts = datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
                            if ts < timestamp:
                                continue
                            self.process_journal_entry(entry, None)
                        except Exception as e:
                            self.logger.error(f"Greška u liniji fajla {filename}: {e}")
            except Exception as e:
                self.logger.error(f"Greška pri otvaranju fajla {filename}: {e}")
        self.update_live_status()

    def load_today_merits(self):
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        self.load_merits_since(today)

    def load_full_pp_cycle(self):
        thursday = self.get_last_thursday()
        self.load_merits_since(thursday)

    def process_journal_entry(self, entry, system=None):
        event = entry.get("event")
        if event in ["FSDJump", "Location"]:
            self.last_seen_system = entry.get("StarSystem", self.last_seen_system or "Nepoznato")
            self.last_seen_system_state = entry.get("PowerplayState", self.last_seen_system_state)
        elif event in ["PowerplayMerits"]:
            net_merits_gained = entry.get("MeritsGained") or 0
            multiplier = self.state_table.get(self.last_seen_system_state, 1.0)

            gross_merits_gained = round(net_merits_gained / multiplier)
            system_control_points_gained = round(gross_merits_gained * 0.25)

            self.live_personal_by_system[self.last_seen_system] = self.live_personal_by_system.get(self.last_seen_system, 0) + net_merits_gained
            self.live_control_points_by_system[self.last_seen_system] = self.live_control_points_by_system.get(self.last_seen_system, 0) + system_control_points_gained
            self.logger.info(f"Dodato: {net_merits_gained} merita za {self.last_seen_system} ({self.last_seen_system_state})")

    def journal_entry(self, cmdr, is_beta, system, station, entry, state):
        self.journal_queue.put((system, entry))
        self.update_live_status()

    def get_plugin_frame(self, parent):
        frame = tk.Frame(parent)
        self.last_frame = frame
        return self.populate_plugin_frame(frame)

    def populate_plugin_frame(self, frame):
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=5)
        tk.Button(button_frame, text=self.translations.translate("Prikaži izveštaj"), compound="left",
                   command=self.show_preview_modal).pack(side="left", padx=5)
        #tk.Button(button_frame, text=self.translations.translate("Učitaj ceo PP ciklus"), compound="left",
#                   command=self.load_full_pp_cycle).pack(side="left", padx=5)

        tk.Label(frame, textvariable=self.status_text).pack()

        self.update_live_status()
        return frame

    def get_plugin_prefs_frame(self, parent, cmdr, is_beta):
        frame = nb.Frame(parent)

        current_row = 0
        nb.Label(frame, text=self.translations.translate("Jezik") + ": ").grid(row=current_row, sticky="w")
        lang_menu = nb.OptionMenu(frame, self.lang_var, self.settings.get_language(), *self.translations.all_languages(),
                                  command=lambda _: self.refresh_gui())
        lang_menu.grid(row=current_row, column=1, sticky="w")

        current_row += 1
        nb.Label(frame, text=self.translations.translate("Webhook") + ": ").grid(row=current_row, sticky="w")
        self.webhook_entry_var.trace_add("write", self.on_webhook_entry_change)
        self.webhook_entry = nb.Entry(frame, width=40, textvariable=self.webhook_entry_var)
        self.webhook_entry.grid(row=current_row, column=1)

        return frame

    def on_webhook_entry_change(self, *args):
        self.settings.set_webhook_url(self.webhook_entry_var.get())

    def on_preferences_closed(self, cmdr, is_beta):
        self.settings.set_language(self.lang_var.get())
        self.settings.set_webhook_url(self.webhook_entry_var.get())
        self.save_settings(self.settings.as_dict())

    def refresh_gui(self):
        self.translations.load(self.lang_var.get())
        if self.last_frame:
            for widget in self.last_frame.winfo_children():
                widget.destroy()
            self.populate_plugin_frame(self.last_frame)

    def update_live_status(self):
        total_p = sum(self.live_personal_by_system.values())
        total_s = sum(self.live_control_points_by_system.values())
        self.status_text.set(f"Uživo: {int(total_p)} ličnih / {int(total_s)} sistemskih merita.")

    def show_preview_modal(self):
        text = self.generate_report_text()

        win = Toplevel()
        win.title(self.translations.translate("Pregled Discord izveštaja"))
        win.geometry("500x500")
        txt = Text(win, wrap="word", height=15)
        txt.insert("1.0", text)
        txt.config(state="disabled")
        txt.pack(padx=10, pady=10, fill="both", expand=True)

        def send_now():
            self.post_to_discord(text)
            win.destroy()

        tk.Button(win, text=self.translations.translate("Pošalji na Discord"), command=send_now).pack(side="left", padx=10, pady=5)
        tk.Button(win, text=self.translations.translate("Otkaži"), command=win.destroy).pack(side="right", padx=10, pady=5)

    def generate_report_text(self) -> str:
        text = f"📊 **{self.translations.translate('Sistemski meriti po sistemima:')}**\n\n"
        for system in sorted(self.live_control_points_by_system):
            s = int(self.live_control_points_by_system[system])
            text += f"- `{system}`: **{s}**\n"
        return text

    def hash_message(self, text: str) -> str:
        h = hashlib.new('sha256')
        byte_array = text.encode('utf-8')
        h.update(byte_array)
        return h.hexdigest()

    def post_to_discord(self, text: str):
        webhook_url = self.settings.get_webhook_url()
        if not webhook_url:
            self.status_text.set(self.translations.translate("Webhook URL nije podešen."))
            return

        thursday = self.get_last_thursday()
        timestamp = int(thursday.timestamp())

        message_hash = self.hash_message(text)

        message_id, existing_message_hash = self.db.lookup_discord_message(timestamp)

        payload = {"content": text}
        headers = {'Content-Type': 'application/json'}

        try:
            if message_id:
                self.logger.info("Našao prethodnu Discord poruku u bazi.")
                if existing_message_hash == message_hash:
                    self.logger.info("Nema promena od poslednje Discord poruke.")
                    return
                else:
                    self.logger.info("Аžuriram prethodnu Discord poruku.")
                    url = f"{webhook_url}/messages/{message_id}"
                    response = requests.patch(url, json=payload, headers=headers)
            else:
                self.logger.info("Šaljem novu Discord poruku")
                response = requests.post(f"{webhook_url}?wait=true", json=payload, headers=headers)
            response.raise_for_status()

        except requests.RequestException as e:
            error_message = self.translations.translate("Greška pri slanju:")
            self.status_text.set(f"{error_message} {e}")

        self.logger.info(response)
        res_json = response.json()
        new_message_id = res_json.get("id")
        self.db.upsert_discord_message(timestamp, new_message_id, message_hash)
        status_text = "Discord poruka ažurirana." if message_id else "Uspešno poslato na Discord."
        self.status_text.set(self.translations.translate(status_text))

    def shut_down(self):
        self.should_run = False
        self.worker_thread.join()

    def worker(self):
        self.logger.info("Učitavam poslednji PP ciklus ...")
        self.status_text.set("Učitavam poslednji PP ciklus ...")
        self.load_full_pp_cycle()
        self.logger.info("Poslednji PP ciklus učitan.")
        self.status_text.set("Poslednji PP ciklus učitan.")
        while self.should_run:
            entry = None
            system = None

            try:
                system, entry = self.journal_queue.get(block=True, timeout=5)
            except Empty:
                pass

            if entry:
                try:
                    self.process_journal_entry(entry, system)
                except Exception as e:
                    self.logger.error(f"Greška u journal_entry: {e}")

            self.update_live_status()
