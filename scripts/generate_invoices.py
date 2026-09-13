import csv
import io
import random
import sqlite3
import tempfile
from pathlib import Path
import re

import fitz
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "invoice_automation.db"

OUTPUT_DIR = BASE_DIR / "test-data" / "incoming"
MANIFEST_PATH = BASE_DIR / "test-data" / "invoice_scenarios.csv"

PO_TOLERANCE = 0.02
AUTO_APPROVAL_LIMIT = 10000
RANDOM_SEED = 42

random.seed(RANDOM_SEED)


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


def fetch_clean_paid_historical_invoice(connection):
    """Return a historical invoice that is otherwise a clean Part 1 case.

    The duplicate-only scenarios should test DUPLICATE_INVOICE, not accidentally
    combine duplicate detection with wrong currency, high value, closed PO,
    inactive supplier, or an amount outside the configured PO tolerance.
    The extra headroom also keeps the 8% multi-reject amount mutation below the
    EUR 10,000 auto-approval threshold.
    """
    return connection.execute(
        """
        SELECT
            h.invoice_number,
            h.invoice_amount,
            h.invoice_date,
            h.po_number,
            s.supplier_id,
            s.supplier_name,
            s.vat_number,
            s.iban,
            po.expected_amount,
            po.currency,
            po.status AS po_status
        FROM HistoricalInvoices h
        JOIN Suppliers s
            ON h.supplier_id = s.supplier_id
        JOIN PurchaseOrders po
            ON h.po_number = po.po_number
        WHERE h.status = 'PAID'
          AND s.status = 'ACTIVE'
          AND po.status = 'OPEN'
          AND po.currency = 'EUR'
          AND h.invoice_amount < ?
          AND ABS(h.invoice_amount - po.expected_amount) / po.expected_amount <= ?
        ORDER BY h.invoice_id
        LIMIT 1;
        """,
        (AUTO_APPROVAL_LIMIT / 1.08, PO_TOLERANCE),
    ).fetchone()


def is_clean_eur_po(po):
    return po["currency"] == "EUR" and po["expected_amount"] < AUTO_APPROVAL_LIMIT


def is_amount_mismatch_baseline(po):
    return (
        po["currency"] == "EUR"
        and po["expected_amount"] * 1.08 < AUTO_APPROVAL_LIMIT
    )


def is_high_value_eur_po(po):
    return po["currency"] == "EUR" and po["expected_amount"] > AUTO_APPROVAL_LIMIT


def select_unique_pos(open_pos, predicate, count, used_po_numbers, description):
    candidates = [
        po
        for po in open_pos
        if predicate(po) and po["po_number"] not in used_po_numbers
    ]

    if len(candidates) < count:
        raise RuntimeError(
            f"Not enough unused purchase orders available for {description}. "
            f"Needed {count}, found {len(candidates)}. "
            "Regenerate the sample data with a wider PO amount/currency spread."
        )

    selected = candidates[:count]
    used_po_numbers.update(po["po_number"] for po in selected)
    return selected

def make_valid_finnish_iban(raw_iban: str) -> str:
    if not raw_iban:
        return raw_iban

    digits = re.sub(r"\D", "", str(raw_iban))

    if len(digits) < 14:
        raise ValueError(f"Cannot build Finnish IBAN from: {raw_iban}")

    bban = digits[-14:]

    provisional = bban + "FI00"

    numeric = "".join(
        str(ord(char) - 55) if char.isalpha() else char
        for char in provisional
    )

    check_digits = 98 - (int(numeric) % 97)

    return f"FI{check_digits:02d}{bban}"
    

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
        "iban": make_valid_finnish_iban(iban),
    }


