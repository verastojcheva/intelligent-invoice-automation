import csv
import random
import sqlite3
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "invoice_automation.db"

OUTPUT_DIR = BASE_DIR / "test-data" / "incoming"
MANIFEST_PATH = BASE_DIR / "test-data" / "invoice_scenarios.csv"

random.seed(42)


def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def fetch_open_pos(connection):
    return connection.execute(
        """
        SELECT
            po.po_number,
            po.supplier_id,
            po.expected_amount,
            po.currency,
            po.status,
            s.supplier_name,
            s.vat_number,
            s.iban,
            s.status AS supplier_status,
            s.risk_level
        FROM PurchaseOrders po
        JOIN Suppliers s
            ON po.supplier_id = s.supplier_id
        WHERE po.status = 'OPEN'
          AND s.status = 'ACTIVE'
        ORDER BY po.po_number;
        """
    ).fetchall()


def fetch_paid_historical_invoice(connection):
    return connection.execute(
        """
        SELECT
            h.invoice_number,
            h.invoice_amount,
            h.invoice_date,
            h.po_number,
            s.supplier_name,
            s.vat_number,
            s.iban,
            po.currency
        FROM HistoricalInvoices h
        JOIN Suppliers s
            ON h.supplier_id = s.supplier_id
        JOIN PurchaseOrders po
            ON h.po_number = po.po_number
        WHERE h.status = 'PAID'
        ORDER BY h.invoice_id
        LIMIT 1;
        """
    ).fetchone()


def find_high_value_po(open_pos):
    candidates = [
        po for po in open_pos
        if po["expected_amount"] > 10000
    ]

    if not candidates:
        raise RuntimeError(
            "No open purchase order above €10,000 exists. "
            "Regenerate the sample data after increasing the PO amount range."
        )

    return candidates[0]


def make_invoice(
    invoice_number,
    supplier_name,
    vat_number,
    po_number,
    amount,
    currency,
    iban,
    invoice_date="2026-08-25",
    due_date="2026-09-24",
):
    return {
        "invoice_number": invoice_number,
        "supplier_name": supplier_name,
        "vat_number": vat_number,
        "po_number": po_number,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "net_amount": round(amount / 1.255, 2),
        "vat_amount": round(amount - (amount / 1.255), 2),
        "total_amount": round(amount, 2),
        "currency": currency,
        "iban": iban,
    }


