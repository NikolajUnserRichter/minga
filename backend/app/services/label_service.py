from io import BytesIO
import qrcode
from reportlab.lib import units
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
        
        # Title: Sorte
        c.setFont("Helvetica-Bold", 16)
        c.drawString(5 * units.mm, y, batch.seed_name or "Unbekannte Sorte")
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
