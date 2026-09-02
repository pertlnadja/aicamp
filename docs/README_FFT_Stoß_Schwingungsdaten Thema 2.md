# README: FFT-Schwingungsdaten Kapp KX260 Twin

## 1. Zweck

Dieses Datenpaket enthält FFT-basierte Schwingungsmessungen der Maschine **Kapp KX260 Twin (510251)**. Die Messungen sind nach Sensor und Workstep getrennt und enthalten neben dem FFT-Spektrum zusätzliche Maschinen- und Prozessdaten.

Die Daten können für Zustandsüberwachung, Trendanalysen, Prozessvergleiche und die Auswertung vorhandener Warn- und Alarmgrenzen verwendet werden.

## 2. Inhalt des Datenpakets

| Merkmal | Wert |
|---|---|
| Maschine | Kapp KX260 Twin (510251) |
| Materialnummer | M0091605 |
| Device | 10.191.78.83:3321 |
| Datentyp | FFT |
| Anzahl Dateien | 16 CSV-Dateien |
| Sensoren | 1 bis 4 |
| Enthaltene Worksteps | 111, 199, 211, 299 |
| FFT-Werte pro Messung | 1024 (`Wert1` bis `Wert1024`) |
| Frequenzauflösung | 6.103515625 Hz pro Bin |
| Amplitudeneinheit | Milli G (mG) |
| Spectrum Count | 1 |

Der Workstep `3` ist fachlich definiert, im vorliegenden Dateipaket jedoch nicht als eigene CSV-Datei enthalten.

## 3. Dateinamensschema

Die Dateien folgen diesem Schema:

```text
<Timestamp>_<Maschine>-<Materialnummer>-<Device>_<Sensor>-<Workstep>-FFT.csv
```

Beispiel:

```text
2026-05-12T22.23.44.131_Kapp_KX260_Twin_(510251)-M0091605-10_191_78_83_3321_3-199-FFT.csv
```

Die beiden letzten Kennungen vor `FFT.csv` bedeuten:

- `3`: Sensor 3, Werkstückspindel 1
- `199`: Workstep 199, Schlichten Spindel 1

## 4. Sensorzuordnung

| Sensor-ID | Messstelle |
|---:|---|
| 1 | Schleifspindel |
| 2 | Abrichterspindel |
| 3 | Werkstückspindel 1 |
| 4 | Werkstückspindel 2 |

## 5. Workstep-Zuordnung

| Workstep | Bearbeitungsschritt |
|---:|---|
| 3 | Warmlaufzyklus |
| 111 | Schruppen Spindel 1 |
| 199 | Schlichten Spindel 1 |
| 211 | Schruppen Spindel 2 |
| 299 | Schlichten Spindel 2 |

## 6. Enthaltene Sensor-Workstep-Kombinationen

| Sensor | Messstelle | 111 | 199 | 211 | 299 |
|---:|---|:---:|:---:|:---:|:---:|
| 1 | Schleifspindel | vorhanden | vorhanden | vorhanden | vorhanden |
| 2 | Abrichterspindel | vorhanden | vorhanden | vorhanden | vorhanden |
| 3 | Werkstückspindel 1 | vorhanden | vorhanden | vorhanden | vorhanden |
| 4 | Werkstückspindel 2 | vorhanden | vorhanden | vorhanden | vorhanden |

Damit enthält das Paket für jeden der vier Sensoren jeweils eine Datei für jeden der vier Produktions-Worksteps.

## 7. Alarmlevel

| Alarmlevel | Bedeutung |
|---:|---|
| -1 | Kein Limit vorhanden |
| 0 | Limit vorhanden, aber kein Alarm |
| 1 | Warnungslimit überschritten |
| 2 | Limit überschritten, Alarm |

Wichtige Interpretation:

- `-1` bedeutet nicht automatisch, dass der Messwert unkritisch ist. Für die betreffende Messung ist keine Grenzwertbewertung verfügbar.
- `0` bedeutet, dass ein Limit vorhanden ist und keine Überschreitung erkannt wurde.
- `1` kennzeichnet die Überschreitung des Warnungslimits.
- `2` kennzeichnet die Überschreitung des Alarmlimits.

Falls im Header Grenzwert- oder Referenzzeilen wie `WARNING`, `ERROR` oder `no Reference` vorkommen, sind diese als Limit- beziehungsweise Referenzinformationen und nicht als normale Messzeilen zu behandeln.

