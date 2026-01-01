from datetime import datetime, timedelta, timezone



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
                'start_date_time': (now - timedelta(hours=24)).isoformat(),  # 24h zurück
                'end_date_time': (now + timedelta(hours=24)).isoformat()     # 24h vorwärts
            },
            blocking=True,
            return_response=True
        )

        agenda = result[entity_id]
        events = agenda['events']

        anzahl_events = len(events)

        logger.info(f"typeofagenda: {type(events)} len: {len(events)} events: {events} kalender ID: {entity_id}")

    except Exception as e:
        hass.states.set('input_text.kalender_error', str(e))

    return events


def parse_iso(dt):
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def event_currently_active(events, keyword):

    for event in events:

        start = parse_iso(event["start"])
        end = parse_iso(event["end"])
        name = event.get("summary", "").lower()
        logger.info(f"currently active: event: {event} | keyword: {keyword} |start: {start} |end: {end} |name: {name} | now: {now}"  )

        if keyword in name and start <= now <= end:
            return True

    return False


def find_event(events, keyword, hours):
    """Sucht Termine mit Keyword innerhalb der nächsten X Stunden"""
    limit = now + timedelta(hours=hours)

    for event in events:

        start = parse_iso(event["start"])
        name = event.get("summary", "").lower()
        logger.info(f"findevents: event: {event} | keyword: {keyword} |start: {start} |name: {name} | now: {now} | limit: {limit}"  )

        if keyword in name and now <= start <= limit:
            return True

    return False


# =========================
# SAAL
# =========================
def moduserkennung_saal():

    saal_events = get_calendar_events("calendar.heizkalender")
    logger.info(f"moduserkennung_saal gefundene events: {saal_events}")

    if event_currently_active(saal_events, "@saal") :
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.saal_modus",
                "option": "Heizen"
            }
        )
        logger.info("Modus Saal auf heizen gesetzt (aktiver Termin)")

    elif find_event(saal_events, "@saal", 3) :
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.saal_modus",
                "option": "Heizen"
            }
        )
        logger.info("Modus Saal auf heizen gesetzt (3h)")


    elif find_event(saal_events, "@saal", 10):
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.saal_modus",
                "option": "Sparen"
            }
        )
        logger.info("Modus Saal auf sparen gesetzt (10h)")

    else:
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.saal_modus",
                "option": "Frostschutz"
            }
        )
        logger.info("Modus Saal auf Frostschutz gesetzt (>10h)")
    return

# =========================
# GASTSTUBE
# =========================
def moduserkennung_gaststube():

    gast_heiz_events = get_calendar_events("calendar.heizkalender")
    gast_oeffnung_events = get_calendar_events("calendar.schwanen_offnungszeiten")

    # Prüfen ob heute geschlossen.
    # D.h. wenn im Clubdesk-Kalender ein Termin mit dem Namen "Gaststätte geschlossen" aktiv ist.
    logger.info(f"check if Gaststube is closed")
    geschlossen = event_currently_active(gast_heiz_events, "gaststätte geschlossen")
    logger.info(f"Gaststube is closed: {geschlossen}")
    # Wenn geschlossen → Öffnungszeiten ignorieren
    if geschlossen:
        gast_events = gast_heiz_events
    else:
        gast_events = gast_heiz_events + gast_oeffnung_events


    if event_currently_active(gast_events, "@gaststube"):
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.gaststube_modus",
                "option": "Heizen"
            }
        )
        logger.info("Modus Gaststube auf heizen gesetzt (aktiver Termin)")

    elif find_event(gast_events, "@gaststube", 3):
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.gaststube_modus",
                "option": "Heizen"
            }
        )
        logger.info("Modus Gaststube auf heizen gesetzt (3h)")

    elif find_event(gast_events, "@gaststube", 10):
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.gaststube_modus",
                "option": "Sparen"
            }
        )
        logger.info("Modus Gaststube auf sparen gesetzt (10h)")

    else:
        hass.services.call(
            "input_select", "select_option",
            {
                "entity_id": "input_select.gaststube_modus",
                "option": "Frostschutz"
            }
        )
        logger.info("Modus Gaststube auf Frostschutz gesetzt (>10h)")
    return

# aktuellen Zeitpunkt bestimmen, ab dem die Vorschau in den Kalender berechnet werden soll
now = datetime.now(timezone.utc)

#Abhängig vom func-Parameter werden unterschiedliche Funktionen aufgerufen.
func_name = data.get('func')
if func_name == 'moduserkennung_saal':
    moduserkennung_saal()
elif func_name == 'moduserkennung_gaststube':
    moduserkennung_gaststube()
else:
    hass.log(f"Unbekannte Funktion: {func_name}")