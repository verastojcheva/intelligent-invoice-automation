from flask import Flask, render_template_string, request

import sqlite3
from datetime import datetime
from pathlib import Path


app = Flask(__name__)
DATABASE_PATH = Path(__file__).resolve().parent.parent / "database" / "invoice_automation.db"

PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Invoice Manual Review</title>
</head>
<body>

    <h2>Manual Invoice Review</h2>

    {% if not invoice_number %}
        <p>No invoice loaded.</p>
    {% else %}

        <h3>Invoice Details</h3>

        <p><strong>Invoice number:</strong> {{ invoice_number }}</p>
        <p><strong>Supplier:</strong> {{ supplier }}</p>
        <p><strong>PO number:</strong> {{ po_number }}</p>
        <p><strong>Amount:</strong> {{ amount }} {{ currency }}</p>
        <p><strong>VAT:</strong> {{ vat }}</p>

        <h3>Issues Detected</h3>

        {% if issues %}
            <ul>
                {% for issue in issues %}
                    <li>{{ issue }}</li>
                {% endfor %}
            </ul>
        {% else %}
            <p>None</p>
        {% endif %}

        <h3>Checks Skipped</h3>

        {% if skipped_checks %}
            <ul>
                {% for check in skipped_checks %}
                    <li>{{ check }}</li>
                {% endfor %}
            </ul>
        {% else %}
            <p>None</p>
        {% endif %}

        <form method="post">

            <input type="hidden" name="invoiceNumber" value="{{ invoice_number }}">
            <input type="hidden" name="decision" value="APPROVED">

            <button type="submit">Approve</button>

        </form>

        <form method="post">

            <input type="hidden" name="invoiceNumber" value="{{ invoice_number }}">
            <input type="hidden" name="decision" value="REJECTED">

            <button type="submit">Reject</button>

        </form>

    {% endif %}

    {% if decision %}
        <h3>Review Result</h3>
        <p>Invoice {{ invoice_number }}: {{ decision }}</p>
    {% endif %}

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def manual_review():

    invoice_number = request.args.get("invoiceNumber", "")
    supplier = request.args.get("supplier", "")
    po_number = request.args.get("poNumber", "")
    amount = request.args.get("amount", "")
    currency = request.args.get("currency", "")
    vat = request.args.get("vat", "")

    issues_raw = request.args.get("issues", "")
    skipped_raw = request.args.get("skippedChecks", "")

    issues = [
        item
        for item in issues_raw.split("|")
        if item
    ]

    skipped_checks = [
        item
        for item in skipped_raw.split("|")
        if item
    ]

    decision = ""

    if request.method == "POST":
        invoice_number = request.form.get("invoiceNumber", "")
        decision = request.form.get("decision", "")

        review_reference = request.args.get("reviewReference", "")

        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ManualReviews
                (
                    review_reference,
                    invoice_number,
                    decision,
                    reviewed_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    review_reference,
                    invoice_number,
                    decision,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    return render_template_string(
        PAGE,
        invoice_number=invoice_number,
        supplier=supplier,
        po_number=po_number,
        amount=amount,
        currency=currency,
        vat=vat,
        issues=issues,
        skipped_checks=skipped_checks,
        decision=decision,
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5001,
        debug=False,
    )