# Etikettendruck

## Die Ausgangslage

NovaERP läuft auf einem Server im Rechenzentrum, der Etikettendrucker steht im
Hofnetz hinter einem normalen Router. Der Server kann den Drucker nicht
erreichen — weder über `IP:9100` noch über IPP, und das ändert sich auch nicht
durch eine andere Bibliothek. Gedruckt werden kann nur dort, wo jemand beide
Seiten sieht.

Daraus folgen genau zwei Wege.

## Weg A — Druck aus dem Browser (aktiv)

Der Rechner, an dem jemand arbeitet, kennt den Drucker bereits: er steht in den
Systemeinstellungen, wie in jedem anderen Programm auch. NovaERP schickt das
PDF deshalb nicht in den Download-Ordner, sondern direkt in den Druckdialog.

Umgesetzt in [`frontend/src/services/print.ts`](../frontend/src/services/print.ts):

* `druckePdf(daten)` — lädt das PDF in ein unsichtbares `iframe` und ruft
  `print()` auf. Der Systemdialog geht auf, Drucker und Anzahl wählt der Nutzer
  dort. Fällt der eingebaute PDF-Viewer aus (kommt auf Mobilgeräten vor), öffnet
  sich stattdessen ein Tab.
* `ladePdfHerunter(daten, dateiname)` — die Rückfalltür als Datei.

Benutzt an drei Stellen:

| Wo | Was |
| --- | --- |
| Produktion → Etiketten | Tagesbogen, ein Etikett je Kiste (Knopf **Drucken**, daneben **Herunterladen**) |
| Produktion → Chargenkarte | Einzeletikett einer Charge |
| Lager → Zeile | Etikett für eine Ware |

**Einmalige Einrichtung am Rechner:** den Etikettendrucker als Standarddrucker
setzen und im Druckdialog *Tatsächliche Größe* / Skalierung 100 % wählen —
sonst rechnet der Treiber die 48,5 × 16,9 mm auf A4 hoch. Für den Rollendrucker
das Format `45 × 25 mm` im Etikettendialog wählen, sonst kommt ein A4-Bogen.

## Weg B — Druck-Warteschlange mit lokalem Agenten (vorbereitet)

Für alles, wo niemand vor dem Bildschirm sitzt — Etiketten aus einem
Automatismus, Nachtlauf, Tablet ohne Druckertreiber. Das ERP legt einen
fertigen Auftrag ab, ein kleines Programm im Hofnetz holt ihn und druckt.

Serverseite steht: Tabelle `print_jobs` und die Endpunkte unten. Der Agent
selbst ist noch nicht geschrieben — dafür muss erst feststehen, welcher Drucker
es wird.

### Warum das PDF am Auftrag hängt

Gerendert wird beim Einreihen, nicht beim Drucken. Zwei Gründe: gedruckt wird
der Stand von damals, auch wenn der Agent erst eine Stunde später vorbeischaut;
und der Agent muss nichts über Chargen, Sorten und Etikettenformate wissen —
er kann PDFs an Drucker schicken, mehr nicht.

### Schlüssel

Der Agent ist kein ERP-Benutzer. Er weist sich mit dem Header
`X-Print-Agent-Key` aus, verglichen gegen die Umgebungsvariable
`PRINT_AGENT_KEY` (in Coolify setzen, wie `PLATFORM_ADMIN_KEY`).

* nicht gesetzt → `503`, die Schnittstelle bleibt zu
* falsch → `401`

Die Adresse ist die des Tenants: `https://<tenant>.novaerp.de/api/v1/…`.

### Endpunkte

**ERP-Seite** (normale Benutzeranmeldung):

| Methode | Pfad | Zweck |
| --- | --- | --- |
| `POST` | `/api/v1/print-jobs/aussaat-etiketten?datum=&format=&kopien=&drucker=` | Tagesbogen einreihen, `201` mit dem Auftrag |
| `GET` | `/api/v1/print-jobs?status=OFFEN` | Aufträge ansehen, neueste zuerst |
| `POST` | `/api/v1/print-jobs/{id}/requeue` | zurück in die Schlange (Papierstau, abgestürzter Agent) |

**Agent-Seite** (`X-Print-Agent-Key`):

| Methode | Pfad | Zweck |
| --- | --- | --- |
| `GET` | `/api/v1/print-agent/jobs` | offene Aufträge, älteste zuerst |
| `POST` | `/api/v1/print-agent/jobs/{id}/claim` | übernehmen; `409`, wenn schon vergeben |
| `GET` | `/api/v1/print-agent/jobs/{id}/document` | die PDF-Bytes |
| `POST` | `/api/v1/print-agent/jobs/{id}/complete` | gedruckt |
| `POST` | `/api/v1/print-agent/jobs/{id}/fail` | `{"fehler": "Kein Papier"}` |

`claim` ist ein einziges `UPDATE … WHERE status = 'OFFEN'`. Zwei Agenten oder
ein Agent nach einem Neustart können denselben Auftrag damit nicht doppelt
drucken — der zweite bekommt `409`.

### Der Agent, wenn es so weit ist

Rund 50 Zeilen, als Dienst auf einem Rechner im Hofnetz (oder einem Raspberry
Pi): alle 10 Sekunden `GET /jobs`, für jeden Auftrag `claim` → `document` →
an den Drucker (`lp -d <drucker>` unter Linux/macOS, `SumatraPDF -print-to`
unter Windows) → `complete` bzw. `fail`. `format` am Auftrag sagt, welche
Rolle bzw. welches Fach gemeint ist.

## Etikettenformate

In [`backend/app/services/label_service.py`](../backend/app/services/label_service.py),
Registry `LABEL_LAYOUTS`:

| Schlüssel | Format |
| --- | --- |
| `avery-48x17` | Avery Zweckform 48,5 × 16,9 mm, 64 je A4-Bogen |
| `45x25` | Rollendrucker, 45 × 25 mm, ein Etikett je Seite |

Ein weiteres Format ist ein `LabelLayout(...)` mehr — Maße, Spalten, Zeilen,
Ränder. Sobald der Drucker feststeht, kommt sein Format hier dazu.