def build_scenarios(connection):
    open_pos = fetch_open_pos(connection)

    duplicate = fetch_clean_paid_historical_invoice(connection)
    if duplicate is None:
        raise RuntimeError(
            "No clean PAID historical EUR invoice is available for duplicate testing. "
            "Regenerate the sample data or guarantee one clean duplicate candidate."
        )

    scenarios = []
    used_po_numbers = set()

    valid_pos = select_unique_pos(
        open_pos, is_clean_eur_po, 6, used_po_numbers, "VALID scenarios"
    )
    missing_po_baseline = select_unique_pos(
        open_pos, is_clean_eur_po, 1, used_po_numbers, "MISSING_PO baseline"
    )[0]
    unknown_supplier_baseline = select_unique_pos(
        open_pos, is_clean_eur_po, 1, used_po_numbers, "UNKNOWN_SUPPLIER baseline"
    )[0]
    amount_mismatch_baseline = select_unique_pos(
        open_pos,
        is_amount_mismatch_baseline,
        1,
        used_po_numbers,
        "AMOUNT_MISMATCH baseline",
    )[0]
    wrong_currency_baseline = select_unique_pos(
        open_pos, is_clean_eur_po, 1, used_po_numbers, "WRONG_CURRENCY baseline"
    )[0]
    missing_vat_baseline = select_unique_pos(
        open_pos, is_clean_eur_po, 1, used_po_numbers, "MISSING_VAT baseline"
    )[0]
    bad_quality_baseline = select_unique_pos(
        open_pos, is_clean_eur_po, 1, used_po_numbers, "BAD_QUALITY baseline"
    )[0]
    high_value_po = select_unique_pos(
        open_pos, is_high_value_eur_po, 1, used_po_numbers, "HIGH_VALUE scenario"
    )[0]
    multi_review_po = select_unique_pos(
        open_pos,
        is_high_value_eur_po,
        1,
        used_po_numbers,
        "MULTI_FAULT_REVIEW scenario",
    )[0]

    for index, po in enumerate(valid_pos[:5], start=1):
        scenarios.append(
            {
                "file_name": f"invoice_{index:02d}_valid.pdf",
                "scenario": "VALID",
                "expected_result": "AUTO_PROCESS",
                "reason": "Supplier, PO, amount and currency all match.",
                "expected_issues": [],
                "invoice": make_invoice(
                    f"INV-{index:03d}",
                    po["supplier_name"],
                    po["vat_number"],
                    po["po_number"],
                    po["expected_amount"],
                    po["currency"],
                    po["iban"],
                ),
                "template": index % 3,
                "quality": "NORMAL",
            }
        )

    duplicate_invoice = make_invoice(
        duplicate["invoice_number"],
        duplicate["supplier_name"],
        duplicate["vat_number"],
        duplicate["po_number"],
        duplicate["invoice_amount"],
        duplicate["currency"],
        duplicate["iban"],
    )
    scenarios.append(
        {
            "file_name": "invoice_06_duplicate.pdf",
            "scenario": "DUPLICATE",
            "expected_result": "REJECT",
            "reason": "Invoice number already exists in historical invoices.",
            "expected_issues": ["DUPLICATE_INVOICE"],
            "invoice": duplicate_invoice,
            "template": 0,
            "quality": "NORMAL",
        }
    )

    po = missing_po_baseline
    scenarios.append(
        {
            "file_name": "invoice_07_missing_po.pdf",
            "scenario": "MISSING_PO",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Referenced purchase order does not exist.",
            "expected_issues": ["MISSING_PO"],
            "invoice": make_invoice(
                "INV-007",
                po["supplier_name"],
                po["vat_number"],
                "PO-9999",
                po["expected_amount"],
                po["currency"],
                po["iban"],
            ),
            "template": 1,
            "quality": "NORMAL",
        }
    )

    po = unknown_supplier_baseline
    scenarios.append(
        {
            "file_name": "invoice_08_unknown_supplier.pdf",
            "scenario": "UNKNOWN_SUPPLIER",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Supplier VAT number does not exist in supplier master data.",
            "expected_issues": ["UNKNOWN_SUPPLIER"],
            "invoice": make_invoice(
                "INV-008",
                "Unknown Industrial Supplier Oy",
                "FI99999999",
                po["po_number"],
                po["expected_amount"],
                po["currency"],
                "FI9999999999999999",
            ),
            "template": 2,
            "quality": "NORMAL",
        }
    )

    po = amount_mismatch_baseline
    scenarios.append(
        {
            "file_name": "invoice_09_amount_mismatch.pdf",
            "scenario": "AMOUNT_MISMATCH",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Invoice amount exceeds the configured 2% PO tolerance.",
            "expected_issues": ["AMOUNT_MISMATCH"],
            "invoice": make_invoice(
                "INV-009",
                po["supplier_name"],
                po["vat_number"],
                po["po_number"],
                po["expected_amount"] * 1.08,
                po["currency"],
                po["iban"],
            ),
            "template": 0,
            "quality": "NORMAL",
        }
    )

    po = wrong_currency_baseline
    scenarios.append(
        {
            "file_name": "invoice_10_wrong_currency.pdf",
            "scenario": "WRONG_CURRENCY",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Invoice currency does not match the purchase order.",
            "expected_issues": ["WRONG_CURRENCY"],
            "invoice": make_invoice(
                "INV-010",
                po["supplier_name"],
                po["vat_number"],
                po["po_number"],
                po["expected_amount"],
                "USD",
                po["iban"],
            ),
            "template": 1,
            "quality": "NORMAL",
        }
    )

    po = missing_vat_baseline
    scenarios.append(
        {
            "file_name": "invoice_11_missing_vat.pdf",
            "scenario": "MISSING_VAT",
            "expected_result": "MANUAL_REVIEW",
            "reason": "VAT number is missing.",
            "expected_issues": ["MISSING_VAT"],
            "invoice": make_invoice(
                "INV-011",
                po["supplier_name"],
                "",
                po["po_number"],
                po["expected_amount"],
                po["currency"],
                po["iban"],
            ),
            "template": 2,
            "quality": "NORMAL",
        }
    )

    scenarios.append(
        {
            "file_name": "invoice_12_high_value.pdf",
            "scenario": "HIGH_VALUE",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Invoice matches the PO but exceeds the EUR 10,000 auto-approval limit.",
            "expected_issues": ["HIGH_VALUE"],
            "invoice": make_invoice(
                "INV-012",
                high_value_po["supplier_name"],
                high_value_po["vat_number"],
                high_value_po["po_number"],
                high_value_po["expected_amount"],
                high_value_po["currency"],
                high_value_po["iban"],
            ),
            "template": 0,
            "quality": "NORMAL",
        }
    )

    po = bad_quality_baseline
    scenarios.append(
        {
            "file_name": "invoice_13_bad_quality.pdf",
            "scenario": "BAD_QUALITY",
            "expected_result": "MANUAL_REVIEW",
            "reason": "Document is image-based and intentionally degraded for OCR/confidence testing.",
            "expected_issues": ["LOW_DOCUMENT_QUALITY"],
            "invoice": make_invoice(
                "INV-013",
                po["supplier_name"],
                po["vat_number"],
                po["po_number"],
                po["expected_amount"],
                po["currency"],
                po["iban"],
            ),
            "template": 1,
            "quality": "BAD_SCAN",
        }
    )

    po = valid_pos[5]
    scenarios.append(
        {
            "file_name": "invoice_14_valid.pdf",
            "scenario": "VALID",
            "expected_result": "AUTO_PROCESS",
            "reason": "Second valid-template test case.",
            "expected_issues": [],
            "invoice": make_invoice(
                "INV-014",
                po["supplier_name"],
                po["vat_number"],
                po["po_number"],
                po["expected_amount"],
                po["currency"],
                po["iban"],
            ),
            "template": 2,
            "quality": "NORMAL",
        }
    )

    second_duplicate = duplicate_invoice.copy()
    scenarios.append(
        {
            "file_name": "invoice_15_duplicate.pdf",
            "scenario": "DUPLICATE",
            "expected_result": "REJECT",
            "reason": "Repeated historical invoice number in a second document layout.",
            "expected_issues": ["DUPLICATE_INVOICE"],
            "invoice": second_duplicate,
            "template": 2,
            "quality": "NORMAL",
        }
    )

    multi_review_invoice = make_invoice(
        "INV-016",
        multi_review_po["supplier_name"],
        "",
        multi_review_po["po_number"],
        multi_review_po["expected_amount"],
        "USD",
        multi_review_po["iban"],
    )
    scenarios.append(
        {
            "file_name": "invoice_16_multi_review.pdf",
            "scenario": "MULTI_FAULT_REVIEW",
            "expected_result": "MANUAL_REVIEW",
            "reason": (
                "Multiple applicable findings: VAT is missing, invoice currency "
                "does not match the PO, and total exceeds the EUR 10,000 "
                "auto-approval limit."
            ),
            "expected_issues": ["MISSING_VAT", "WRONG_CURRENCY", "HIGH_VALUE"],
            "invoice": multi_review_invoice,
            "template": 0,
            "quality": "NORMAL",
        }
    )

    multi_reject_invoice = make_invoice(
        duplicate["invoice_number"],
        duplicate["supplier_name"],
        duplicate["vat_number"],
        duplicate["po_number"],
        duplicate["invoice_amount"] * 1.08,
        "USD",
        duplicate["iban"],
    )
    scenarios.append(
        {
            "file_name": "invoice_17_multi_reject.pdf",
            "scenario": "MULTI_FAULT_REJECT",
            "expected_result": "REJECT",
            "reason": (
                "Duplicate protection determines the final REJECT route; amount "
                "and currency mismatches must also be recorded."
            ),
            "expected_issues": [
                "DUPLICATE_INVOICE",
                "AMOUNT_MISMATCH",
                "WRONG_CURRENCY",
            ],
            "invoice": multi_reject_invoice,
            "template": 1,
            "quality": "NORMAL",
        }
    )

    audit_scenarios(connection, scenarios)
    return scenarios


