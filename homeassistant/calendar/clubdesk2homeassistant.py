import requests
import icalendar
from icalendar import Calendar, Event
from datetime import datetime, timedelta
from dateutil.rrule import rrulestr, rruleset
import pytz  # für TZ-Sicherheit

import re
import os


utc = pytz.UTC  # Global für alle Vergleiche

def normalize_datetime(dt_obj):
    """Für ALLE date/datetime → einheitliches TZ-aware datetime"""
    if isinstance(dt_obj, datetime):
        return utc.localize(dt_obj) if dt_obj.tzinfo is None else dt_obj.astimezone(utc)
    return utc.localize(datetime.combine(dt_obj, datetime.min.time()))


def flatten_ical_calendar(cal, start_range=None, end_range=None):
    """
    Entfaltet ICS → NEUES Calendar-Objekt mit flachen Events (walkbar!)
    """

    if start_range is None:
        start_range = datetime.now(utc) - timedelta(days=365)
    if end_range is None:
        end_range = datetime.now(utc) + timedelta(days=730)

    # Original parsen
    new_cal = Calendar()  # NEUES Calendar für expanded Events

    for vevent in cal.walk('VEVENT'):
        # TZ-sichere Extraktion (wie vorher gefixt)
        dtstart = normalize_datetime(vevent.get('dtstart').dt)
        dtend = normalize_datetime(vevent.get('dtend', vevent.get('dtstart')).dt)

        # Non-recurring
        if 'RRULE' not in vevent:
            if dtend >= start_range and dtstart <= end_range:
                new_cal.add_component(_copy_normalized_vevent(vevent))
            continue

        # Recurring: expandieren
        duration = dtend - dtstart
        rules = rruleset()

        # RRULE
        rrule_bytes = vevent['RRULE'].to_ical()
        rrule_str = rrule_bytes.decode('utf-8')
        rule = rrulestr(rrule_str, dtstart=dtstart)
        rules.rrule(rule)

        # EXDATE/RDATE falls vorhanden
        if 'EXDATE' in vevent:
            exdates = vevent['EXDATE'].dts if hasattr(vevent['EXDATE'], 'dts') else [vevent['EXDATE']]
            for exdate in exdates: rules.exdate(exdate.dt)
        if 'RDATE' in vevent:
            rdates = vevent['RDATE'].dts if hasattr(vevent['RDATE'], 'dts') else [vevent['RDATE']]
            for rdate in rdates: rules.rdate(rdate.dt)

        instance_counter = 0
        for occ_start in rules.between(start_range, end_range, inc=True):
            instance_counter += 1
            occ_end = occ_start + duration
            expanded_event = _copy_normalized_vevent(vevent, occ_start, occ_end, instance_counter)
            new_cal.add_component(expanded_event)

    return new_cal  # <- Calendar-Objekt!

def _copy_normalized_vevent(vevent, new_start=None, new_end=None, instance_id=None):
    """Kopiert VEVENT mit TZ-normalisierten Zeiten + UNIQUE UID"""
    ev = Event()

    # Original UID holen
    original_uid = str(vevent.get('uid', 'no-uid'))

    # UNIQUE UID für expanded Instances
    if instance_id is not None:
        unique_uid = f"{original_uid}_{instance_id}"
    else:
        unique_uid = original_uid

    for name, value in vevent.property_items():
        if name in ('DTSTART', 'DTEND', 'RRULE', 'EXDATE', 'RDATE', 'RECURRENCE-ID', 'UID'):
            continue
        ev.add(name, value)

    # Normalisierte Zeiten
    if new_start is None:
        dtstart = normalize_datetime(vevent['DTSTART'].dt)
        dtend = normalize_datetime(vevent.get('DTEND', vevent['DTSTART']).dt)
    else:
        dtstart, dtend = new_start, new_end

    ev.add('DTSTART', dtstart)
    ev.add('DTEND', dtend)
    ev.add('UID', unique_uid)  # ✅ UNIQUE UID!
    return ev


