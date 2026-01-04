# Parametrisiertes Heiz-Script für ZHA (robust, kein return)

from typing import Any
if False:  # for IDE only, never runs
    hass: Any = None
    data: dict[str, Any] = {}
    logger: Any = None


AREA_ID = data.get("area_id")
HEIZ_TEMP = float(data.get("heiz_temp", 35))
ABSENK_TEMP = float(data.get("absenk_temp", 6))

if not AREA_ID:
    logger.error("Heiz-Script: area_id fehlt")
else:

    logger.info(f"{AREA_ID}: Heiz-Script gestartet {HEIZ_TEMP} {ABSENK_TEMP}")

    # Heizbedarfssensor
    sensor_id = f"sensor.{AREA_ID}_heizbedarf_berechnet"
    sensor = hass.states.get(sensor_id)

    if sensor is None:
        logger.error(f"{AREA_ID}: Heizbedarfssensor nicht gefunden ({sensor_id})")
    else:
        try:
            heizbedarf = float(sensor.state)
        except ValueError:
            logger.error(f"{AREA_ID}: Heizbedarf ist kein numerischer Wert")
        else:
            zieltemperatur = HEIZ_TEMP if heizbedarf > 0 else ABSENK_TEMP
            logger.info(
                f"{AREA_ID}: Heizbedarf={heizbedarf} → Zieltemperatur={zieltemperatur}"
            )

            # Climate-Entitäten im Area suchen
            climates = hass.states.entity_ids("climate")
            thermostate = []
            for entity_id in climates:
                state = hass.states.get(entity_id)
                if not state:
                    continue
                if entity_id.startswith(f"climate.{AREA_ID}"):
                    thermostate.append(entity_id)

            if not thermostate:
                logger.error(f"{AREA_ID}: Keine Thermostate gefunden")
            else:
                logger.info(f"{AREA_ID}: {len(thermostate)} Thermostate gefunden")
                thermostate.sort()
                # Jedes Thermostat einzeln behandeln
                for entity_id in thermostate:
                    state = hass.states.get(entity_id)

                    if state.state in ("unavailable", "unknown"):
                        logger.error(f"{AREA_ID}: {entity_id} nicht verfügbar – übersprungen")
                        continue

                    # Temperatur setzen
                    try:
                        hass.services.call(
                            "climate",
                            "set_temperature",
                            {
                                "entity_id": entity_id,
                                "temperature": zieltemperatur,
                            },
                            False,
                        )
                        logger.info(
                            f"{AREA_ID}: {entity_id} → Temperatur {zieltemperatur}"
                        )
                    except Exception as e:
                        logger.error(f"{AREA_ID}: {entity_id} Temperatur-Fehler → {e}")
                        continue

                logger.info(f"{AREA_ID}: Heiz-Script abgeschlossen")
