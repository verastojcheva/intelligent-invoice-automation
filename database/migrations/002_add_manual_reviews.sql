CREATE TABLE IF NOT EXISTS ManualReviews (
    review_reference TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewed_at TEXT NOT NULL
);