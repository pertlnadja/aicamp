Tabellen zu UseCase "Automatisierte Zeitreihenanalyse (Trends, Drifts, Anomalien)":

SNR_BOOKINGS_HMC_2026.csv => Seriennummernbuchung für Montage Ilz
SNR_BOOKINGS_LAN_2026.csv => Seriennummernbuchung für Fertigung Lannach
SNR_MEASUREMENTS_HMC_2026.csv => Messwerte für Montage Ilz
SNR_MEASUREMENTS_LAN_2026.csv => Messwerte für Fertigung Lannach
MERGE_UNMERGE_2026.csv => "Mergetabelle" beschreibt welche Seriennummern (Bauteile) in welche Bauteile verbaut wurden.

Spaltenbeschreibungen:
STATION_NUMBER
-> Stationsnummer an der das Bauteil bearbeitet wurde
PART_NUMBER
-> Teilenummer des Bauteils (Aggregatetyp)
SERIAL_NUMBER
-> Seriennummer des Bauteils (eindeutige Identifizierung des Bauteils)
BOOK_DATE
-> Buchungsdatum des Bauteils
BOOK_STATE
-> Buchungsstatus (0-pass / 1-fail / 2-scrap / 3-in process)
MEASURE_NAME
-> Messwert für das Bauteil (Beispiel: Endanzug Moment, Voranzug Winkel, …)
UNIT
-> Einheit des Messwertes
LOWER_LIMIT
-> Eingestellte Untergrenze für den Messwert
UPPER_LIMIT
-> Eingestellte Obergrenze für den Messwert
MEASURE_VALUE
-> Aktueller Messwert
KAP_NR
-> Kapazitätsnummer (Stationsnummer)
PART_NUMBER_MASTER
-> Teilenummer des Master-Bauteils in welches ein anderes Bauteil verbaut (gemerged) wird
SNR_MASTER
-> Seriennummer des Master-Bauteils in welches ein anderes Bauteil verbaut (gemerged) wird
MERGED
-> Merge-Zeitpunkt, Zeitpunkt zu dem ein Bauteil in ein anderes verbaut wurde
UNMERGE
-> Unmerge-Zeitpunkt, Zeitpunkt an dem ein Bauteil aus dem anderen ausgebaut wurde
PART_NUMBER_SLAVE
-> Teilenummer des Slave-Bauteils, welches in ein Master-Bauteil verbaut (gemerged) wird
SNR_SLAVE
-> Seriennummer des Slave-Bauteils, welches in ein Master-Bauteil verbaut (gemerged) wird