def build_scenarios(connection):
    open_pos = fetch_open_pos(connection)

    if len(open_pos) < 8:
        raise RuntimeError(
            "Not enough open purchase orders to build the test scenarios."
        )

    duplicate = fetch_paid_historical_invoice(connection)

    if duplicate is None:
        raise RuntimeError(
            "No PAID historical invoice exists for duplicate testing."
        )

    high_value_po = find_high_value_po(open_pos)

    scenarios = []

    valid_pos = open_pos[:5]

    for index, po in enumerate(valid_pos, start=1):
        invoice = make_invoice(
            invoice_number=f"INV-{index:03d}",
            supplier_name=po["supplier_name"],
            vat_number=po["vat_number"],
            po_number=po["po_number"],
            amount=po["expected_amount"],
            currency=po["currency"],
            iban=po["iban"],
        )

        scenarios.append(
            {
                "file_name": f"invoice_{index:02d}_valid.pdf",
                "scenario": "VALID",
                "expected_result": "AUTO_PROCESS",
                "reason": "Supplier, PO, amount and currency all match.",
                "invoice": invoice,
                "template": index % 3,
                "quality": "NORMAL",
            }
        )

    duplicate_invoice = make_invoice(
        invoice_number=duplicate["invoice_number"],
        supplier_name=duplicate["supplier_name"],
        vat_number=duplicate["vat_number"],
        po_number=duplicate["po_number"],
        amount=duplicate["invoice_amount"],
        currency=duplicate["currency"],
        iban=duplicate["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_06_duplicate.pdf",
            "scenario": "DUPLICATE",
            "expected_result": "REJECT",
            "reason": "Invoice number already exists in historical invoices.",
            "invoice": duplicate_invoice,
            "template": 0,
            "quality": "NORMAL",
        }
    )

    po = open_pos[5]

    invoice = make_invoice(
        "INV-007",
        po["supplier_name"],
        po["vat_number"],
        "PO-9999",
        po["expected_amount"],
        po["currency"],
        po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_07_missing_po.pdf",
            "scenario": "MISSING_PO",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Referenced purchase order does not exist.",
            "invoice": invoice,
            "template": 1,
            "quality": "NORMAL",
        }
    )

    po = open_pos[6]

    invoice = make_invoice(
        "INV-008",
        "Unknown Industrial Supplier Oy",
        "FI99999999",
        po["po_number"],
        po["expected_amount"],
        po["currency"],
        "FI9999999999999999",
    )

    scenarios.append(
        {
            "file_name": "invoice_08_unknown_supplier.pdf",
            "scenario": "UNKNOWN_SUPPLIER",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Supplier VAT number does not exist in supplier master data.",
            "invoice": invoice,
            "template": 2,
            "quality": "NORMAL",
        }
    )

    po = open_pos[7]

    invoice = make_invoice(
        "INV-009",
        po["supplier_name"],
        po["vat_number"],
        po["po_number"],
        po["expected_amount"] * 1.08,
        po["currency"],
        po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_09_amount_mismatch.pdf",
            "scenario": "AMOUNT_MISMATCH",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Invoice amount exceeds the configured 2% PO tolerance.",
            "invoice": invoice,
            "template": 0,
            "quality": "NORMAL",
        }
    )

    po = open_pos[1]

    wrong_currency = (
        "USD"
        if po["currency"] != "USD"
        else "EUR"
    )

    invoice = make_invoice(
        "INV-010",
        po["supplier_name"],
        po["vat_number"],
        po["po_number"],
        po["expected_amount"],
        wrong_currency,
        po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_10_wrong_currency.pdf",
            "scenario": "WRONG_CURRENCY",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Invoice currency does not match the purchase order.",
            "invoice": invoice,
            "template": 1,
            "quality": "NORMAL",
        }
    )

    po = open_pos[2]

    invoice = make_invoice(
        "INV-011",
        po["supplier_name"],
        "",
        po["po_number"],
        po["expected_amount"],
        po["currency"],
        po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_11_missing_vat.pdf",
            "scenario": "MISSING_VAT",
            "expected_result": "MANUAL_REVIEW",
            "reason": "VAT number is missing.",
            "invoice": invoice,
            "template": 2,
            "quality": "NORMAL",
        }
    )

    invoice = make_invoice(
        "INV-012",
        high_value_po["supplier_name"],
        high_value_po["vat_number"],
        high_value_po["po_number"],
        high_value_po["expected_amount"],
        high_value_po["currency"],
        high_value_po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_12_high_value.pdf",
            "scenario": "HIGH_VALUE",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Invoice matches the PO but exceeds the €10,000 auto-approval limit.",
            "invoice": invoice,
            "template": 0,
            "quality": "NORMAL",
        }
    )

    po = open_pos[3]

    invoice = make_invoice(
        "INV-013",
        po["supplier_name"],
        po["vat_number"],
        po["po_number"],
        po["expected_amount"],
        po["currency"],
        po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_13_bad_quality.pdf",
            "scenario": "BAD_QUALITY",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Document quality is intentionally degraded for extraction testing.",
            "invoice": invoice,
            "template": 1,
            "quality": "BAD",
        }
    )

    po = open_pos[4]

    invoice = make_invoice(
        "INV-014",
        po["supplier_name"],
        po["vat_number"],
        po["po_number"],
        po["expected_amount"],
        po["currency"],
        po["iban"],
    )

    scenarios.append(
        {
            "file_name": "invoice_14_valid.pdf",
            "scenario": "VALID",
            "expected_result": "AUTO_PROCESS",
            "reason": "Second valid-template test case.",
            "invoice": invoice,
            "template": 2,
            "quality": "NORMAL",
        }
    )

    second_duplicate = duplicate_invoice.copy()
    second_duplicate["invoice_number"] = duplicate["invoice_number"]

    scenarios.append(
        {
            "file_name": "invoice_15_duplicate.pdf",
            "scenario": "DUPLICATE",
            "expected_result": "REJECT",
            "reason": "Repeated historical invoice number for duplicate-detection testing.",
            "invoice": second_duplicate,
            "template": 2,
            "quality": "NORMAL",
        }
    )

    return scenarios


def draw_template_standard(pdf, invoice):
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, 790, "INVOICE")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 760, f"Supplier: {invoice['supplier_name']}")
    pdf.drawString(50, 744, f"VAT number: {invoice['vat_number']}")
    pdf.drawString(50, 728, f"IBAN: {invoice['iban']}")

    pdf.drawString(
        360,
        760,
        f"Invoice: {invoice['invoice_number']}",
    )
    pdf.drawString(
        360,
        744,
        f"Date: {invoice['invoice_date']}",
    )
    pdf.drawString(
        360,
        728,
        f"Due: {invoice['due_date']}",
    )

    pdf.line(50, 700, 545, 700)

    pdf.drawString(50, 675, f"Purchase order: {invoice['po_number']}")
    pdf.drawString(50, 650, f"Net amount: {invoice['net_amount']:.2f}")
    pdf.drawString(50, 632, f"VAT: {invoice['vat_amount']:.2f}")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(
        50,
        605,
        f"TOTAL: {invoice['total_amount']:.2f} {invoice['currency']}",
    )