def sync_calendar():
    try:
        # 1. ICS-Datei laden
        ics_url = "https://calendar.clubdesk.com/clubdesk/ical/59940/1000212/djEts51Hu_914bRwP0SYLBR-31y_V-WOegp15Rz3556yFNw=/basic.ics"

        logger.info("Lade ICS-Datei...")
        response = requests.get(ics_url, timeout=10)

        if response.status_code != 200:
            logger.error(f"Fehler beim Abrufen: Status {response.status_code}")
            return

        ics_content = response.text
        # logger.error(f"xxxxx rohdate {ics_content}")

        # 2. UNTIL-Fehler korrigieren
        logger.info("Korrigiere UNTIL-Fehler...")

        ics_content = re.sub(
            r'UNTIL=(\d{8})([^T0-9])',
            r'UNTIL=\1T000000Z\2',
            ics_content
        )

        ics_content = re.sub(
            r'UNTIL=(\d{8}T\d{6})([^Z])',
            r'UNTIL=\1Z\2',
            ics_content
        )

        logger.info("UNTIL-Fehler korrigiert")

        #logger.error(f"xxxxx after UNTIL-korrektur {ics_content}")


        # 3. ICS-Datei parsen
        logger.info("Parse ICS-Datei...")
        try:
            cal = icalendar.Calendar.from_ical(ics_content)
        except Exception as e:
            logger.error(f"Fehler beim Parsen: {e}")
            logger.exception("message")
            return


        #logger.error(f"xxxxx cal-Object  {cal}")

        new_cal = flatten_ical_calendar(cal)

        #logger.error(f"xxxxx cal-Object flattend  {new_cal}")

        # 4. Keyword-Mapping f..r Orte definieren
        # Keyword ... Ort (case-insensitive)
        location_keywords = {
            'gaststube': '@gaststube',
            'saal': '@saal',
        }
        # 5. Events aus ICS extrahieren
        new_events = {}
        event_count = 0


        for component in new_cal.walk():
            if component.name == "VEVENT":
                event_count += 1

                dtstart = component.get('dtstart')
                dtend = component.get('dtend')
                summary = str(component.get('summary', f'Event {event_count}'))
                description = str(component.get('description', ''))
                location = str(component.get('location', ''))
                ics_uid = str(component.get('uid', f'event-{event_count}'))

                start_dt = dtstart.dt if dtstart else None
                end_dt = dtend.dt if dtend else None

                # 6. Ort basierend auf Keywords in Summary erg..nzen
                found_location = None

                # Pr..fe Description und Location auf Keywords
                search_text = location.lower()

                found_locations = set()

                # Alle passenden Keywords prüfen
                for keyword, location_name in location_keywords.items():
                    if keyword in search_text:
                        found_locations.add(location_name)
                        logger.info(f"Keyword '{keyword}' gefunden ... Ort: {location_name}")

                # Enhanced Summary aufbauen
                if found_locations:
                    # Nur Locations anhängen, die noch nicht in der Summary stehen
                    to_add = []
                    summary_lower = summary.lower()
                    for loc in found_locations:
                        if loc.lower() not in summary_lower:
                            to_add.append(loc)

                    if to_add:
                        enhanced_summary = f"{summary} ({', '.join(to_add)})"
                    else:
                        enhanced_summary = summary
                else:
                    enhanced_summary = summary
                logger.info(f"enhanced_summary:{enhanced_summary}")

                # 7. ICS-UID in Beschreibung einbetten
                enhanced_description = description
                if ics_uid:
                    # Markiere die UID eindeutig mit einem Präfix
                    enhanced_description = f"[ICS-UID:{ics_uid}]\n{description}".strip()
                # print(f"type {type(start_dt)} und {type(end_dt)}")
                # print(f"type tzinfo {type(start_dt.replace(tzinfo=None))}")

                event_data = {
                    'summary': enhanced_summary,
                    'description': enhanced_description,
                    'dtstart': start_dt,
                    'dtend': end_dt,
                    'location': found_location if found_location else location,
                    'ics_uid': ics_uid,
                    'start_iso': start_dt.isoformat() if start_dt else None,
                    'end_iso': end_dt.isoformat() if end_dt else None,
                }

                new_events[ics_uid] = event_data
                logger.info(f"Event aus ICS: {event_data} location:{location} (ICS-UID: {ics_uid})")

        if not new_events:
            logger.warning("Keine Events in ICS gefunden")
            return

        logger.info(f"Insgesamt {event_count} Events in ICS verarbeitet")

        # 8. Bestehende Events aus Home Assistant Kalender abrufen
        logger.info("Lese bestehende Events aus Kalender...")

        target_calendar = "calendar.heizkalender"

        cal_entity = hass.states.get(target_calendar)

        if cal_entity is None:
            logger.error(f"Kalender {target_calendar} nicht gefunden!")
            return

        existing_ha_events = {}  # ics_uid ... ha_event

        # Lese die lokale Kalender-Datei direkt
        calendar_storage_path = ".storage/local_calendar.calendar_heizkalender.ics"

        try:
            if os.path.isfile(calendar_storage_path):
                with open(calendar_storage_path, 'r') as f:
                    ics_content = f.read()
                    local_cal = Calendar.from_ical(ics_content)
                    for component in local_cal.walk():
                        if component.name == "VEVENT":
                            desc = str(component.get('DESCRIPTION', ''))
                            ics_uid_from_desc = extract_ics_uid(desc)
                            if ics_uid_from_desc:
                                summary = component.get('SUMMARY', '')
                                existing_ha_events[ics_uid_from_desc] = {
                                    'summary': str(summary),
                                    'description': desc,
                                    'location': component.get('LOCATION'),
                                    'dtstart': component.get('DTSTART').dt,
                                    'dtend': component.get('DTEND').dt,
                                    'uid': ics_uid_from_desc
                                }
                                logger.info(f"Bestehendes Event: {summary} (ICS-UID: {ics_uid_from_desc})")
        except Exception as e:
            logger.error(f"Konnte bestehende Events nicht auslesen: {e}")
            logger.exception("message")

        # 9. Vergleich und Synchronisierung
        created_count = 0
        updated_count = 0
        deleted_count = 0

        # Neue oder aktualisierte Events
        #logger.error(f"xxxxxx:  {new_events}")
        for ics_uid, new_event in new_events.items():
            try:
                # Neues Event
                logger.info(f"Neues Event erstellen: {new_event['summary']} - start: {new_event['dtstart']} end: {new_event['dtend']}")

                if hasattr(new_event['dtstart'], 'date') and not hasattr(new_event['dtstart'], 'time'):
                    hass.services.call('calendar', 'create_event', {
                        'entity_id': target_calendar,
                        'summary': new_event['summary'],
                        'description': new_event['description'],
                        'location': new_event['location'],
                        'start_date': new_event['start_iso'],
                        'end_date': new_event['end_iso'],
                    })
                else:
                    hass.services.call('calendar', 'create_event', {
                        'entity_id': target_calendar,
                        'summary': new_event['summary'],
                        'description': new_event['description'],
                        'location': new_event['location'],
                        'start_date_time': new_event['start_iso'],
                        'end_date_time': new_event['end_iso'],
                    })

                created_count += 1

            except Exception as e:
                logger.error(f"Fehler bei {new_event['summary']}: {e}")
                logger.exception("message")
            continue
        logger.info(
            f"Synchronisierung abgeschlossen: +{created_count} neu, ~{updated_count} ge..ndert, -{deleted_count} gel..scht")

    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
        logger.exception("message")
        return


def extract_ics_uid(description):
    """Extrahiert die ICS-UID aus dem Beschreibungsfeld"""
    try:
        if description and '[ICS-UID:' in description:
            # Format: "[ICS-UID:xxx-xxx-xxx]\n..."
            start = description.find('[ICS-UID:') + len('[ICS-UID:')
            end = description.find(']', start)
            if end > start:
                return description[start:end]
    except Exception as e:
        logger.error(f"Fehler beim Extrahieren der UID: {e}")
        logger.exception("message")
    return None


# Starte die Funktion
sync_calendar()