def get_business_issues(connection, scenario):
    invoice = scenario["invoice"]
    issues = []

    if not invoice["vat_number"]:
        issues.append("MISSING_VAT")

    supplier = None
    if invoice["vat_number"]:
        supplier = connection.execute(
            "SELECT * FROM Suppliers WHERE vat_number = ?;",
            (invoice["vat_number"],),
        ).fetchone()
        if supplier is None:
            issues.append("UNKNOWN_SUPPLIER")

    if connection.execute(
        "SELECT 1 FROM HistoricalInvoices WHERE invoice_number = ? LIMIT 1;",
        (invoice["invoice_number"],),
    ).fetchone():
        issues.append("DUPLICATE_INVOICE")

    po = connection.execute(
        "SELECT * FROM PurchaseOrders WHERE po_number = ?;",
        (invoice["po_number"],),
    ).fetchone()

    if po is None:
        issues.append("MISSING_PO")
    else:
        if invoice["currency"] != po["currency"]:
            issues.append("WRONG_CURRENCY")

        difference = abs(invoice["total_amount"] - po["expected_amount"])
        if po["expected_amount"] > 0 and difference / po["expected_amount"] > PO_TOLERANCE:
            issues.append("AMOUNT_MISMATCH")

        if supplier is not None and supplier["supplier_id"] != po["supplier_id"]:
            issues.append("SUPPLIER_PO_MISMATCH")

    if invoice["total_amount"] > AUTO_APPROVAL_LIMIT:
        issues.append("HIGH_VALUE")

    if scenario["quality"] == "BAD_SCAN":
        issues.append("LOW_DOCUMENT_QUALITY")

    return issues