## 8. Aufbau einer CSV-Datei

Eine Datei besteht grundsätzlich aus folgenden Bereichen:

### 8.1 Messmetadaten

Im Kopfbereich stehen unter anderem:

- Datentyp
- Maschinenname
- Materialnummer
- Device
- Sensor-ID
- Workstep
- Frequenzauflösung
- Spectrum Count
- Referenz- oder Limitinformationen

### 8.2 Prozess- und Maschinenwerte

Messzeilen enthalten neben dem Spektrum unter anderem folgende Felder:

- `Timestamp`
- `Alarmlevel`
- `TeilNr`
- `Drehzahl`
- Achslasten
- Achspositionen
- Achstemperaturen
- Achsvorschübe
- Spindellasten
- Spindeltemperaturen
- Abrichtzähler
- maximaler Abrichtwert
- Schleifscheibendurchmesser
- DMC-Code
- Maschinen-Override

Die exakte Reihenfolge ist dem jeweiligen CSV-Header zu entnehmen.

### 8.3 FFT-Spektrum

Das Spektrum besteht aus 1024 Amplitudenwerten:

```text
Wert1, Wert2, ..., Wert1024
```

Alle FFT-Amplituden sind in **mG** angegeben.

## 9. Frequenzachse

Die Frequenzauflösung beträgt:

```text
6.103515625 Hz/Bin
```

Wenn `Wert1` dem 0-Hz-Bin entspricht, gilt für `WertN`:

```text
Frequenz in Hz = (N - 1) * 6.103515625
```

Beispiele:

| FFT-Spalte | Frequenz |
|---|---:|
| `Wert1` | 0 Hz |
| `Wert2` | 6.103515625 Hz |
| `Wert10` | 54.931640625 Hz |
| `Wert100` | 604.248046875 Hz |
| `Wert1024` | 6243.896484375 Hz |

## 10. Empfohlene Auswertelogik

Messungen sollten mindestens nach folgenden Merkmalen getrennt werden:

1. Maschine und Materialnummer
2. Sensor
3. Workstep
4. Zeitstempel
5. Alarmlevel

Für fachlich belastbare Vergleiche sollten nur Messungen mit identischem Sensor und identischem Workstep direkt miteinander verglichen werden. Sinnvolle Vergleiche sind beispielsweise:

- Schruppen gegen Schlichten auf Spindel 1: `111` gegen `199`
- Schruppen gegen Schlichten auf Spindel 2: `211` gegen `299`
- gleiche Worksteps zwischen den Sensoren
- zeitliche Entwicklung eines Sensors innerhalb desselben Worksteps
- Messspektrum gegen zugehörige Warn- und Alarmlimits

## 11. Hinweise zur Interpretation

- Ein einzelner hoher FFT-Wert ist ohne Frequenzbezug, Prozesszustand und Verlauf nicht ausreichend für eine Zustandsdiagnose.
- Sensoren und Worksteps dürfen bei Vergleichen nicht vermischt werden.
- Alarmlevel `-1` erfordert eine separate fachliche Bewertung, da kein Limit hinterlegt ist.
- Referenz- und Limitzeilen müssen beim Einlesen von normalen Messzeilen getrennt werden.
- Maschinen- und Prozessparameter sollten gemeinsam mit den FFT-Daten gespeichert und ausgewertet werden, damit Schwingungsänderungen dem jeweiligen Betriebszustand zugeordnet werden können.

## 12. Kurzlegende

```text
Sensoren:
1   = Schleifspindel
2   = Abrichterspindel
3   = Werkstückspindel 1
4   = Werkstückspindel 2

Worksteps:
3   = Warmlaufzyklus
111 = Schruppen Spindel 1
199 = Schlichten Spindel 1
211 = Schruppen Spindel 2
299 = Schlichten Spindel 2

Alarmlevel:
-1  = kein Limit vorhanden
0   = Limit vorhanden, kein Alarm
1   = Warnungslimit überschritten
2   = Limit überschritten, Alarm

Amplitude:
mG  = Milli G
```


# README: Stoß-Schwingungsdaten Kapp KX260 Twin

## 1. Zweck

Dieses Datenpaket enthält zeitaufgelöste Stoß- und RMS-Schwingungsmessungen der Maschine **Kapp KX260 Twin (510251)**. Die Dateien sind nach Sensor und Workstep getrennt und enthalten zusätzlich Maschinen- und Prozessparameter.

