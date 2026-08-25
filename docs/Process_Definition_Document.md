# Process Definition Document

## 1. Process Name

Enterprise Intelligent Invoice Processing

## 2. Process Owner

Accounts Payable Manager

## 3. Stakeholders

- Accounts Payable Specialists
- Finance Manager
- Procurement Team
- IT / Automation Team

## 4. Process Objective

Automate the processing and validation of supplier invoices — from receipt through extraction,
validation, and decisioning — so that standard, rule-conforming invoices are processed without
manual intervention, while ambiguous or exceptional invoices are routed to human employees for
review.

## 5. Inputs

- Supplier invoice PDF
- Supplier master data
- Purchase order data
- Historical invoice data

## 6. Outputs

- Approved invoice (posted to ERP)
- Manual review case
- Rejected invoice
- Processing log entry

## 7. Current Pain Points

- Repetitive manual work on invoices that are routine and low-risk
- Data-entry errors introduced during manual transcription into the ERP
- Slow, queue-dependent processing that delays payment cycles
- Duplicate-payment risk due to inconsistent manual duplicate checking
- Inconsistent validation quality across different AP employees
- Poor visibility into processing status, volumes, and bottlenecks
- Skilled employee time consumed by straightforward, non-exceptional invoices

## 8. Systems Involved

- Invoice source (email / shared folder / scanning system)
- UiPath (extraction, validation, orchestration)
- Supplier database
- Purchase order database
- ERP system

## 9. Process Frequency

Example volume assumption: **~100 invoices/day**, arriving throughout the business day with peaks
around month-end.

## 10. Business Rules

- Supplier must exist and be in an active status in the supplier master
- Purchase order must exist and be open/valid
- Invoice must not be a duplicate of a previously processed invoice
- Invoice amount must match the PO amount within a defined tolerance (e.g. 2%)
- Invoice currency must match the expected/PO currency
- Additional rules (VAT format, minimum extraction confidence, auto-approval limit, etc.) as
  defined in project configuration

## 11. Known Exceptions

- Missing purchase order
- Unknown/unrecognized supplier
- Duplicate invoice
- Incorrect or mismatched amount
- Unreadable or low-quality document
- Low-confidence field extraction

## 12. Automation Suitability

This process is a strong automation candidate because it is:

- **Repetitive** — the same sequence of lookups and checks is performed for every invoice
- **Rule-based** — the vast majority of decisions (supplier valid? PO valid? amount matches?
  duplicate?) follow clear, deterministic business rules rather than open-ended judgment
- **High-volume** — a steady daily volume of invoices means even modest per-invoice time savings
  compound into significant total effort reduction
- **Structured but variable input** — invoices arrive as semi-structured PDF documents, which
  document-understanding/OCR technology can reliably extract, while genuinely ambiguous cases can
  still be escalated to a human

## 13. Expected Business Value

- Reduced manual effort on routine, low-risk invoices
- Reduced data-entry and validation errors
- Faster invoice processing and shorter time-to-pay
- Better auditability through consistent, logged processing decisions
- AP staff time redirected toward invoices that genuinely require judgment

## 14. Functional Requirements

| ID    | Requirement                                                                                                      |
| ----- | ---------------------------------------------------------------------------------------------------------------- |
| FR-01 | The system shall retrieve incoming invoices from the source location.                                            |
| FR-02 | The system shall extract invoice information (invoice number, supplier, PO, amount, currency, dates, VAT, IBAN). |
| FR-03 | The system shall validate the supplier against supplier master data.                                             |
| FR-04 | The system shall validate the invoice against purchase order data.                                               |
| FR-05 | The system shall detect duplicate invoices.                                                                      |
| FR-06 | The system shall apply configurable business rules to reach a decision (auto-process, review, reject).           |
| FR-07 | The system shall log every processing outcome for auditability.                                                  |

## 15. Acceptance Criteria

- Valid invoices (correct supplier, PO, amount, and no duplicate) are processed automatically
  without human intervention.
- Duplicate invoices are always rejected and never posted to the ERP.
- Invalid, ambiguous, or low-confidence invoices are routed to human review rather than
  auto-processed.
- Every invoice transaction — successful or not — is logged with a clear outcome and reason.
