# Business Case

## Company Context

Our fictional company operates an Accounts Payable (AP) department responsible for receiving,
validating, and processing supplier invoices. Every invoice that arrives — whether by email, portal
upload, or physical mail scan — currently has to pass through a manual review and entry process
before it can be paid.

## Current (Manual) Process

```
Supplier
    ↓
Invoice received
    ↓
AP employee opens invoice
    ↓
Extracts invoice information
    ↓
Searches supplier
    ↓
Checks purchase order
    ↓
Checks amount
    ↓
Checks for duplicate
    ↓
Enters invoice into ERP
    ↓
Approves / escalates
    ↓
Archives invoice
```

Each invoice, regardless of how simple or routine it is, is handled end-to-end by a human AP
employee. There is no differentiation between a straightforward, fully-matching invoice and one
that genuinely requires judgment.

## Problems With the Current Process

- **Repetitive manual work** — the same lookup/validation steps are repeated for every single
  invoice, including the large majority that are completely routine.
- **Data-entry errors** — manual transcription of amounts, supplier details, and PO numbers into
  the ERP introduces avoidable mistakes.
- **Slow processing** — invoices queue up behind whichever employee is available, extending
  time-to-pay and time-to-close.
- **Duplicate-payment risk** — without systematic, consistent duplicate checking, the same
  invoice can occasionally be paid twice.
- **Inconsistent validation** — different employees may apply supplier/PO/amount checks with
  varying rigor, leading to uneven control quality.
- **Poor processing visibility** — management has limited real-time insight into how many
  invoices are in progress, how long they take, or where bottlenecks occur.
- **Employee time wasted on straightforward invoices** — skilled AP staff spend most of their
  time on invoices that have no exceptions at all, rather than on the smaller number of cases
  that genuinely need human judgment.

## Automation Objective

**Automate standard invoice processing while routing ambiguous or exceptional cases to human
employees.**

This is the business justification for the project: free AP staff from repetitive, low-judgment
work on routine invoices, while preserving (and strengthening) human review for the cases that
actually need it — missing purchase orders, unknown suppliers, amount mismatches, duplicates, and
low-confidence document extractions.