Die Daten eignen sich für Zustandsüberwachung, Trendanalysen, Prozessvergleiche, Stoßerkennung und die spätere Definition beziehungsweise Auswertung von Warn- und Alarmgrenzen.

## 2. Inhalt des Datenpakets

| Merkmal | Wert |
|---|---|
| Maschine | Kapp KX260 Twin (510251) |
| Materialnummer | M0091605 |
| Device | 10.191.78.83:3321 |
| Messart | Stoß |
| Sensoren | 1 bis 4 |
| Worksteps | 3, 111, 199, 211, 299 |
| Messgrößen | `Stoss` und `RMS` |
| Amplitudeneinheit | Milli G (mG) |
| Spectrum Count | 0 |

## 3. Dateinamensschema

Die Dateien folgen diesem Schema:

```text
<Timestamp>_<Maschine>-<Materialnummer>-<Device>_<Sensor>-<Workstep>-Stoss.csv
```

Beispiel:

```text
2026-05-12T02.22.47.869_Kapp_KX260_Twin_(510251)-M0091605-10_191_78_83_3321_2-299-Stoss.csv
```

Die beiden letzten Kennungen vor `Stoss.csv` bedeuten in diesem Beispiel:

- `2`: Sensor 2, Abrichterspindel
- `299`: Workstep 299, Schlichten Spindel 2

## 4. Sensorzuordnung

| Sensor-ID | Messstelle |
|---:|---|
| 1 | Schleifspindel |
| 2 | Abrichterspindel |
| 3 | Werkstückspindel 1 |
| 4 | Werkstückspindel 2 |

## 5. Workstep-Zuordnung

| Workstep | Bearbeitungsschritt |
|---:|---|
| 3 | Warmlaufzyklus |
| 111 | Schruppen Spindel 1 |
| 199 | Schlichten Spindel 1 |
| 211 | Schruppen Spindel 2 |
| 299 | Schlichten Spindel 2 |

## 6. Enthaltene Sensor-Workstep-Kombinationen

| Sensor | Messstelle | 3 | 111 | 199 | 211 | 299 |
|---:|---|:---:|:---:|:---:|:---:|:---:|
| 1 | Schleifspindel | vorhanden | vorhanden | vorhanden | vorhanden | vorhanden |
| 2 | Abrichterspindel | vorhanden | vorhanden | vorhanden | vorhanden | vorhanden |
| 3 | Werkstückspindel 1 | vorhanden | vorhanden | vorhanden | vorhanden | vorhanden |
| 4 | Werkstückspindel 2 | vorhanden | vorhanden | vorhanden | vorhanden | vorhanden |

## 7. Alarmlevel

| Alarmlevel | Bedeutung |
|---:|---|
| -1 | Kein Limit vorhanden |
| 0 | Limit vorhanden, aber kein Alarm |
| 1 | Warnungslimit überschritten |
| 2 | Limit überschritten, Alarm |

### Hinweise zur Interpretation

- `-1` bedeutet, dass für die Messung kein Limit vorhanden ist. Daraus kann nicht automatisch abgeleitet werden, dass der Messwert unkritisch ist.
- `0` bedeutet, dass ein Limit vorhanden ist und keine Überschreitung erkannt wurde.
- `1` kennzeichnet die Überschreitung des Warnungslimits.
- `2` kennzeichnet die Überschreitung des Alarmlimits.
- Zeilen mit `WARNING`, `ERROR` oder `no Reference` sind Grenzwert- beziehungsweise Referenzinformationen und müssen beim Einlesen von regulären Messzeilen getrennt werden.

## 8. Aufbau einer CSV-Datei

### 8.1 Metadaten

Der Kopfbereich enthält unter anderem:

- `type`: Messart `Stoss`
- `machinename`: Maschinenbezeichnung
- `materialnumber`: Materialnummer
- `Device`: Geräteadresse
- `sensor`: Sensor-ID
- `time between values`: zeitlicher Abstand zwischen den Messwerten in Millisekunden
- `spectrumcount`: bei diesen Stoßdaten `0`
- `workstep`: Workstep-ID
- Referenz- beziehungsweise Limitinformationen

### 8.2 Messwerttabelle

Die eigentliche Messwerttabelle beginnt mit einer Kopfzeile und enthält folgende zentrale Felder:

