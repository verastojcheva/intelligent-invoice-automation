import re
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "invoice_automation.db"


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


connection = sqlite3.connect(DB_PATH)

try:
    suppliers = connection.execute(
        "SELECT supplier_id, iban FROM Suppliers;"
    ).fetchall()

    for supplier_id, old_iban in suppliers:
        new_iban = make_valid_finnish_iban(old_iban)

        connection.execute(
            "UPDATE Suppliers SET iban = ? WHERE supplier_id = ?;",
            (new_iban, supplier_id),
        )

        print(f"{supplier_id}: {old_iban} -> {new_iban}")

    connection.commit()
    print("Supplier IBANs updated successfully.")

finally:
    connection.close()