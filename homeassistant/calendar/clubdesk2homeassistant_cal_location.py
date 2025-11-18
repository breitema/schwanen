import requests
import icalendar
from icalendar import Calendar
from datetime import datetime
import re
import os
import json
import time

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
            'gastst..tte': '@gaststube',
            'gastro': '@gaststube',
            'restaurant': '@gaststube',
            'saal': '@saal',
            'festsaal': '@saal',
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
                enhanced_summary = summary
                found_location = None

                # Pr..fe Description und Location auf Keywords
                search_text = (description + ' ' + location + ' ' + summary).lower()

                for keyword, location_name in location_keywords.items():
                    if keyword in search_text:
                        found_location = location_name
                        logger.info(f"Keyword '{keyword}' gefunden ... Ort: {location_name}")
                        break

                # Erg..nze Summary mit Ort, falls nicht bereits enthalten
                if found_location and found_location.lower() not in summary.lower():
                    enhanced_summary = f"{summary} ({found_location})"

                # 7. ICS-UID in Beschreibung einbetten
                enhanced_description = description
                if ics_uid:
                    # Markiere die UID eindeutig mit einem Pr..fix
                    enhanced_description = f"[ICS-UID:{ics_uid}]\n{description}".strip()
                #print(f"type {type(start_dt)} und {type(end_dt)}")
                #print(f"type tzinfo {type(start_dt.replace(tzinfo=None))}")

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
                logger.info(f"Event aus ICS: {enhanced_summary} (ICS-UID: {ics_uid})")

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
        logger.warning("HERE1")

        try:
            logger.warning(f"HERE2 {calendar_storage_path}")
            if os.path.isfile(calendar_storage_path):
                logger.warning("HERE3")
                with open(calendar_storage_path, 'r') as f:
                    ics_content = f.read()
#                    logger.warning(f"ics_content: {ics_content}")
                    cal = Calendar.from_ical(ics_content)
                    logger.warning("HERE4")
#                    logger.warning(f"geparst: {cal}");

                    for component in cal.walk():
#                        logger.warning(f"HERE5: {component}")
                        if component.name == "VEVENT":
                            desc = str(component.get('DESCRIPTION', ''))
                            ics_uid_from_desc = extract_ics_uid(desc)
                            if ics_uid_from_desc:
                                summary = component.get('SUMMARY', '')
                                existing_ha_events[ics_uid_from_desc] = {
                                    'summary': str(summary),
                                    'description': desc,
                                    'dtstart': component.get('DTSTART').dt,
                                    'dtend': component.get('DTEND').dt,
                                    'uid': ics_uid_from_desc
                                }
                                logger.info(f"Bestehendes Event: {summary} (ICS-UID: {ics_uid_from_desc})")
        except Exception as e:
            logger.warning(f"Konnte bestehende Events nicht auslesen: {e}")
            existing_ha_events = {}
        # 9. Vergleich und Synchronisierung
        logger.info("Vergleiche und synchronisiere Events...")
        #logger.info(f"ICS-UID-MAPPIN-HA_EVENTS: {existing_ha_events}")
        created_count = 0
        updated_count = 0
        deleted_count = 0

        # Neue oder aktualisierte Events
        for ics_uid, new_event in new_events.items():
            try:
                if ics_uid in existing_ha_events:
                    # Event existiert bereits
                    existing = existing_ha_events[ics_uid]
                    ha_uid = existing.get('uid')
                    logger.info(f"uid Match found: Existing entry : HA_UID={ha_uid} {existing} New entry: UID={ics_uid}, {new_event}")
                    if (existing.get('summary') != new_event['summary'] or
                        existing.get('description') != new_event['description'] or
                        existing.get('dtstart') != new_event['start_iso'] or
                        existing.get('dtend') != new_event['end_iso']):

                        logger.info(f"Event ge..ndert: {new_event['summary']}")

                        # L..sche altes Event

                        # so funktioniert wenn innerhalb eines asynchronen prozesses ausgeführt
#                        await hass.services.async_call(
#                            'calendar',
#                            'delete_event',
#                            {
#                                'entity_id': target_calendar,
#                                'uid': ha_uid,
#                            },
#                            blocking=True
#                         )

                        # Bei Ausführung in synchronem Thread:
                        hass.loop.call_soon_threadsafe(
                            hass.async_create_task,
                            hass.services.async_call(
                                'calendar',
                                'delete_event',
                                {
                                    'entity_id': target_calendar,
                                    'uid': ha_uid,
                                },
                                blocking=True
                            )
                        )
                         
                         
#                        # Ausführung innerhalb eventloop:
#                        hass.services.call('calendar', 'delete_event', {
#                            'entity_id': target_calendar,
#                            'uid': ha_uid,
#                        })
                        logger.warning(f"HERE7: {entity_id} / {ha_uid} / {ics_uid}")

                        time.sleep(0.5)  # Kurze Pause

                        # Erstelle neues Event (mit ICS-UID in Beschreibung)
                        if hasattr(new_event['dtstart'], 'date') and not hasattr(new_event['dtstart'], 'time'):
                            hass.services.call('calendar', 'create_event', {
                                'entity_id': target_calendar,
                                'summary': new_event['summary'],
                                'description': new_event['description'],
                                'start_date': new_event['start_iso'],
                                'end_date': new_event['end_iso'],
                            })
                        else:
                            hass.services.call('calendar', 'create_event', {
                                'entity_id': target_calendar,
                                'summary': new_event['summary'],
                                'description': new_event['description'],
                                'start_date_time': new_event['start_iso'],
                                'end_date_time': new_event['end_iso'],
                            })

                        updated_count += 1
                    else:
                        logger.info(f"Event unver..ndert: {new_event['summary']}")
                else:
                    # Neues Event
                    logger.info(f"Neues Event erstellen: {new_event['summary']}")

                    if hasattr(new_event['dtstart'], 'date') and not hasattr(new_event['dtstart'], 'time'):
                        hass.services.call('calendar', 'create_event', {
                            'entity_id': target_calendar,
                            'summary': new_event['summary'],
                            'description': new_event['description'],
                            'start_date': new_event['start_iso'],
                            'end_date': new_event['end_iso'],
                        })
                    else:
                        hass.services.call('calendar', 'create_event', {
                            'entity_id': target_calendar,
                            'summary': new_event['summary'],
                            'description': new_event['description'],
                            'start_date_time': new_event['start_iso'],
                            'end_date_time': new_event['end_iso'],
                        })

                    created_count += 1

            except Exception as e:
                logger.error(f"Fehler bei {new_event['summary']}: {e}")
                continue


        # Events l..schen, die nicht mehr in der ICS vorhanden sind
        logger.warning(f"start loeschen existing: {existing_ha_events} new {new_events}")
        for ics_uid, existing in existing_ha_events.items():
            logger.warning(f"loeschen ics_uid: {ics_uid}, existing {existing}")
            if ics_uid not in new_events:
                try:
                    ha_uid = existing.get('uid')
                    summary = existing.get('summary')
                    logger.info(f"L..sche Event: {summary}")

                    hass.services.call('calendar', 'delete_event', {
                        'entity_id': target_calendar,
                        'uid': ha_uid,
                    })

                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Fehler beim L..schen: {e}")
                    continue

        logger.warning(f"Synchronisierung abgeschlossen: +{created_count} neu, ~{updated_count} ge..ndert, -{deleted_count} gel..scht")

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