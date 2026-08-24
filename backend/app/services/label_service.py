from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Sequence
import qrcode
from reportlab.lib import units
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from datetime import date

from app.models.production import GrowBatch
from app.models.inventory import FinishedGoodsInventory

# Standard thermal label size (e.g., Brother DK-11202 shipping label or generic 62mm)
# Let's assume 62mm width continuous or similar.
# 62mm x 100mm is a common size.
LABEL_WIDTH = 62 * units.mm
LABEL_HEIGHT = 100 * units.mm


@dataclass(frozen=True)
class LabelLayout:
    """Geometrie eines Etikettenbogens. Alle Maße in mm."""

    label_width: float
    label_height: float
    columns: int
    rows: int
    #: Rand bis zur ersten Spalte bzw. bis zur Oberkante der ersten Zeile
    margin_left: float
    margin_top: float
    #: None = A4-Bogen, sonst eine eigene Seitengröße (Rollendrucker)
    page_width: Optional[float] = None
    page_height: Optional[float] = None
    title_size: float = 8.0
    body_size: float = 6.5
    padding: float = 1.5

    @property
    def per_page(self) -> int:
        return self.columns * self.rows

    def page_size(self) -> tuple:
        if self.page_width is None or self.page_height is None:
            return A4
        return (self.page_width * units.mm, self.page_height * units.mm)


# Avery Zweckform 3667 / L7871: 48,5 × 16,9 mm, 4 Spalten × 16 Zeilen = 64 je A4.
# Die Etiketten stoßen aneinander; die Ränder ergeben sich aus dem Rest:
# (210 − 4×48,5)/2 = 8 mm seitlich, (297 − 16×16,9)/2 = 13,3 mm oben/unten.
AVERY_48x17 = LabelLayout(
    label_width=48.5, label_height=16.9, columns=4, rows=16,
    margin_left=8.0, margin_top=13.3,
)

# Rollendrucker: ein Etikett je Seite, dafür mehr Platz für größere Schrift.
ROLLE_45x25 = LabelLayout(
    label_width=45.0, label_height=25.0, columns=1, rows=1,
    margin_left=0.0, margin_top=0.0,
    page_width=45.0, page_height=25.0,
    title_size=10.0, body_size=8.0, padding=2.0,
)

LABEL_LAYOUTS = {
    "avery-48x17": AVERY_48x17,
    "45x25": ROLLE_45x25,
}


class UnbekanntesFormat(ValueError):
    """Angefordertes Etikettenformat steht nicht in LABEL_LAYOUTS."""


class KeineAussaat(LookupError):
    """An dem Tag ist keine Aussaat erfasst — es gibt nichts zu etikettieren."""


