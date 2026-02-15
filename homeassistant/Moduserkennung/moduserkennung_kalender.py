from datetime import datetime, timedelta, timezone



# =========================
# KONSTANTEN
# =========================
HEIZGESCHWINDIGKEIT_SAAL = 1.0  # °C pro Stunde
HEIZGESCHWINDIGKEIT_GASTSTUBE = 1.0 # °C pro Stunde
HEIZKREISLAUF_ZEIT = {
    "saal": 45/60,      # 45 Minuten in Stunden
    "gaststube": 30/60, # 30 Minuten in Stunden
    "beide": 60/60      # 1 Stunde
}


# =========================
# HILFSFUNKTIONEN
# =========================

def get_calendar_events(entity_id):
    try:
        result = hass.services.call(
            'calendar', 'get_events',
            {
                'entity_id': entity_id,
                'start_date_time': (now - timedelta(hours=24)).isoformat(),
                'end_date_time': (now + timedelta(hours=24)).isoformat()
            },
            blocking=True,
            return_response=True
        )
        agenda = result[entity_id]
        return agenda['events']
    except Exception as e:
        logger.error(f"Kalenderfehler {entity_id}: {e}")
        hass.states.set('input_text.kalender_error', f"{entity_id}: {str(e)}")
        return []  # ← Immer leere Liste zurückgeben!

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


def get_temperatur(entity_id):
    """Holt aktuellen Temperaturwert aus Sensor oder input_number Entity"""
    try:
        state = hass.states.get(entity_id)
        if not state or state.state == 'unavailable':
            logger.warning(f"{entity_id} nicht verfügbar, Default 15°C")
            return 15.0

        # input_number gibt Strings zurück → zu float konvertieren
        temp_value = float(state.state)
        logger.debug(f"{entity_id}: {temp_value}°C")
        return temp_value

    except ValueError:
        logger.error(f"{entity_id}: ungültiger Wert '{state.state}'")
        return 15.0
    except Exception as e:
        logger.error(f"Fehler beim Lesen {entity_id}: {e}, Default 15°C")
        return 15.0


def get_heizlast_vorschau():
    """Bestimmt Heizlast: 'saal', 'gaststube' oder 'beide' für nächste 10h"""
    saal_events = get_calendar_events("calendar.heizkalender")
    gast_heiz_events = get_calendar_events("calendar.heizkalender")
    gast_oeffnung_events = get_calendar_events("calendar.schwanen_offnungszeiten")

    geschlossen = event_currently_active(gast_heiz_events, "gaststätte geschlossen")
    gast_events = gast_heiz_events if geschlossen else gast_heiz_events + gast_oeffnung_events

    saal_needed = event_currently_active(saal_events, "@saal") or find_event(saal_events, "@saal", 10)
    gast_needed = event_currently_active(gast_events, "@gaststube") or find_event(gast_events, "@gaststube", 10)

    if saal_needed and gast_needed:
        return "beide"
    elif saal_needed:
        return "saal"
    elif gast_needed:
        return "gaststube"
    return "keiner"

# 🔥 STETIGE AUSSENTEMPERATUR-FUNKTION
def get_aussen_faktor(aussen_temp):
    """
    Sanfte stetige Funktion: Minimaler Einfluss der Außentemperatur
    Basis: 10°C = 1.0
    -10°C: 0.88 (+12% längere Zeit)
     0°C: 0.94 (+6% längere Zeit)
    20°C: 1.10 (-10% kürzere Zeit)
    """
    if aussen_temp >= 10:
        return min(1.0 + (aussen_temp - 10) * 0.01, 1.10)  # Max +10%
    else:
        return max(0.88 + (aussen_temp / 10) * 0.06, 0.88)  # Min -12%


