from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)

# =========================
# HILFSFUNKTIONEN
# =========================

def get_calendar_events(entity_id):
    """Liefert die aktuellen Kalenderdaten als Liste"""
    event_list = []
    try:
        # Thread-sicheren Service-Call
        result = hass.services.call(
            'calendar',
            'get_events',
            {
                'entity_id': entity_id,
                'duration': {'hours': 24}
            },
            blocking=True,
            return_response=True
        )

        agenda = result[entity_id]
        events = agenda['events']

        anzahl_events = len(events)

        logger.error(f"typeofagenda: {type(events)} len: {len(events)} events: {events} kalender ID: {entity_id}")

    except Exception as e:
        hass.states.set('input_text.kalender_error', str(e))

    return events


def parse_iso(dt):
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def find_event(events, keyword, hours):
    """Sucht Termine mit Keyword innerhalb der nächsten X Stunden"""
    limit = now + timedelta(hours=hours)

    for event in events:

        start = parse_iso(event["start"])
        name = event.get("summary", "").lower()
        logger.warning(f"findevents: event: {event} | start: {start} |name: {name} | now: {now} | limit: {limit}"  )

        if keyword in name and now <= start <= limit:
            return True

    return False


def has_closed_event_today(events):
    """Prüft ob heute 'Gaststätte geschlossen' o.ä. existiert"""
    today = now.date()

    for event in events:
        start = parse_iso(event["start"]).date()
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
logger.error(f"gefundene events: {saal_events}")
if find_event(saal_events, "@saal", 3):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.saal_modus",
            "option": "Heizen"
        }
    )
    logger.warning("Modus Saal auf heizen gesetzt (3h)")


elif find_event(saal_events, "@saal", 10):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.saal_modus",
            "option": "Sparen"
        }
    )
    logger.warning("Modus Saal auf sparen gesetzt (10h)")

else:
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.saal_modus",
            "option": "Frostschutz"
        }
    )
    logger.warning("Modus Saal auf Frostschutz gesetzt (>10h)")


# =========================
# GASTSTUBE
# =========================

gast_heiz_events = get_calendar_events("calendar.heizkalender")
gast_oeffnung_events = get_calendar_events("calendar.schwanen_offnungszeiten")

# Prüfen ob heute geschlossen
geschlossen = has_closed_event_today(gast_heiz_events)
logger.info(f"Gaststube_has_closed: {geschlossen}")
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
    logger.warning("Modus Gaststube auf heizen gesetzt (3h)")

elif find_event(gast_events, "@gaststube", 10):
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.gaststube_modus",
            "option": "Sparen"
        }
    )
    logger.warning("Modus Gaststube auf sparen gesetzt (10h)")

else:
    hass.services.call(
        "input_select", "select_option",
        {
            "entity_id": "input_select.gaststube_modus",
            "option": "Frostschutz"
        }
    )
    logger.warning("Modus Gaststube auf Frostschutz gesetzt (>10h)")
