"""
Tests: Gernot-Feedback vom 21.08.2026.

Abgedeckt:
- Excel-Templates brauchen eine ausgefüllte Beispielzeile ("damit ich genau
  weiß was ich einfüllen muss") — ohne dass das Beispiel beim Re-Upload als
  echte Datenzeile importiert wird.
"""
import io

import pytest
from openpyxl import load_workbook

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ENTITIES = ["customers", "suppliers", "seeds", "products", "locations", "order_history", "grow_batches"]


def _upload(client, entity: str, content: bytes):
    return client.post(
        f"/api/v1/imports/{entity}",
        files={"file": (f"template_{entity}.xlsx", content, XLSX_MIME)},
    )


class TestImportTemplates:
    @pytest.mark.parametrize("entity", ENTITIES)
    def test_template_hat_ausgefuelltes_beispielblatt(self, client, entity):
        r = client.get(f"/api/v1/imports/template/{entity}")
        assert r.status_code == 200, r.text

        wb = load_workbook(io.BytesIO(r.content))
        assert "Beispiel" in wb.sheetnames, f"{entity}: Beispielblatt fehlt"

        ws = wb["Beispiel"]
        header = [c.value for c in ws[1]]
        beispiel = [c.value for c in ws[2]]

        # Jede Pflichtspalte (Header endet auf "*") muss im Beispiel gefüllt sein
        for idx, h in enumerate(header):
            if h and str(h).rstrip().endswith("*"):
                assert beispiel[idx] not in (None, ""), f"{entity}: Pflichtfeld '{h}' im Beispiel leer"

    @pytest.mark.parametrize("entity", ENTITIES)
    def test_datenblatt_ist_leer_und_heisst_daten(self, client, entity):
        r = client.get(f"/api/v1/imports/template/{entity}")
        wb = load_workbook(io.BytesIO(r.content))
        assert wb.sheetnames[0] == "Daten", f"{entity}: erstes Blatt muss 'Daten' heißen"
        assert wb.active.title == "Daten", f"{entity}: 'Daten' muss beim Öffnen aktiv sein"

    @pytest.mark.parametrize("entity", ["customers", "order_history", "grow_batches"])
    def test_unveraendertes_template_importiert_nichts(self, client, entity):
        """Das Beispiel darf nicht versehentlich als Datensatz landen."""
        tpl = client.get(f"/api/v1/imports/template/{entity}").content
        r = _upload(client, entity, tpl)
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 0, f"{entity}: Beispielzeile wurde importiert"
        assert r.json()["errors"] == []

    def test_beispielblatt_wird_nie_als_datenblatt_gelesen(self, client):
        """Excel speichert das zuletzt angesehene Blatt als aktiv.

        Wer im Template auf 'Beispiel' klickt und speichert, darf damit nicht
        die Beispieldaten importieren."""
        tpl = client.get("/api/v1/imports/template/customers").content
        wb = load_workbook(io.BytesIO(tpl))
        wb.active = wb.sheetnames.index("Beispiel")
        buf = io.BytesIO()
        wb.save(buf)

        r = _upload(client, "customers", buf.getvalue())
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 0, "Beispielblatt wurde als Datenblatt importiert"

    def test_altes_einblatt_template_bleibt_importierbar(self, client):
        """Vor dem Beispielblatt ausgegebene Templates müssen weiter funktionieren."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "customers"
        ws.append(["name *", "typ *", "email"])
        ws.append(["[str]", "[enum:GASTRO|HANDEL|GEWERBE|PRIVAT]", "[str]"])
        ws.append(["Altes Template GmbH", "GASTRO", "alt@example.com"])
        buf = io.BytesIO()
        wb.save(buf)

        r = _upload(client, "customers", buf.getvalue())
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 1