def draw_template_compact(pdf, invoice):
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(60, 790, invoice["supplier_name"])

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawRightString(535, 790, "Invoice")

    pdf.setFont("Helvetica", 10)

    details = [
        ("Invoice number", invoice["invoice_number"]),
        ("Invoice date", invoice["invoice_date"]),
        ("Due date", invoice["due_date"]),
        ("VAT number", invoice["vat_number"]),
        ("Purchase order", invoice["po_number"]),
        ("IBAN", invoice["iban"]),
    ]

    y = 745

    for label, value in details:
        pdf.drawString(60, y, f"{label}:")
        pdf.drawString(170, y, str(value))
        y -= 22

    pdf.line(60, y - 5, 535, y - 5)

    y -= 40

    pdf.drawString(
        60,
        y,
        f"Net amount: {invoice['net_amount']:.2f} {invoice['currency']}",
    )

    pdf.drawString(
        60,
        y - 22,
        f"VAT: {invoice['vat_amount']:.2f} {invoice['currency']}",
    )

    pdf.setFont("Helvetica-Bold", 13)

    pdf.drawString(
        60,
        y - 55,
        f"Total: {invoice['total_amount']:.2f} {invoice['currency']}",
    )


def draw_template_table(pdf, invoice):
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(50, 790, "SUPPLIER INVOICE")

    pdf.setFont("Helvetica", 10)

    pdf.drawString(50, 755, invoice["supplier_name"])
    pdf.drawString(50, 739, f"VAT: {invoice['vat_number']}")
    pdf.drawString(50, 723, f"IBAN: {invoice['iban']}")

    pdf.drawRightString(
        540,
        755,
        f"No. {invoice['invoice_number']}",
    )

    pdf.drawRightString(
        540,
        739,
        invoice["invoice_date"],
    )

    pdf.drawRightString(
        540,
        723,
        f"Due {invoice['due_date']}",
    )

    y = 665

    pdf.line(50, y, 540, y)

    pdf.drawString(60, y - 25, "PO")
    pdf.drawString(210, y - 25, "Net")
    pdf.drawString(315, y - 25, "VAT")
    pdf.drawString(420, y - 25, "Total")

    pdf.line(50, y - 35, 540, y - 35)

    pdf.drawString(60, y - 60, invoice["po_number"])
    pdf.drawString(210, y - 60, f"{invoice['net_amount']:.2f}")
    pdf.drawString(315, y - 60, f"{invoice['vat_amount']:.2f}")

    pdf.setFont("Helvetica-Bold", 10)

    pdf.drawString(
        420,
        y - 60,
        f"{invoice['total_amount']:.2f} {invoice['currency']}",
    )


def create_pdf(path, invoice, template, quality):
    pdf = canvas.Canvas(str(path), pagesize=A4)

    if quality == "BAD":
        pdf.setFillGray(0.45)

    if template == 0:
        draw_template_standard(pdf, invoice)
    elif template == 1:
        draw_template_compact(pdf, invoice)
    else:
        draw_template_table(pdf, invoice)

    if quality == "BAD":
        pdf.setFillGray(0.65)
        pdf.setFont("Helvetica", 8)

        for _ in range(30):
            x = random.randint(40, 540)
            y = random.randint(100, 800)
            pdf.drawString(x, y, ".")

    pdf.save()


def write_manifest(scenarios):
    fields = [
        "file_name",
        "scenario",
        "expected_result",
        "reason",
        "invoice_number",
        "supplier_name",
        "vat_number",
        "po_number",
        "total_amount",
        "currency",
    ]

    with MANIFEST_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for scenario in scenarios:
            invoice = scenario["invoice"]

            writer.writerow(
                {
                    "file_name": scenario["file_name"],
                    "scenario": scenario["scenario"],
                    "expected_result": scenario["expected_result"],
                    "reason": scenario["reason"],
                    "invoice_number": invoice["invoice_number"],
                    "supplier_name": invoice["supplier_name"],
                    "vat_number": invoice["vat_number"],
                    "po_number": invoice["po_number"],
                    "total_amount": invoice["total_amount"],
                    "currency": invoice["currency"],
                }
            )


def clear_old_test_files():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_file in OUTPUT_DIR.glob("*.pdf"):
        pdf_file.unlink()

    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}. "
            "Run generate_data.py first."
        )

    clear_old_test_files()

    connection = connect_db()

    try:
        scenarios = build_scenarios(connection)

        for scenario in scenarios:
            create_pdf(
                OUTPUT_DIR / scenario["file_name"],
                scenario["invoice"],
                scenario["template"],
                scenario["quality"],
            )

        write_manifest(scenarios)

    finally:
        connection.close()

    print("Test invoice generation completed successfully.")
    print(f"PDF invoices: {len(scenarios)}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Scenario manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()