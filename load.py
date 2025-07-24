import semantic_version
from meritmonitor.meritmonitor import MeritMonitor

PLUGIN_NAME = "MeritMonitor"
PLUGIN_VERSION = semantic_version.Version.coerce("1.0.0")

merit_monitor = MeritMonitor(PLUGIN_NAME, PLUGIN_VERSION)

def plugin_start3(plugin_dir: str):
    merit_monitor.plugin_start(plugin_dir)
    return PLUGIN_NAME

def plugin_app(parent):
    return merit_monitor.get_plugin_frame(parent)

def plugin_prefs(parent, cmdr, is_beta: bool):
    return merit_monitor.get_plugin_prefs_frame(parent, cmdr, is_beta)

def on_preferences_closed(cmdr, is_beta: bool):
    merit_monitor.on_preferences_closed(cmdr, is_beta)

def prefs_changed(cmdr, is_beta):
    return merit_monitor.on_preferences_closed(cmdr, is_beta)

def plugin_stop():
    merit_monitor.on_preferences_closed("", False)
    merit_monitor.shut_down()

def journal_entry(cmdr, is_beta, system, station, entry, state):
    return merit_monitor.journal_entry(cmdr, is_beta, system, station, entry, state)