| Feld | Beschreibung | Einheit |
|---|---|---|
| `Timestamp` | Zeitstempel der Messung | Unix-Epoch in ms |
| `Alarmlevel` | Status gemäß Alarmlevel-Zuordnung | - |
| `TeilNr` | Werkstück- beziehungsweise Teilenummer | - |
| `Drehzahl` | erfasste Drehzahl | rpm |
| `Stoss` | Stoß- beziehungsweise Spitzenwert | mG |
| `RMS` | Effektivwert der Schwingung | mG |

Zusätzlich werden Maschinen- und Prozesswerte aufgezeichnet, darunter:

- Spindellasten und Spindeltemperaturen
- Achslasten, Achspositionen und Achstemperaturen
- Achsvorschübe
- Abrichtzähler und maximaler Abrichtwert
- Schleifscheibendurchmesser
- DMC-Code
- Maschinen-Override

Die exakte Reihenfolge ist der Kopfzeile der jeweiligen CSV-Datei zu entnehmen.

## 9. Abtastintervall

Das Feld `time between values` beschreibt den zeitlichen Abstand zwischen zwei Messwerten:

| Sensor | Messstelle | Zeit zwischen Messwerten |
|---:|---|---:|
| 1 | Schleifspindel | 8,333 ms |
| 2 | Abrichterspindel | 8,333 ms |
| 3 | Werkstückspindel 1 | 8,333 ms |
| 4 | Werkstückspindel 2 | 5,000 ms |

Bei zeitbezogenen Vergleichen muss das sensorspezifische Abtastintervall berücksichtigt werden.

## 10. Bedeutung der Schwingungskennwerte

### `Stoss`

Der Wert beschreibt den erfassten Stoß- beziehungsweise Spitzenwert. Er reagiert auf kurzzeitige Impulse und mechanische Stoßereignisse. Die Einheit ist **mG**.

### `RMS`

Der RMS-Wert ist der Effektivwert der Schwingung über das jeweilige Messfenster. Er beschreibt die allgemeine Schwingungsbelastung. Die Einheit ist ebenfalls **mG**.

`Stoss` und `RMS` sollten gemeinsam ausgewertet werden. Ein hoher Stoßwert bei vergleichsweise niedrigem RMS weist auf ein kurzzeitiges Ereignis hin, während ein dauerhaft erhöhter RMS-Wert auf eine breitere Schwingungsbelastung hindeuten kann. Die technische Bewertung muss immer im jeweiligen Prozesskontext erfolgen.

## 11. Empfohlene Auswertelogik

Messungen sollten mindestens nach folgenden Merkmalen getrennt werden:

1. Maschine und Materialnummer
2. Sensor
3. Workstep
4. Zeitstempel
5. Teilenummer
6. Alarmlevel

Für belastbare Vergleiche sollten nur Messungen mit identischem Sensor und identischem Workstep direkt miteinander verglichen werden.


## 12. Hinweise für den Datenimport

- Die Metadaten stehen vor der eigentlichen Tabellenkopfzeile.
- Die Messwerttabelle beginnt bei der Zeile, deren erstes Feld `Timestamp` lautet.
- Referenzzeilen mit `WARNING`, `ERROR` oder `no Reference` dürfen nicht als normale Messungen interpretiert werden.
- Für reguläre Messzeilen ist `Alarmlevel` numerisch gemäß Kapitel 7 auszuwerten.
- Dezimalwerte verwenden in den CSV-Dateien einen Punkt.
- Die Amplitudenfelder `Stoss` und `RMS` sind in mG angegeben.
- Sensor-ID und Workstep sollten sowohl aus den Metadaten als auch aus dem Dateinamen validiert werden.
- Das Abtastintervall darf nicht pauschal für alle Sensoren angenommen werden.

## 13. Kurzlegende

```text
Sensoren:
1   = Schleifspindel
2   = Abrichterspindel
3   = Werkstückspindel 1
4   = Werkstückspindel 2

Worksteps:
3   = Warmlaufzyklus
111 = Schruppen Spindel 1
199 = Schlichten Spindel 1
211 = Schruppen Spindel 2
299 = Schlichten Spindel 2

Alarmlevel:
-1  = kein Limit vorhanden
0   = Limit vorhanden, kein Alarm
1   = Warnungslimit überschritten
2   = Limit überschritten, Alarm

Amplitude:
mG  = Milli G
```


