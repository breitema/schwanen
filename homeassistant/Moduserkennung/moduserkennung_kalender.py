from datetime import datetime, timedelta
from dateutil.parser import isoparse

now = datetime.now()

# =========================
# HILFSFUNKTIONEN
# =========================

def get_calendar_events(entity_id):
    """Liefert die aktuellen Kalenderdaten als Liste"""
    state = hass.states.get(entity_id)
    if not state:
        return []

    events = state.attributes.get("events")
    if events:
        return events

    # Fallback für Einzeltermine
    start = state.attributes.get("start_time")
    message = state.attributes.get("message")
    if start and message:
        return [{
            "start": start,
            "message": message
        }]

    return []


def find_event(events, keyword, hours):
    """Sucht Termine mit Keyword innerhalb der nächsten X Stunden"""
    limit = now + timedelta(hours=hours)

    for event in events:
        start = isoparse(event["start"])
        name = event.get("message", "").lower()

        if keyword in name and now <= start <= limit:
            return True

    return False


def has_closed_event_today(events):
    """Prüft ob heute 'Gaststätte geschlossen' o.ä. existiert"""
    today = now.date()

    for event in events:
        start = isoparse(event["start"]).date()
        name = event.get("message", "").lower()

        if start == today and (
            "gaststätte geschlossen" in name or
            "gaststube geschlossen" in name
        ):
            return True

    return False


# =========================
# SAAL
# =========================

saal_events = get_calendar_events("calendar.heizkalender")

if find_event(saal_events, "@saal", 3):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.saal_modus",
            "option": "Heizen"
        }
    )

elif find_event(saal_events, "@saal", 10):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.saal_modus",
            "option": "Sparen"
        }
    )

else:
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.saal_modus",
            "option": "Frostschutz"
        }
    )


# =========================
# GASTSTUBE
# =========================

gast_heiz_events = get_calendar_events("calendar.heizkalender")
gast_oeffnung_events = get_calendar_events("calendar.schwanen_offnungszeiten")

# Prüfen ob heute geschlossen
geschlossen = has_closed_event_today(gast_heiz_events)

# Wenn geschlossen → Öffnungszeiten ignorieren
if geschlossen:
    gast_events = gast_heiz_events
else:
    gast_events = gast_heiz_events + gast_oeffnung_events


if find_event(gast_events, "@gaststube", 3):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.gaststube_modus",
            "option": "Heizen"
        }
    )

elif find_event(gast_events, "@gaststube", 10):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.gaststube_modus",
            "option": "Sparen"
        }
    )

else:
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.gaststube_modus",
            "option": "Frostschutz"
        }
    )
