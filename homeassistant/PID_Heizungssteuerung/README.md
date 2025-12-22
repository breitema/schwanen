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
Um den Heizmodus für den Saal im nicht-manuellen Modus zu ermitteln wird für die erst für die nächsten 3h nach Terminen im Kalender mit der entity ID "calendar.heizkalender" geschaut, die "@saal" im Namen haben, werden solche in der Zeit gefunden, wird der Modus Saal mit der ID "input_select.saal_modus" auf "heizen" gestellt, wenn nicht wird die gleiche Suche nochmal für die nächsten 10h wiederholt, wobei hier bei einem Treffer der Modus Saal ("input_select.saal_modus") auf "Sparen" gesetzt, wird immer noch nichts gefunden wird der Modus Saal ("input_select.saal_modus") auf "Frostschutz" gestellt.

### Ermittlung des Heizmodus' in der Gaststube
Um den Heizmodus für die Gaststube im nicht-manuellen Modus zu ermitteln wird für die erst für die nächsten 3h nach Terminen in den Kalendern mit den entity IDs "calendar.heizkalender" und "calendar.schwanen_offnungszeiten" geschaut, die "@gaststube" im Namen haben, werden solche in der Zeit gefunden, wird der Modus Gaststube mit der ID "input_select.gaststube_modus" auf "Heizen" gestellt, wenn nicht wird die gleiche Suche nochmal für die nächsten 10h wiederholt, wobei hier bei einem Treffer der Modus Gaststube ("input_select.gaststube_modus") auf "Sparen" gesetzt, wird immer noch nichts gefunden wird der Modus Gaststube ("input_select.gaststube_modus") auf "Frostschutz" gestellt. Eine Ausnahme besteht in der Gaststube im Falle dessen, dass im Kalender mit der ID "calendar.heizkalender" ein Termin mit dem Namen "Gaststätte geschlossen" oder "Gaststube geschlossen" an diesem Tag existiert. In diesem Fall werden Termine im Öffnungszeitenkalender mit der entity ID "calendar.schwanen_offnungszeiten" ignoriert.



# ChatGPT Anfragen:



### **Nachricht 1**

Wir wollen über den Homeassistant mit einer PID Steuerung zwei getrennte Räume steuern.
In jedem Raum sind zwei Temperatursensoren und mehrere Heizkörper mit TRVZB ventilen.
Es gibt eine zentrale Therme.
Die Heizung soll in zwei Modi arbeiten: Wenn nur ein Raum geheizt werden muss, sollen die Ventile in diesem raum komplett geöffnet und im anderen Komplett geschlossen sein. Die Steuerung soll dann nur über die vorlauftemperatur der Therme gesteuert werden.
Gleichzeitig soll die Heizung auch witterungsgeführt arbeiten. D.h. die Außentemperatur über einen Außenfühler soll zur Steuerung der Vorlauftemepratur berücksichtigt werden.
Es soll für jeden Raum drei Zielwerte geben: Frostschutz, Sparen und Heizen.
Einer der Räume ist sehr träge. Hier muss ggf. eine mehrstündige aufheizphase berücksichtigt werden.


### **Nachricht 2**

Thermostate im Saal
climate.saal_1_thermostat

climate.saal2_thermostat

climate.sonoff_trvzb_thermostat

climate.saal_4_thermostat

climate.saal_5_thermostat

climate.saal_6_thermostat

climate.saal_7_thermostat

climate.sonoff_trvzb_thermostat_2

climate.saal_8_thermostat

Thermostate in der Gaststube:

climate.gaststube_1_thermostat

climate.thermostat_gaststube_thermostat_2

climate.gaststube_3_thermostat

climate.gaststube_4_thermostat

climate.gaststube_5_thermostat

climate.gaststube_6_thermostat

Saal Temperatursenensor

sensor.sensor_saal_temperatur

Gaststube Temperatursensor

sensor.durchschnittstemperatur_gaststube

Außentemperatursensor

sensor.externer_temperatursensor_temperatur

Therme ID hier müssen die zwei werte angegeben werden zwischen denen die Temperatur schwanken soll.

climate.smarttherm_heizungs_thermostat

Bitte keinen Better Thermostat verwenden


### Nachricht 3

Der Träge raum ist die Gaststube, ja die vorlaufregelung soll gesteuert werden und ich hätte gerne immer automatische Bedarfserkennung und Witterungsgeführtes vorheizen


### Nachricht 4

Gerne in einer Datei