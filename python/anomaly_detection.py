import importlib.util
import sqlite3
import statistics
from pathlib import Path
from typing import Optional


MIN_HISTORY_COUNT = 3
ROBUST_Z_THRESHOLD = 3.5
ZERO_MAD_DEVIATION_THRESHOLD = 0.50


def get_parse_amount(database_path: str):
    project_root = Path(database_path).resolve().parent.parent
    validator_path = project_root / "python" / "validator.py"

    spec = importlib.util.spec_from_file_location(
        "invoice_validator",
        validator_path,
    )

    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load validator.py from {validator_path}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.parse_amount


def get_supplier_historical_amounts(
    database_path: str,
    vat_number: str,
) -> list[float]:
    if not vat_number:
        return []

    connection = sqlite3.connect(database_path)

    try:
        rows = connection.execute(
            """
            SELECT h.invoice_amount
            FROM HistoricalInvoices h
            JOIN Suppliers s
                ON h.supplier_id = s.supplier_id
            WHERE s.vat_number = ?
              AND h.status = 'PAID'
              AND h.invoice_amount IS NOT NULL
              AND h.invoice_amount > 0
            ORDER BY h.invoice_date;
            """,
            (vat_number,),
        ).fetchall()

        return [float(row[0]) for row in rows]

    finally:
        connection.close()


def calculate_median_absolute_deviation(
    values: list[float],
    median_value: float,
) -> float:
    deviations = [
        abs(value - median_value)
        for value in values
    ]

    return statistics.median(deviations)


def analyze_amount_anomaly(
    current_amount: Optional[float],
    historical_amounts: list[float],
) -> dict:
    result = {
        "isAnomaly": False,
        "anomalyScore": 0.0,
        "historyCount": len(historical_amounts),
        "historicalMedian": 0.0,
        "mad": 0.0,
        "issues": [],
    }

    if current_amount is None or current_amount <= 0:
        result["issues"].append("ANOMALY_CHECK_INVALID_AMOUNT")
        return result

    if len(historical_amounts) < MIN_HISTORY_COUNT:
        result["issues"].append("ANOMALY_CHECK_INSUFFICIENT_HISTORY")
        return result

    historical_median = statistics.median(historical_amounts)

    mad = calculate_median_absolute_deviation(
        historical_amounts,
        historical_median,
    )

    result["historicalMedian"] = round(historical_median, 2)
    result["mad"] = round(mad, 2)

    if mad > 0:
        robust_z_score = (
            0.6745
            * abs(current_amount - historical_median)
            / mad
        )

        result["anomalyScore"] = round(robust_z_score, 2)

        if robust_z_score >= ROBUST_Z_THRESHOLD:
            result["isAnomaly"] = True
            result["issues"].append("UNUSUAL_INVOICE_AMOUNT")

        return result

    if historical_median <= 0:
        result["issues"].append("ANOMALY_CHECK_INVALID_HISTORY")
        return result

    percentage_difference = (
        abs(current_amount - historical_median)
        / historical_median
    )

    result["anomalyScore"] = round(
        percentage_difference,
        2,
    )

    if percentage_difference >= ZERO_MAD_DEVIATION_THRESHOLD:
        result["isAnomaly"] = True
        result["issues"].append("UNUSUAL_INVOICE_AMOUNT")

    return result


def analyze_invoice_anomaly(
    database_path: str,
    vat_number: str,
    amount,
) -> dict:
    parse_amount = get_parse_amount(database_path)
    parsed_amount = parse_amount(amount)

    historical_amounts = get_supplier_historical_amounts(
        database_path,
        vat_number,
    )

    result = analyze_amount_anomaly(
        parsed_amount,
        historical_amounts,
    )

    if parsed_amount is None:
        result["issues"] = [
            "ANOMALY_CHECK_UNPARSEABLE_AMOUNT"
        ]

    return result


def analyze_invoice_anomaly_for_uipath(
    database_path,
    vat_number,
    amount,
) -> list[str]:
    try:
        result = analyze_invoice_anomaly(
            str(database_path),
            str(vat_number) if vat_number else "",
            amount,
        )

    except Exception as exc:
        result = {
            "isAnomaly": False,
            "anomalyScore": 0.0,
            "historyCount": 0,
            "historicalMedian": 0.0,
            "mad": 0.0,
            "issues": [
                f"ANOMALY_CHECK_ERROR:{type(exc).__name__}"
            ],
        }

    return [
        str(result["isAnomaly"]),
        str(result["anomalyScore"]),
        str(result["historyCount"]),
        str(result["historicalMedian"]),
        str(result["mad"]),
        "|".join(result["issues"]),
    ]


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATABASE_PATH = BASE_DIR / "database" / "invoice_automation.db"

    print(
        analyze_invoice_anomaly(
            str(DATABASE_PATH),
            "FI12345678",
            5000.00,
        )
    )