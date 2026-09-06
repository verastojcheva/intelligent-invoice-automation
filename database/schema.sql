PRAGMA foreign_keys = ON;

CREATE TABLE Suppliers (
    supplier_id     INTEGER PRIMARY KEY,
    supplier_name   TEXT NOT NULL,
    vat_number      TEXT UNIQUE NOT NULL,
    iban            TEXT,
    status          TEXT NOT NULL
                    CHECK (status IN ('ACTIVE', 'INACTIVE')),
    risk_level      TEXT NOT NULL
                    CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH'))
);


CREATE TABLE PurchaseOrders (
    po_number       TEXT PRIMARY KEY,
    supplier_id     INTEGER NOT NULL,
    expected_amount REAL NOT NULL
                    CHECK (expected_amount >= 0),
    currency        TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('OPEN', 'CLOSED')),

    FOREIGN KEY (supplier_id)
        REFERENCES Suppliers(supplier_id)
);

CREATE TABLE HistoricalInvoices (
    invoice_id      INTEGER PRIMARY KEY,
    invoice_number  TEXT NOT NULL,
    supplier_id     INTEGER NOT NULL,
    po_number       TEXT,
    invoice_amount  REAL NOT NULL
                    CHECK (invoice_amount >= 0),
    invoice_date    TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('PAID', 'PENDING', 'REJECTED')),

    FOREIGN KEY (supplier_id)
        REFERENCES Suppliers(supplier_id),

    FOREIGN KEY (po_number)
        REFERENCES PurchaseOrders(po_number)
);


CREATE TABLE AutomationLog (
    transaction_id      TEXT PRIMARY KEY,
    invoice_number      TEXT,
    timestamp           TEXT NOT NULL,

    status              TEXT NOT NULL
                        CHECK (
                            status IN (
                                'SUCCESS',
                                'REVIEW',
                                'REJECTED',
                                'BUSINESS_EXCEPTION',
                                'APPLICATION_EXCEPTION'
                            )
                        ),

    processing_time     REAL
                        CHECK (
                            processing_time IS NULL
                            OR processing_time >= 0
                        ),

    exception_type      TEXT
                        CHECK (
                            exception_type IS NULL
                            OR exception_type IN (
                                'BUSINESS',
                                'APPLICATION',
                                'DOCUMENT'
                            )
                        ),

    exception_message   TEXT,

    -- Pipe-delimited or JSON-serialized validation findings produced by
    -- business/document validation. Supports multiple issues per invoice.
    validation_issues   TEXT,

    -- Optional record of checks that could not run because a prerequisite
    -- was unavailable (for example PO-dependent checks when the PO is missing).
    skipped_checks      TEXT

    -- ERP document/reference number returned after successful posting.
    erp_reference       TEXT
);


CREATE INDEX idx_po_supplier
    ON PurchaseOrders(supplier_id);

CREATE INDEX idx_invoice_supplier
    ON HistoricalInvoices(supplier_id);

CREATE INDEX idx_invoice_po
    ON HistoricalInvoices(po_number);

CREATE INDEX idx_invoice_number
    ON HistoricalInvoices(invoice_number);

CREATE INDEX idx_log_invoice_number
    ON AutomationLog(invoice_number);