def audit_scenarios(connection, scenarios):
    if len(scenarios) != 17:
        raise AssertionError(f"Expected 17 scenarios, found {len(scenarios)}")

    file_names = [scenario["file_name"] for scenario in scenarios]
    if len(file_names) != len(set(file_names)):
        raise AssertionError("Scenario file names are not unique.")

    isolated_scenarios = {
        "VALID",
        "MISSING_PO",
        "UNKNOWN_SUPPLIER",
        "AMOUNT_MISMATCH",
        "WRONG_CURRENCY",
        "MISSING_VAT",
        "HIGH_VALUE",
        "BAD_QUALITY",
    }
    isolated_po_numbers = [
        scenario["invoice"]["po_number"]
        for scenario in scenarios
        if scenario["scenario"] in isolated_scenarios
        and scenario["scenario"] != "MISSING_PO"
    ]
    if len(isolated_po_numbers) != len(set(isolated_po_numbers)):
        raise AssertionError("Isolated scenarios reuse a PO unexpectedly.")

    for scenario in scenarios:
        actual_issues = get_business_issues(connection, scenario)
        expected_issues = scenario["expected_issues"]
        if set(actual_issues) != set(expected_issues):
            raise AssertionError(
                f"{scenario['file_name']} issue mismatch: "
                f"expected {expected_issues}, calculated {actual_issues}"
            )


def draw_template_standard(pdf, invoice):
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, 790, "INVOICE")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 760, f"Supplier: {invoice['supplier_name']}")
    pdf.drawString(50, 744, f"VAT number: {invoice['vat_number']}")
    pdf.drawString(50, 728, f"IBAN: {invoice['iban']}")

    pdf.drawString(360, 760, f"Invoice: {invoice['invoice_number']}")
    pdf.drawString(360, 744, f"Date: {invoice['invoice_date']}")
    pdf.drawString(360, 728, f"Due: {invoice['due_date']}")

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
    pdf.drawString(60, y, f"Net amount: {invoice['net_amount']:.2f} {invoice['currency']}")
    pdf.drawString(60, y - 22, f"VAT: {invoice['vat_amount']:.2f} {invoice['currency']}")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(60, y - 55, f"Total: {invoice['total_amount']:.2f} {invoice['currency']}")


def draw_template_table(pdf, invoice):
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(50, 790, "SUPPLIER INVOICE")
    pdf.setFont("Helvetica", 10)

    pdf.drawString(50, 755, invoice["supplier_name"])
    pdf.drawString(50, 739, f"VAT: {invoice['vat_number']}")
    pdf.drawString(50, 723, f"IBAN: {invoice['iban']}")
    pdf.drawRightString(540, 755, f"No. {invoice['invoice_number']}")
    pdf.drawRightString(540, 739, invoice["invoice_date"])
    pdf.drawRightString(540, 723, f"Due {invoice['due_date']}")

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
    pdf.drawString(420, y - 60, f"{invoice['total_amount']:.2f} {invoice['currency']}")


