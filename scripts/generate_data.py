import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "invoice_automation.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

random.seed(42)


SUPPLIERS = [
    (1, "Nordic Pumps Oy", "FI12345678", "FI2112345600000785", "ACTIVE", "LOW"),
    (2, "Arctic Industrial Systems Oy", "FI23456789", "FI4212345600000786", "ACTIVE", "LOW"),
    (3, "Baltic Components Oy", "FI34567890", "FI6312345600000787", "ACTIVE", "MEDIUM"),
    (4, "Lakeside Engineering Oy", "FI45678901", "FI8412345600000788", "ACTIVE", "LOW"),
    (5, "Polar Automation Oy", "FI56789012", "FI0512345600000789", "ACTIVE", "LOW"),
    (6, "Northern Steelworks Oy", "FI67890123", "FI2612345600000790", "ACTIVE", "MEDIUM"),
    (7, "Aurora Maintenance Oy", "FI78901234", "FI4712345600000791", "ACTIVE", "LOW"),
    (8, "FinnTech Supplies Oy", "FI89012345", "FI6812345600000792", "ACTIVE", "LOW"),
    (9, "Saimaa Logistics Oy", "FI90123456", "FI8912345600000793", "ACTIVE", "MEDIUM"),
    (10, "Lapland Electrical Oy", "FI11223344", "FI1012345600000794", "ACTIVE", "LOW"),
    (11, "BlueRiver Controls Oy", "FI22334455", "FI3112345600000795", "ACTIVE", "LOW"),
    (12, "Precision Mechanics Oy", "FI33445566", "FI5212345600000796", "ACTIVE", "MEDIUM"),
    (13, "Industrial Flow Oy", "FI44556677", "FI7312345600000797", "ACTIVE", "LOW"),
    (14, "West Coast Hydraulics Oy", "FI55667788", "FI9412345600000798", "ACTIVE", "HIGH"),
    (15, "Eastern Process Solutions Oy", "FI66778899", "FI1512345600000799", "ACTIVE", "LOW"),
    (16, "Core Automation Oy", "FI77889900", "FI3612345600000800", "ACTIVE", "LOW"),
    (17, "Metro Technical Services Oy", "FI88990011", "FI5712345600000801", "ACTIVE", "MEDIUM"),
    (18, "Prime Industrial Parts Oy", "FI99001122", "FI7812345600000802", "ACTIVE", "LOW"),
    (19, "Legacy Manufacturing Oy", "FI10101010", "FI9912345600000803", "INACTIVE", "HIGH"),
    (20, "NorthStar Process Oy", "FI20202020", "FI2012345600000804", "ACTIVE", "LOW"),
]


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    is_new_database = not DB_PATH.exists()

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON;")

    if is_new_database:
        if not SCHEMA_PATH.exists():
            connection.close()
            raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    return connection


def clear_existing_data(connection):
    cursor = connection.cursor()

    cursor.execute("DELETE FROM AutomationLog;")
    cursor.execute("DELETE FROM HistoricalInvoices;")
    cursor.execute("DELETE FROM PurchaseOrders;")
    cursor.execute("DELETE FROM Suppliers;")

    connection.commit()


def insert_suppliers(connection):
    connection.executemany(
        """
        INSERT INTO Suppliers (
            supplier_id,
            supplier_name,
            vat_number,
            iban,
            status,
            risk_level
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        SUPPLIERS,
    )


def generate_purchase_orders():
    active_suppliers = [
        supplier for supplier in SUPPLIERS
        if supplier[4] == "ACTIVE"
    ]

    purchase_orders = []

    for i in range(1, 31):
        supplier = random.choice(active_suppliers)

        purchase_orders.append(
            (
                f"PO-{1000 + i}",
                supplier[0],
                round(random.uniform(500, 15000), 2),
                random.choice(["EUR", "EUR", "EUR", "SEK", "USD"]),
                random.choice(["OPEN", "OPEN", "OPEN", "CLOSED"]),
            )
        )

    return purchase_orders


def insert_purchase_orders(connection, purchase_orders):
    connection.executemany(
        """
        INSERT INTO PurchaseOrders (
            po_number,
            supplier_id,
            expected_amount,
            currency,
            status
        )
        VALUES (?, ?, ?, ?, ?);
        """,
        purchase_orders,
    )


def generate_historical_invoices(purchase_orders):
    historical_invoices = []
    start_date = date.today() - timedelta(days=180)
    invoice_id = 1

    pos_by_supplier = {}

    for po in purchase_orders:
        supplier_id = po[1]
        pos_by_supplier.setdefault(supplier_id, []).append(po)

    for supplier_id, supplier_pos in pos_by_supplier.items():
        invoice_count = random.randint(2, 4)

        for _ in range(invoice_count):
            po = random.choice(supplier_pos)

            po_number = po[0]
            expected_amount = po[2]

            variation = random.uniform(0.97, 1.03)
            invoice_amount = round(expected_amount * variation, 2)

            invoice_date = start_date + timedelta(
                days=random.randint(0, 180)
            )

            status = random.choices(
                ["PAID", "PENDING", "REJECTED"],
                weights=[0.75, 0.20, 0.05],
                k=1,
            )[0]

            historical_invoices.append(
                (
                    invoice_id,
                    f"HIST-{1000 + invoice_id}",
                    supplier_id,
                    po_number,
                    invoice_amount,
                    invoice_date.isoformat(),
                    status,
                )
            )

            invoice_id += 1

    return historical_invoices


def insert_historical_invoices(connection, historical_invoices):
    connection.executemany(
        """
        INSERT INTO HistoricalInvoices (
            invoice_id,
            invoice_number,
            supplier_id,
            po_number,
            invoice_amount,
            invoice_date,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        historical_invoices,
    )


def print_summary(connection):
    cursor = connection.cursor()

    tables = [
        "Suppliers",
        "PurchaseOrders",
        "HistoricalInvoices",
        "AutomationLog",
    ]

    print("\nSample data generation completed successfully.")
    print(f"Database: {DB_PATH}\n")

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        print(f"{table}: {count} rows")


def main():
    print("Generating sample invoice-processing data...")

    connection = connect_db()

    try:
        clear_existing_data(connection)

        insert_suppliers(connection)

        purchase_orders = generate_purchase_orders()
        insert_purchase_orders(connection, purchase_orders)

        historical_invoices = generate_historical_invoices(purchase_orders)
        insert_historical_invoices(connection, historical_invoices)

        connection.commit()
        print_summary(connection)

    except Exception as error:
        connection.rollback()
        print(f"\nData generation failed: {error}")
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()