# =========================
# Heizmodusberechnung für SAAL bzw. Gaststube - DYNAMISCHE VORHEIZEIT
# =========================
def moduserkennung_raum(raum_config):
    """
    Universelle Heizlogik für Saal ODER Gaststube

    raum_config = {
        'name': 'Saal',                    # Log-Name
        'keyword': '@saal',                # Kalender-Suchbegriff
        'heiz_events_entity': 'calendar.heizkalender',
        'oeffnungs_events_entity': None,   # None für Saal
        'modus_entity': 'input_select.saal_modus',
        'soll_temp_entity': 'input_number.saal_heizen',
        'ist_temp_entity': 'sensor.durchschnitt_saal_helfer',
        'heiz_geschwindigkeit': 2.0,
        'heizkreislauf_default': 'saal'
    }
    """
    raum_name = raum_config['name']

    # Events laden
    heiz_events = get_calendar_events(raum_config['heiz_events_entity'])

    # Gaststube-Spezialfall: Öffnungszeiten + Geschlossen-Check
    if raum_config.get('oeffnungs_events_entity'):
        oeffnungs_events = get_calendar_events(raum_config['oeffnungs_events_entity'])
        geschlossen = event_currently_active(heiz_events, "gaststätte geschlossen")
        events = heiz_events if geschlossen else heiz_events + oeffnungs_events
        keyword = raum_config['keyword']
    else:
        events = heiz_events
        keyword = raum_config['keyword']

    # Aktiver Termin → sofort heizen
    if event_currently_active(events, keyword):
        hass.services.call("input_select", "select_option",
                           {"entity_id": raum_config['modus_entity'], "option": "Heizen"})
        logger.info(f"✅ {raum_name}: Heizen (aktueller Termin)")
        return

    # NÄCHSTES Event finden
    naechstes_event = None
    for event in events:
        start = parse_iso(event["start"])
        name = event.get("summary", "").lower()
        if keyword in name and start > now:
            if naechstes_event is None or start < parse_iso(naechstes_event["start"]):
                naechstes_event = event

    if naechstes_event is None:
        hass.services.call("input_select", "select_option",
                           {"entity_id": raum_config['modus_entity'], "option": "Frostschutz"})
        logger.info(f"❌ {raum_name}: Frostschutz (kein Termin)")
        return

    # Zeit bis Event
    start_zeit = parse_iso(naechstes_event["start"])
    zeit_bis_event = (start_zeit - now).total_seconds() / 3600

    # Temperaturen + Berechnung
    soll_temp = get_temperatur(raum_config['soll_temp_entity'])
    ist_temp = get_temperatur(raum_config['ist_temp_entity'])
    aussen_temp = get_temperatur("sensor.aussentemperatursensor_temperatur")

    delta_temp = soll_temp - ist_temp
    heizlast = get_heizlast_vorschau()

    # Stetiger Außen-Faktor
    aussen_faktor = get_aussen_faktor(aussen_temp)
    effektive_geschwindigkeit = raum_config['heiz_geschwindigkeit'] * aussen_faktor

    heizkreislauf_key = heizlast if heizlast != "keiner" else raum_config['heizkreislauf_default']
    heizkreislauf_zeit = HEIZKREISLAUF_ZEIT[heizkreislauf_key]
    aufheiz_zeit = heizkreislauf_zeit + (delta_temp / effektive_geschwindigkeit)

    logger.info(f"{raum_name}: Event in {zeit_bis_event*60:.0f}min | ΔT={delta_temp}°C | "
                f"Außen={aussen_temp}°C→{aussen_faktor:.2f} | Geschw.={effektive_geschwindigkeit:.1f}°C/h | "
                f"Heizlast={heizlast} | Bedarf={aufheiz_zeit*60:.0f}min")

    # Entscheidung
    if zeit_bis_event <= aufheiz_zeit:
        hass.services.call("input_select", "select_option",
                           {"entity_id": raum_config['modus_entity'], "option": "Heizen"})
        logger.info(f"✅ {raum_name}: HEIZEN")
    else:
        hass.services.call("input_select", "select_option",
                           {"entity_id": raum_config['modus_entity'], "option": "Frostschutz"})
        logger.info(f"❌ {raum_name}: FROSTSCHUTZ")

# Saal-Konfiguration
SAAL_CONFIG = {
    'name': 'Saal',
    'keyword': '@saal',
    'heiz_events_entity': 'calendar.heizkalender',
    'oeffnungs_events_entity': None,
    'modus_entity': 'input_select.saal_modus',
    'soll_temp_entity': 'input_number.saal_heizen',
    'ist_temp_entity': 'sensor.durchschnitt_saal_helfer',
    'heiz_geschwindigkeit': 2.0,
    'heizkreislauf_default': 'saal'
}

# Gaststube-Konfiguration
GASTSTUBE_CONFIG = {
    'name': 'Gaststube',
    'keyword': '@gaststube',
    'heiz_events_entity': 'calendar.heizkalender',
    'oeffnungs_events_entity': 'calendar.schwanen_offnungszeiten',
    'modus_entity': 'input_select.gaststube_modus',
    'soll_temp_entity': 'input_number.gaststube_heizen',
    'ist_temp_entity': 'sensor.durchschnitt_gaststube_helfer',
    'heiz_geschwindigkeit': 1.0,
    'heizkreislauf_default': 'gaststube'
}


# Hauptlogik
now = datetime.now(timezone.utc)
func_name = data.get('func')
if func_name == 'moduserkennung_saal':
    moduserkennung_raum(SAAL_CONFIG)
elif func_name == 'moduserkennung_gaststube':
    moduserkennung_raum(GASTSTUBE_CONFIG)
else:
    hass.error(f"Unbekannte Funktion: {func_name}")