def create_clean_pdf(path, invoice, template):
    pdf = canvas.Canvas(str(path), pagesize=A4)
    if template == 0:
        draw_template_standard(pdf, invoice)
    elif template == 1:
        draw_template_compact(pdf, invoice)
    else:
        draw_template_table(pdf, invoice)
    pdf.save()


def degrade_pdf_to_scan(source_pdf_path, output_pdf_path):
    """Convert a clean digital PDF into a realistic image-only degraded scan."""
    document = fitz.open(source_pdf_path)
    try:
        page = document[0]
        pix = page.get_pixmap(dpi=115, alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")

        image = image.rotate(1.0, expand=True, fillcolor=255)
        image = image.filter(ImageFilter.GaussianBlur(radius=0.65))

        downscaled = image.resize(
            (max(1, int(image.width * 0.82)), max(1, int(image.height * 0.82))),
            Image.Resampling.BILINEAR,
        )
        image = downscaled.resize(image.size, Image.Resampling.BILINEAR)
        image = ImageEnhance.Contrast(image).enhance(0.82)
        image = ImageEnhance.Brightness(image).enhance(0.97)

        noise = Image.effect_noise(image.size, 8).convert("L")
        image = Image.blend(image, noise, 0.04)

        image = image.convert("RGB")
        image.save(output_pdf_path, "PDF", resolution=100.0)
    finally:
        document.close()


def create_pdf(path, invoice, template, quality):
    if quality != "BAD_SCAN":
        create_clean_pdf(path, invoice, template)
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        clean_path = Path(temp_dir) / "clean_invoice.pdf"
        create_clean_pdf(clean_path, invoice, template)
        degrade_pdf_to_scan(clean_path, path)


def write_manifest(scenarios):
    fields = [
        "file_name",
        "scenario",
        "expected_result",
        "expected_issues",
        "reason",
        "invoice_number",
        "supplier_name",
        "vat_number",
        "po_number",
        "total_amount",
        "currency",
    ]

    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for scenario in scenarios:
            invoice = scenario["invoice"]
            writer.writerow(
                {
                    "file_name": scenario["file_name"],
                    "scenario": scenario["scenario"],
                    "expected_result": scenario["expected_result"],
                    "expected_issues": "|".join(scenario["expected_issues"]),
                    "reason": scenario["reason"],
                    "invoice_number": invoice["invoice_number"],
                    "supplier_name": invoice["supplier_name"],
                    "vat_number": invoice["vat_number"],
                    "po_number": invoice["po_number"],
                    "total_amount": f"{invoice['total_amount']:.2f}",
                    "currency": invoice["currency"],
                }
            )


def clear_old_test_files():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_file in OUTPUT_DIR.glob("*.pdf"):
        pdf_file.unlink()
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()


def verify_generated_outputs(scenarios):
    expected_names = {scenario["file_name"] for scenario in scenarios}
    actual_names = {path.name for path in OUTPUT_DIR.glob("*.pdf")}

    if actual_names != expected_names:
        raise AssertionError(
            f"Generated PDF set mismatch. Expected {sorted(expected_names)}, "
            f"found {sorted(actual_names)}"
        )

    if not MANIFEST_PATH.exists():
        raise AssertionError("Scenario manifest was not generated.")

    for scenario in scenarios:
        path = OUTPUT_DIR / scenario["file_name"]
        document = fitz.open(path)
        try:
            if len(document) != 1:
                raise AssertionError(f"{path.name} should contain exactly one page.")

            page = document[0]
            text = page.get_text().strip()

            if scenario["quality"] == "BAD_SCAN":
                if text:
                    raise AssertionError(
                        f"{path.name} still contains an extractable digital text layer."
                    )
                images = page.get_images(full=True)
                if not images:
                    raise AssertionError(
                        f"{path.name} is expected to be image-based but contains no page image."
                    )
            else:
                if not text:
                    raise AssertionError(f"{path.name} unexpectedly has no extractable text.")
                invoice_number = scenario["invoice"]["invoice_number"]
                if invoice_number not in text:
                    raise AssertionError(
                        f"{path.name} does not contain expected invoice number {invoice_number}."
                    )
        finally:
            document.close()

    print("Generated-output verification passed for all 17 PDFs.")


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}. Run generate_data.py first."
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
        verify_generated_outputs(scenarios)
    finally:
        connection.close()

    print("Test invoice generation completed successfully.")
    print(f"PDF invoices: {len(scenarios)}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(f"Scenario manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
