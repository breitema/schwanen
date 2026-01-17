import requests
import icalendar
from icalendar import Calendar
import re
import os

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

        # 3. ICS-Datei parsen
        logger.info("Parse ICS-Datei...")
        try:
            cal = icalendar.Calendar.from_ical(ics_content)
        except Exception as e:
            logger.error(f"Fehler beim Parsen: {e}")
            return
        # 4. Keyword-Mapping f..r Orte definieren
        # Keyword ... Ort (case-insensitive)
        location_keywords = {
            'gaststube': '@gaststube',
            'saal': '@saal',
        }
        # 5. Events aus ICS extrahieren
        new_events = {}
        event_count = 0

        for component in cal.walk():
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
                    cal = Calendar.from_ical(ics_content)
                    for component in cal.walk():
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
        # 9. Vergleich und Synchronisierung
        created_count = 0
        updated_count = 0
        deleted_count = 0

        # Neue oder aktualisierte Events
        for ics_uid, new_event in new_events.items():
            try:
                # Neues Event
                logger.info(f"Neues Event erstellen: {new_event['summary']}")

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
                continue
        logger.info(
            f"Synchronisierung abgeschlossen: +{created_count} neu, ~{updated_count} ge..ndert, -{deleted_count} gel..scht")

    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
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

    return None


# Starte die Funktion
sync_calendar()