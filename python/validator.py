import math
import re
from datetime import datetime
from typing import Optional


WEIGHTS = {
    "MISSING_VAT": 20,
    "INVALID_VAT_FORMAT": 20,
    "MISSING_INVOICE_NUMBER": 30,
    "INVALID_INVOICE_NUMBER_FORMAT": 15,
    "MISSING_AMOUNT": 30,
    "INVALID_AMOUNT": 30,
    "MISSING_INVOICE_DATE": 10,
    "INVALID_INVOICE_DATE": 10,
    "MISSING_IBAN": 30,
    "INVALID_IBAN": 30,
    "MISSING_CURRENCY": 20,
    "INVALID_CURRENCY_FORMAT": 20,
}


ACCEPTED_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
]


def normalize_vat(raw) -> str:
    text = str(raw or "").upper()
    compact = re.sub(r"[^A-Z0-9]", "", text)

    match = re.search(r"FI\d{8}", compact)

    return match.group(0) if match else compact


def normalize_iban(raw) -> str:
    text = str(raw or "").upper()
    compact = re.sub(r"[^A-Z0-9]", "", text)

    match = re.search(r"FI\d{16}", compact)

    return match.group(0) if match else compact


def validate_finnish_iban(iban: str) -> bool:
    iban = normalize_iban(iban)

    if not iban:
        return False

    if not re.fullmatch(r"FI\d{16}", iban):
        return False

    rearranged = iban[4:] + iban[:4]

    numeric_iban = "".join(
        char if char.isdigit()
        else str(ord(char) - 55)
        for char in rearranged
    )

    return int(numeric_iban) % 97 == 1


def parse_amount(raw) -> Optional[float]:
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) else None

    text = str(raw).strip()

    if not text:
        return None

    text = re.sub(r"[^\d,.\-]", "", text)

    if not text:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    elif "," in text:
        whole, _, fraction = text.rpartition(",")

        if (
            1 <= len(fraction) <= 2
            and whole.count(",") == 0
        ):
            text = f"{whole}.{fraction}"
        else:
            text = text.replace(",", "")

    try:
        value = float(text)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


def check_vat(invoice: dict) -> Optional[str]:
    raw_vat = invoice.get("vat")

    if raw_vat is None or not str(raw_vat).strip():
        return "MISSING_VAT"

    vat = normalize_vat(raw_vat)

    if not re.fullmatch(r"FI\d{8}", vat):
        return "INVALID_VAT_FORMAT"

    return None


def check_invoice_number(invoice: dict) -> Optional[str]:
    invoice_number = str(
        invoice.get("invoiceNumber", "")
    ).strip()

    if not invoice_number:
        return "MISSING_INVOICE_NUMBER"

    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9\-_/]*",
        invoice_number,
    ):
        return "INVALID_INVOICE_NUMBER_FORMAT"

    return None


def check_amount(invoice: dict) -> Optional[str]:
    raw_amount = invoice.get("amount")

    if raw_amount is None:
        return "MISSING_AMOUNT"

    amount = parse_amount(raw_amount)

    if amount is None or amount <= 0:
        return "INVALID_AMOUNT"

    return None


def check_invoice_date(invoice: dict) -> Optional[str]:
    invoice_date = str(
        invoice.get("invoiceDate", "")
    ).strip()

    if not invoice_date:
        return "MISSING_INVOICE_DATE"

    for date_format in ACCEPTED_DATE_FORMATS:
        try:
            datetime.strptime(
                invoice_date,
                date_format,
            )
            return None

        except ValueError:
            continue

    return "INVALID_INVOICE_DATE"


def check_iban(invoice: dict) -> Optional[str]:
    raw_iban = invoice.get("iban")

    if raw_iban is None or not str(raw_iban).strip():
        return "MISSING_IBAN"

    if not validate_finnish_iban(raw_iban):
        return "INVALID_IBAN"

    return None


def check_currency(invoice: dict) -> Optional[str]:
    currency = str(
        invoice.get("currency", "")
    ).strip().upper()

    if not currency:
        return "MISSING_CURRENCY"

    if not re.fullmatch(r"[A-Z]{3}", currency):
        return "INVALID_CURRENCY_FORMAT"

    return None


CHECKS = [
    check_vat,
    check_invoice_number,
    check_amount,
    check_invoice_date,
    check_iban,
    check_currency,
]


def validate_invoice(invoice: dict) -> dict:
    issues = [
        issue
        for issue in (
            check(invoice)
            for check in CHECKS
        )
        if issue
    ]

    risk_score = min(
        sum(
            WEIGHTS[issue]
            for issue in issues
        ),
        100,
    )

    return {
        "valid": len(issues) == 0,
        "riskScore": risk_score,
        "issues": issues,
    }


def validate_invoice_for_uipath(
    supplier,
    vat,
    amount,
    po,
    invoice_number,
    invoice_date,
    currency,
    iban,
) -> list[str]:

    invoice = {
        "supplier": supplier,
        "vat": vat,
        "amount": amount,
        "po": po,
        "invoiceNumber": invoice_number,
        "invoiceDate": invoice_date,
        "currency": currency,
        "iban": iban,
    }
    
    print("DEBUG IBAN:", repr(invoice.get("iban")))

    result = validate_invoice(invoice)

    return [
        str(result["valid"]),
        str(result["riskScore"]),
        "|".join(result["issues"]),
    ]


if __name__ == "__main__":
    clean_invoice = {
        "supplier": "Nordic Pumps Oy",
        "vat": "FI12345678",
        "amount": 4250.00,
        "po": "PO-1045",
        "invoiceNumber": "INV-001",
        "invoiceDate": "2026-09-01",
        "currency": "EUR",
        "iban": "FI2112345600000785",
    }

    noisy_invoice = {
        "supplier": "Nordic Pumps Oy",
        "vat": "VAT: FI12345678",
        "amount": "862,66",
        "po": "PO-1045",
        "invoiceNumber": "INV-001",
        "invoiceDate": "2026-09-01",
        "currency": "EUR",
        "iban": "IBAN: FI21 1234 5600 0007 85",
    }

    print(
        "Clean:",
        validate_invoice(clean_invoice),
    )

    print(
        "Noisy:",
        validate_invoice(noisy_invoice),
    )