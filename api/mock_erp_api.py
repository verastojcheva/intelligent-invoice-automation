from datetime import datetime
from flask import Flask, jsonify, request


app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "mock-erp-api",
        }
    )


@app.route("/api/invoices", methods=["POST"])
def create_invoice():
    data = request.get_json(silent=True)

    if not data:
        return jsonify(
            {
                "success": False,
                "error": "INVALID_JSON",
            }
        ), 400

    required_fields = [
        "invoiceNumber",
        "supplierName",
        "poNumber",
        "totalAmount",
        "currency",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in data
        or data[field] in (None, "")
    ]

    if missing_fields:
        return jsonify(
            {
                "success": False,
                "error": "MISSING_REQUIRED_FIELDS",
                "missingFields": missing_fields,
            }
        ), 400

    try:
        total_amount = float(data["totalAmount"])

    except (TypeError, ValueError):
        return jsonify(
            {
                "success": False,
                "error": "INVALID_AMOUNT",
            }
        ), 400

    if total_amount <= 0:
        return jsonify(
            {
                "success": False,
                "error": "INVALID_AMOUNT",
            }
        ), 400

    erp_reference = (
        "ERP-"
        + str(data["invoiceNumber"])
        + "-"
        + datetime.now().strftime("%Y%m%d%H%M%S")
    )

    return jsonify(
        {
            "success": True,
            "erpReference": erp_reference,
            "invoiceNumber": data["invoiceNumber"],
            "status": "POSTED",
        }
    ), 201


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )