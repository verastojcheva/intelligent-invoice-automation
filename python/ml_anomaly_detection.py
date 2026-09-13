import sqlite3

import numpy as np
from sklearn.ensemble import IsolationForest


MIN_HISTORY_COUNT = 4


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


def run_isolation_forest(
    current_amount: float,
    historical_amounts: list[float],
) -> dict:
    result = {
        "isMlAnomaly": False,
        "mlAnomalyScore": 0.0,
        "historyCount": len(historical_amounts),
        "issues": [],
    }

    if current_amount is None or current_amount <= 0:
        result["issues"].append(
            "ML_ANOMALY_INVALID_AMOUNT"
        )
        return result

    if len(historical_amounts) < MIN_HISTORY_COUNT:
        result["issues"].append(
            "ML_ANOMALY_INSUFFICIENT_HISTORY"
        )
        return result

    training_data = np.array(
        historical_amounts,
        dtype=float,
    ).reshape(-1, 1)

    model = IsolationForest(
        contamination="auto",
        random_state=42,
    )

    model.fit(training_data)

    current_data = np.array(
        [[current_amount]],
        dtype=float,
    )

    prediction = model.predict(current_data)[0]

    decision_score = model.decision_function(
        current_data
    )[0]

    result["mlAnomalyScore"] = round(
        float(decision_score),
        4,
    )

    if prediction == -1:
        result["isMlAnomaly"] = True
        result["issues"].append(
            "ML_UNUSUAL_INVOICE_AMOUNT"
        )

    return result


def analyze_invoice_ml(
    database_path: str,
    vat_number: str,
    amount,
) -> dict:
    try:
        current_amount = float(amount)

    except (TypeError, ValueError):
        return {
            "isMlAnomaly": False,
            "mlAnomalyScore": 0.0,
            "historyCount": 0,
            "issues": [
                "ML_ANOMALY_INVALID_AMOUNT"
            ],
        }

    historical_amounts = (
        get_supplier_historical_amounts(
            database_path,
            vat_number,
        )
    )

    return run_isolation_forest(
        current_amount,
        historical_amounts,
    )


def analyze_invoice_ml_for_uipath(
    database_path,
    vat_number,
    amount,
) -> list[str]:
    try:
        result = analyze_invoice_ml(
            str(database_path),
            str(vat_number)
            if vat_number
            else "",
            amount,
        )

    except Exception as exc:
        result = {
            "isMlAnomaly": False,
            "mlAnomalyScore": 0.0,
            "historyCount": 0,
            "issues": [
                f"ML_ANOMALY_ERROR:{type(exc).__name__}"
            ],
        }

    return [
        str(result["isMlAnomaly"]),
        str(result["mlAnomalyScore"]),
        str(result["historyCount"]),
        "|".join(result["issues"]),
    ]


if __name__ == "__main__":
    test_history = [
        12141.92,
        12490.66,
        11982.30,
        12260.36,
        12050.00,
        12310.00,
    ]

    print(
        run_isolation_forest(
            15000.00,
            test_history,
        )
    )

    print(
        run_isolation_forest(
            12200.00,
            test_history,
        )
    )