def baue_aussaat_etikettenbogen(db, tag: date, format: str) -> tuple:
    """Rendert den Etikettenbogen eines Aussaattages.

    Wird von zwei Seiten gebraucht — vom Direktdruck im Browser und beim
    Einreihen in die Druck-Warteschlange. Beide müssen dasselbe Blatt
    bekommen, deshalb liegt der Weg von Datum + Format zum PDF hier.

    :returns: (pdf_bytes, dateiname)
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from app.models.seed import SeedBatch

    layout = LABEL_LAYOUTS.get(format)
    if layout is None:
        raise UnbekanntesFormat(
            f"Unbekanntes Etikettenformat '{format}'. Möglich: "
            + ", ".join(sorted(LABEL_LAYOUTS))
        )

    batches = db.execute(
        select(GrowBatch)
        .options(joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed))
        .where(GrowBatch.aussaat_datum == tag)
        .order_by(GrowBatch.created_at)
    ).unique().scalars().all()

    if not batches:
        raise KeineAussaat(
            f"Für den {tag.strftime('%d.%m.%Y')} ist keine Aussaat erfasst."
        )

    return (
        LabelService.generate_aussaat_labels(batches, layout),
        f"Aussaat-Etiketten_{tag.isoformat()}.pdf",
    )


def _fit_size(c, text: str, font: str, size: float, max_width: float) -> float:
    """Verkleinert die Schrift, bis der Text in die Etikettenbreite passt.

    Kürzen ist die schlechtere Wahl — im Growroom hilft 'Sonnenblume Bla'
    niemandem. Unter 4,5 pt wird es unleserlich, dann bleibt nur kürzen.
    """
    while size > 4.5 and c.stringWidth(text, font, size) > max_width:
        size -= 0.25
    return size


def _truncate(c, text: str, font: str, size: float, max_width: float) -> str:
    while text and c.stringWidth(text, font, size) > max_width:
        text = text[:-1]
    return text


def _fit(c, text: str, font: str, size: float, max_width: float) -> tuple:
    size = _fit_size(c, text, font, size, max_width)
    return _truncate(c, text, font, size, max_width), size


def _aussaat_label_text(batch: GrowBatch, tray_nr: int, trays: int) -> tuple:
    """Beschriftung eines Tray-Etiketts: Titel, zwei Zeilen links/rechts."""
    seed_batch = getattr(batch, "seed_batch", None)
    seed = getattr(seed_batch, "seed", None) if seed_batch is not None else None
    name = (getattr(seed, "name", None) or "Unbekannte Sorte").strip()
    sorte = (getattr(seed, "sorte", None) or "").strip()
    titel = f"{name} {sorte}" if sorte and sorte.lower() not in name.lower() else name

    ernte = batch.erwartete_ernte_optimal
    # Die Chargennummer ist der Rückverfolgungsschlüssel — sie muss aufs Tray.
    charge = (getattr(seed_batch, "charge_nummer", None) or "").strip()
    links3 = f"{charge} {batch.regal_position}".strip() if batch.regal_position else charge

    return (
        titel,
        f"Aussaat {batch.aussaat_datum.strftime('%d.%m.%Y')}",
        f"Ernte {ernte.strftime('%d.%m.%Y')}" if ernte else "",
        links3,
        f"{tray_nr}/{trays}",
    )


class LabelService:
    @staticmethod
    def generate_grow_label(batch: GrowBatch) -> bytes:
        """
        Generiert ein Label für eine Aussaat-Charge (Trays).
        """
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(LABEL_WIDTH, LABEL_HEIGHT))
        
        # Border (optional, for debugging mostly)
        # c.rect(1*units.mm, 1*units.mm, LABEL_WIDTH-2*units.mm, LABEL_HEIGHT-2*units.mm)

        # Content
        y = LABEL_HEIGHT - 10 * units.mm
        
        # Title: Sorte (via seed_batch.seed.name; Fallback wenn Relation nicht geladen)
        seed_name = "Unbekannte Sorte"
        seed_batch = getattr(batch, "seed_batch", None)
        if seed_batch is not None:
            seed = getattr(seed_batch, "seed", None)
            if seed is not None and getattr(seed, "name", None):
                seed_name = seed.name
        c.setFont("Helvetica-Bold", 16)
        c.drawString(5 * units.mm, y, seed_name)
        y -= 8 * units.mm

        # Subtitle: Variety specific (if available, mostly part of name)
        c.setFont("Helvetica", 10)
        c.drawString(5 * units.mm, y, f"Charge: {batch.id}")
        y -= 15 * units.mm

        # QR Code
        qr_code = qr.QrCodeWidget(f"BATCH:{batch.id}")
        qr_code.barWidth = 35 * units.mm
        qr_code.barHeight = 35 * units.mm
        qr_code.qrVersion = 1
        
        d = Drawing(35 * units.mm, 35 * units.mm)
        d.add(qr_code)
        renderPDF.draw(d, c, (LABEL_WIDTH - 35 * units.mm) / 2, y - 35*units.mm)
        y -= 40 * units.mm

        # Sowing Date
        c.setFont("Helvetica-Bold", 12)
        c.drawString(5 * units.mm, y, f"Aussaat: {batch.aussaat_datum.strftime('%d.%m.%Y')}")
        y -= 6 * units.mm

        # Trays
        c.setFont("Helvetica", 12)
        c.drawString(5 * units.mm, y, f"Trays: {batch.tray_anzahl}")
        y -= 6 * units.mm

        # Location
        if batch.regal_position:
            c.drawString(5 * units.mm, y, f"Pos: {batch.regal_position}")
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def generate_aussaat_labels(
        batches: Sequence[GrowBatch],
        layout: LabelLayout = AVERY_48x17,
    ) -> bytes:
        """Etikettenbogen für die Aussaat eines Tages — ein Etikett je Tray.

        Der Growroom braucht das Etikett am Tray, nicht an der Charge: erst
        damit lässt sich später zurückverfolgen, aus welcher Saatgut-Charge
        eine Schale stammt.
        """
        zeilen = []
        for batch in batches:
            trays = max(batch.tray_anzahl or 1, 1)
            for nr in range(1, trays + 1):
                zeilen.append(_aussaat_label_text(batch, nr, trays))

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=layout.page_size())
        page_width, page_height = layout.page_size()
        pad = layout.padding * units.mm
        max_width = layout.label_width * units.mm - 2 * pad

        for index, (titel, links2, rechts2, links3, rechts3) in enumerate(zeilen):
            platz = index % layout.per_page
            if index and platz == 0:
                c.showPage()

            spalte = platz % layout.columns
            reihe = platz // layout.columns
            x = layout.margin_left * units.mm + spalte * layout.label_width * units.mm
            # ReportLab zählt von unten, der Bogen wird von oben befüllt.
            y = page_height - (layout.margin_top + (reihe + 1) * layout.label_height) * units.mm

            leading = layout.body_size * 1.7
            cap = layout.title_size * 0.72
            frei = (layout.label_height * units.mm - (cap + 2 * leading)) / 2
            basis = y + layout.label_height * units.mm - frei - cap

            text, size = _fit(c, titel, "Helvetica-Bold", layout.title_size, max_width)
            c.setFont("Helvetica-Bold", size)
            c.drawString(x + pad, basis, text)

            for versatz, (links, rechts) in enumerate(((links2, rechts2), (links3, rechts3)), start=1):
                zeile_y = basis - versatz * leading
                # Beide Hälften teilen sich eine Schriftgröße — sonst steht die
                # rechte Angabe größer neben der geschrumpften linken.
                size = _fit_size(c, f"{links}  {rechts}".strip(), "Helvetica",
                                 layout.body_size, max_width)
                rechts_breite = c.stringWidth(rechts, "Helvetica", size) if rechts else 0
                c.setFont("Helvetica", size)
                c.drawString(x + pad, zeile_y, _truncate(
                    c, links, "Helvetica", size, max_width - rechts_breite - 0.5 * units.mm))
                if rechts:
                    c.drawRightString(x + layout.label_width * units.mm - pad, zeile_y, rechts)

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def generate_product_label(inventory: FinishedGoodsInventory) -> bytes:
        """
        Generiert ein Label für Fertigware.
        """
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(LABEL_WIDTH, LABEL_HEIGHT))

        y = LABEL_HEIGHT - 10 * units.mm

        # Product Name
        product_name = inventory.product.name if inventory.product else "Produkt"
        c.setFont("Helvetica-Bold", 14)
        c.drawString(5 * units.mm, y, product_name)
        y -= 8 * units.mm

        # Variant / SKU
        sku = inventory.product.sku if inventory.product else ""
        c.setFont("Helvetica", 10)
        c.drawString(5 * units.mm, y, f"Art.Nr: {sku}")
        y -= 10 * units.mm

        # Quantity
        c.setFont("Helvetica-Bold", 18)
        c.drawRightString(LABEL_WIDTH - 5 * units.mm, y, f"{inventory.current_quantity_g:.0f}g")
        y -= 10 * units.mm

        # Divider
        c.line(5 * units.mm, y, LABEL_WIDTH - 5 * units.mm, y)
        y -= 5 * units.mm

        # QR Code (New!)
        # Content: INV:{id} for scanning
        qr_content = f"INV:{inventory.id}"
        qr_code = qr.QrCodeWidget(qr_content)
        qr_code.barWidth = 25 * units.mm
        qr_code.barHeight = 25 * units.mm
        qr_code.qrVersion = 1
        
        d = Drawing(25 * units.mm, 25 * units.mm)
        d.add(qr_code)
        # Position top-right or somewhere visible. Let's put it on the right side below divider.
        renderPDF.draw(d, c, LABEL_WIDTH - 30 * units.mm, y - 25*units.mm)
        
        # Adjust Y for text on left


        # Dates
        c.setFont("Helvetica", 9)
        c.drawString(5 * units.mm, y, "Ernte:")
        c.drawRightString(LABEL_WIDTH - 5 * units.mm, y, inventory.harvest_date.strftime('%d.%m.%Y'))
        y -= 5 * units.mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(5 * units.mm, y, "Zu verbrauchen bis:")
        y -= 5 * units.mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(5 * units.mm, y, inventory.best_before_date.strftime('%d.%m.%Y'))
        y -= 10 * units.mm

        # Lot Code
        c.setFont("Helvetica", 8)
        c.drawString(5 * units.mm, y, f"Los-Nr: {inventory.batch_number}")
        y -= 8 * units.mm

        # Origin / Producer
        c.setFont("Helvetica", 6)
        c.drawString(5 * units.mm, y, "Hergestellt von:")
        y -= 3 * units.mm
        c.drawString(5 * units.mm, y, "Minga Greens Microgreens")
        y -= 3 * units.mm
        c.drawString(5 * units.mm, y, "Musterstraße 1, 80331 München")

        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.getvalue()
