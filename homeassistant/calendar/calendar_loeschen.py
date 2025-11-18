import os

# Pfad zur lokalen ICS-Datei des Kalenders
ics_path = "/config/.storage/local_calendar.calendar_heizkalender.ics"
calendar_entity = "calendar.heizkalender"

def leere_ics_datei(pfad):
    # Überschreibe Datei mit leeren ICS-Grundgerüst
    try:
      with open(pfad, 'w') as f:
          f.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//homeassistant//NONSGML Calendar//EN\nEND:VCALENDAR\n")
    except Exception as e:
      logger.error(f"Fehler beim Schreiben: {e}")

def reload_calendar_via_restart(hass):
    async def do_restart():
        await hass.services.async_call("homeassistant", "restart")

    hass.loop.call_soon_threadsafe(
        hass.async_create_task,
        do_restart()
    )

# Datei löschen bzw. leeren

if os.path.isfile(ics_path):
    leere_ics_datei(ics_path)
    logger.warning(f"ICS-Datei {ics_path} geleert (alle Termine entfernt).")
else:
    logger.warning(f"ICS-Datei {ics_path} nicht gefunden.")

# reload calender
logger.warning(f"Versuche Kalender zu reloaden: {calendar_entity}")
# Danach reload thread-safe anstossen
#trigger_recorder_reload_threadsafe(hass)
reload_calendar_via_restart(hass);
logger.warning(f"Kalender {calendar_entity} neu geladen.")