import glob
import os
import json
from datetime import datetime, timedelta
import hashlib
from time import sleep

from queue import Queue, Empty
from threading import Thread, Event

import tkinter as tk
from tkinter import StringVar, Toplevel, Text

import requests
import myNotebook as nb
from semantic_version import Version

from config import get_config # from EDMC

from meritmonitor.meritcalculator import control_points_from_merits_gained
from meritmonitor.meritstore import MeritStore
from meritmonitor.settings import Settings
from meritmonitor.translations import Translations
from meritmonitor.database import Database
from meritmonitor.thursday import get_last_thursday
from meritmonitor.logger import get_logger, set_global_log_file


class MeritMonitor:
    webhook_entry = None
    settings = Settings("")
    lang_var = StringVar(value=settings.get_language())
    webhook_entry_var = StringVar(value=settings.get_webhook_url())

    personal_total = 0
    merit_store = MeritStore()
    last_seen_system = "Nepoznato"
    last_seen_system_state = "Unoccupied"
    last_frame = None
    status_text = StringVar(value="Status: učitavanje...")
    plugin_dir = None
    logger = None
    translations = None
    db = None
    root = None
    last_discord_update = datetime.now()
    notified_of_missing_webhook = False

    def __init__(self, plugin_name: str, version: Version) -> None:
        self.plugin_name: str = plugin_name
        self.version: Version = version

        self.journal_queue: Queue = Queue()
        self.should_run: Event = Event()
        self.should_run.set()
        self.worker_thread = Thread(target=self.worker, name='MeritMonitor worker')
        self.worker_thread.daemon = True

    def plugin_start(self, plugin_dir: str) -> None:
        self.plugin_dir = plugin_dir
        self.translations = Translations(os.path.join(plugin_dir, "lang"))
        self.init_files(plugin_dir)
        set_global_log_file(self.log_file)
        self.logger = get_logger()
        try:
            self.settings = Settings(self.settings_file)
            self.lang_var.set(self.settings.get_language())
            self.webhook_entry_var.set(self.settings.get_webhook_url())

            self.translations.load(self.settings.get_language())

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

    def get_journal_dir(self) -> str:
        self.logger.info("Trying to get custom journal directory from EDMC")
        journal_dir = ""
        try:
            journal_dir = get_config().get_str("journaldir")
            if journal_dir is None or journal_dir == "":
                self.logger.info("Trying to get default journal directory from EDMC")
                journal_dir = get_config().default_journal_dir
        except Exception as e:
            self.logger.error(f"exception getting journal_dir: {repr(e)} [{e}]")

        if isinstance(journal_dir, str) and os.path.isdir(journal_dir):
            self.logger.info(f"Using EDMC journal directory: {journal_dir}")
        else:
            user_dir = os.environ.get('USERPROFILE')
            if user_dir is None:
                self.logger.critical("Unable to find journal directory!")
                return ""
            journal_dir = os.path.join(user_dir, "Saved Games", "Frontier Developments", "Elite Dangerous")
            self.logger.info(f"Falling back to default journal directory: {journal_dir}")
        return journal_dir

    def load_merits_since(self, timestamp):
        self.merit_store = MeritStore()
        journal_dir = os.path.expanduser(self.get_journal_dir())

        for filename in sorted(glob.glob(os.path.join(journal_dir, "Journal.*.log"))):
            try:
                if filename.endswith('.lnk'):
                    continue
                mtime = datetime.utcfromtimestamp(os.path.getmtime(filename))
                if mtime < timestamp:
                    continue
                #self.logger.info(f"Processing journal: {filename}")
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
        thursday = get_last_thursday()
        self.load_merits_since(thursday)

    def process_journal_entry(self, entry, system=None):
        event = entry.get("event")
        if event in ["FSDJump", "Location"]:
            self.last_seen_system = entry.get("StarSystem", self.last_seen_system or "Nepoznato")
            self.last_seen_system_state = entry.get("PowerplayState", self.last_seen_system_state)
        elif event in ["PowerplayMerits"]:
            net_merits_gained = entry.get("MeritsGained") or 0

            system_control_points_gained = control_points_from_merits_gained(self.last_seen_system_state, net_merits_gained)

            self.merit_store.add_personal(self.last_seen_system, net_merits_gained)
            self.merit_store.add_control_points(self.last_seen_system, system_control_points_gained)
            self.logger.info(f"Dodato: {net_merits_gained} merita za {self.last_seen_system} ({self.last_seen_system_state})")

    def journal_entry(self, cmdr, is_beta, system, station, entry, state):
        self.journal_queue.put((system, entry))

    def get_plugin_frame(self, parent):
        self.root = parent.winfo_toplevel()
        frame = tk.Frame(parent)
        self.last_frame = frame
        return self.populate_plugin_frame(frame)

    def populate_plugin_frame(self, frame):
        logo_path = os.path.join(self.plugin_dir, "logo.png")
        logo = tk.PhotoImage(file=logo_path)
        logo_label = tk.Label(frame, image=logo)
        logo_label.pack()
        logo_label.image = logo

        button_frame = tk.Frame(frame)
        button_frame.pack(pady=5)
        tk.Button(button_frame, text=self.translations.translate("Prikaži izveštaj"), compound="left",
                   command=self.show_preview_modal).pack(side="left", padx=5)

        tk.Label(frame, textvariable=self.status_text).pack()

        horizontal_rule = tk.Frame(frame, height=1, bd=0, bg="grey")
        horizontal_rule.pack(fill="x", padx=0, pady=10)

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
        self.notified_of_missing_webhook = False

    def on_preferences_closed(self, cmdr, is_beta):
        self.settings.set_language(self.lang_var.get())
        self.on_webhook_entry_change()
        self.settings.save_settings(self.settings_file)

    def refresh_gui(self):
        self.translations.load(self.lang_var.get())
        if self.last_frame:
            for widget in self.last_frame.winfo_children():
                widget.destroy()
            self.populate_plugin_frame(self.last_frame)

    def update_live_status(self):
        total_p = self.merit_store.sum_personal()
        total_s = self.merit_store.sum_system()
        live = self.translations.translate("Uživo")
        merits = self.translations.translate("ličnih")
        control_points = self.translations.translate("sistemskih merita")
        self.set_status_text(f"{live}: {total_p} {merits} / {total_s} {control_points}.")

    def show_preview_modal(self):
        text = self.generate_report_text()
        win = Toplevel()
        win.title(self.translations.translate("Pregled Discord izveštaja"))
        win.geometry("500x500")
        txt = Text(win, wrap="word", height=15)
        txt.insert("1.0", text)
        txt.config(state="disabled")
        txt.pack(padx=10, pady=10, fill="both", expand=True)
        tk.Button(win, text=self.translations.translate("Otkaži"), command=win.destroy).pack(side="right", padx=10, pady=5)

    def generate_report_text(self) -> str:
        text = f"📊 **{self.translations.translate('Sistemski meriti po sistemima:')}**\n\n"
        text += self.merit_store.get_control_points_by_system_report()
        return text

    def hash_message(self, text: str) -> str:
        h = hashlib.new('sha256')
        byte_array = text.encode('utf-8')
        h.update(byte_array)
        return h.hexdigest()

    def post_to_discord(self, text: str):
        webhook_url = self.settings.get_webhook_url()
        if not webhook_url and not self.notified_of_missing_webhook:
            self.set_status_text(self.translations.translate("Webhook URL nije podešen."))
            self.notified_of_missing_webhook = True
            return

        thursday = get_last_thursday()
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
            self.set_status_text(f"{error_message} {e}")

        self.logger.info(response)
        res_json = response.json()
        new_message_id = res_json.get("id")
        self.db.upsert_discord_message(timestamp, new_message_id, message_hash)
        status_text = "Discord poruka ažurirana." if message_id else "Uspešno poslato na Discord."
        self.set_status_text(self.translations.translate(status_text))

    def shut_down(self):
        self.should_run.clear()
        self.worker_thread.join(timeout=10)

    def worker(self):
        self.logger.info("Inicijalizujem sqlite3 ...")
        self.db = Database(os.path.join(self.plugin_dir, "merits.db"))
        self.logger.info("Učitavam poslednji PP ciklus ...")
        self.set_status_text("Učitavam poslednji PP ciklus ...")
        self.load_full_pp_cycle()
        self.logger.info("Poslednji PP ciklus učitan.")
        self.set_status_text("Poslednji PP ciklus učitan.")
        self.background_discord_update()
        self.logger.info("Glavna petlja I/O niti")
        while self.should_run.is_set():
            entry = None
            system = None

            try:
                system, entry = self.journal_queue.get(block=True, timeout=2)
            except Empty:
                pass

            if entry:
                try:
                    self.process_journal_entry(entry, system)
                    self.update_live_status()
                    self.background_discord_update()
                except Exception as e:
                    self.logger.error(f"Greška u journal_entry: {e}")

    def set_status_text(self, new_text: str):
        def update():
            self.status_text.set(new_text)
        if not self.root:
            self.logger.warning(f"No root widget: {new_text}")
            return
        self.root.after(0, update)

    def delay_discord_update(self):
        delay_seconds = 1
        if datetime.now() - self.last_discord_update >= timedelta(seconds=delay_seconds):
            sleep(delay_seconds)

    def background_discord_update(self):
        if self.merit_store.sum_system() == 0:
            self.logger.info("Nothing to send to Discord")
            return
        self.logger.info("Discord update")
        self.delay_discord_update()
        discord_message = self.generate_report_text()
        self.post_to_discord(discord_message)
