# Grundprinzip der Heizungssteuerung
## Raumsituation
Der Schwanen verfügt über zwei Haupträume: Gaststube und Saal.

In der **Gaststube** gibt es sechs Heizkörper, die durch intelligente Heizkörpertherventile (TRVZB) angesteuert werden können.

Der **Saal** verfügt über neun Heizkörper, die durch intelleigente Heizkörperventile (TRVZB) angesteurt werden können.

Darüber hinaus gibt es noch eine Heizkörper in der die Herrentoilette, der über ein intelligenen Thermostatventil verfügt.
Der Heizkörper in der Damentoilette kann aktuell nicht gesteuert werden. D.h. er heizt immer, wenn die Therme heizt.

### Heizmodus Gaststube
Die Gaststube hat 3 Heizmodi: Heizen, Sparen und Frostschutz.
Welcher Modus gerade aktiv ist, wird aus drei Quellen bestimmt:
1. Öffnungszeiten der Gastätte (Sofern im Kalender kein Termin "Gaststätte geschlossen" eingetragen ist)
2. Verantaltungskalender (Ort: "Gaststube")
3. Manuell über Auswahl. Die Manuelle Modusauswahl ist zeitlich beschränkt und wird nach spätestens einer Stunde wieder gelöscht. Danach wird wieder die Brechnung aus Kalender und/oder Öffnuntzeiten aktiv.

Je nach Auswahl wird die Solltemperatur für die Gaststube eingestellt:

Heizen: 26°C

Sparen: 17°C

Frostschutz: 6°C

### Heizmodus Saal
Der Saal hat 3 Heizmodi: Heizen, Sparen und Frostschutz.
Welcher Modus gerade aktiv ist, wird aus zwei Quellen bestimmt:
1. Verantaltungskalender (Ort: "Gaststube")
2. Manuell über Auswahl. Die Manuelle Modusauswahl ist zeitlich beschränkt und wird nach spätestens einer Stunde wieder gelöscht. Danach wird wieder die Brechnung aus dem Kalender aktiv.

Je nach Auswahl wird die Solltemperatur für den Saal eingestellt:

Heizen: 26°C

Sparen: 17°C

Frostschutz: 6°C

### Hochheizen
Alle Räume sind im Defaultmodus "Frostschutz".

10h (evtl. Abhängig von Isttemperatur und Außentemperatur?) vor Öffnuntszeit bzw. Termin(s.o.) wird der Modus des Raums auf "Sparen" geändert.
4h (evtl. Abhängig von Außentemperatur?)

## Steuerung der Therme
Die Therme wird über einen ESP3266 Chip angesteuert und über eine PID Steuerung kontrolliert,
sie wird auf Basis der gewählten Heizmodi in den Räumen und der Außentemperatur nach folgender Rechnung
gesteuert:

2 * (1,4 * (S<sub>S</sub> - S<sub>I</sub>) + 2,4 * (G<sub>S</sub> - G<sub>I</sub>)) + 62 - (A * 0,8)

S<sub>S</sub> = Solltemperatur Saal

S<sub>I</sub> = Isttemperatur Saal

G<sub>S</sub> = Solltemperatur Gaststube

G<sub>I</sub> = Isttemperatur Gasttstube

A = Außentemperatur

## Steuerung der Thermostate
Je nach Modusauswahl werden auch die Thermostate eingestellt:

Heizen: 35°C (Damit die Thermostate voll aufgedreht sind, da die Thermostattemperatursensoren etwas ungenau sind)

Sparen: 17°C

Frostschutz: 7°C

### Ermittlung des Heizmodus' im Saal
Um den Heizmodus für den Saal im nicht-manuellen Modus zu ermitteln wird erst für die nächsten 3h nach Terminen im 
Kalender mit der entity ID "calendar.heizkalender" geschaut, die "@saal" im Namen haben, werden solche in diesem Zeitraum 
gefunden, wird der Modus Saal mit der ID "input_select.saal_modus" auf "heizen" gestellt. Wenn nicht, wird die gleiche 
Suche für die nächsten 10h wiederholt, wobei hier bei einem Treffer der Modus Saal ("input_select.saal_modus") 
auf "Sparen" gesetzt wird.
Wird immer noch nichts gefunden, wird der Modus Saal ("input_select.saal_modus") auf "Frostschutz" gestellt.

### Ermittlung des Heizmodus' in der Gaststube
Um den Heizmodus für die Gaststube im nicht-manuellen Modus zu ermitteln wird für die erst für die nächsten 3h nach 
Terminen in den Kalendern mit den entity IDs "calendar.heizkalender" und "calendar.schwanen_offnungszeiten" geschaut,
die "@gaststube" im Namen haben. 
Werden solche in der Zeit gefunden, wird der Modus Gaststube mit der ID "input_select.gaststube_modus" auf "Heizen" gestellt.
Wenn nicht wird die gleiche Suche nochmal für die kommenden 10h wiederholt, wobei hier bei einem Treffer der Modus 
Gaststube ("input_select.gaststube_modus") auf "Sparen" gesetzt wird.
Wird immer noch nichts gefunden, wird der Modus Gaststube ("input_select.gaststube_modus") auf "Frostschutz" gestellt.
Eine Ausnahme besteht in der Gaststube im Falle dessen, dass im Kalender mit der ID "calendar.heizkalender" ein Termin 
mit dem Namen "Gaststätte geschlossen" oder "Gaststube geschlossen" an diesem Tag existiert. 
In diesem Fall werden nur Termine im Kalender mit der ID "calendar.heizkalender" berücksichtigt.

