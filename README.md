# Enterprise Intelligent Invoice Processing Automation

An end-to-end enterprise automation prototype for supplier invoice processing using **UiPath, UiPath Orchestrator, Python, SQL, REST APIs, OCR, machine learning, and human-in-the-loop review**.

The solution automatically processes straightforward invoices while routing exceptional transactions for human review or rejection based on business rules.

---

## Overview

Invoice processing involves more than extracting information from a PDF. A reliable automation must validate business data, detect duplicates and inconsistencies, handle poor-quality documents, integrate with enterprise systems, recover from technical failures, and involve humans when business judgment is required.

This project implements an enterprise-style invoice processing architecture centered on **UiPath**.

The automation:

- Extracts invoice information with OCR fallback
- Validates invoice and business data
- Checks suppliers and purchase orders against SQL data
- Detects duplicate invoices
- Performs statistical anomaly detection
- Uses Isolation Forest for ML-based anomaly detection
- Aggregates multiple validation findings
- Routes transactions according to business rules
- Supports human-in-the-loop review
- Integrates with a simulated ERP through a REST API
- Uses UiPath Orchestrator queues for transaction processing
- Separates business and application exceptions
- Supports retry of technical failures
- Records transaction outcomes for monitoring and traceability

---

## Architecture

```text
                         Supplier Invoice
                                │
                                ▼
                       UiPath Dispatcher
                                │
                                ▼
                     Orchestrator Queue
                                │
                                ▼
                        UiPath Performer
                                │
                                ▼
                 PDF Extraction / OCR Fallback
                                │
                                ▼
                  Structured Data Extraction
                                │
                                ▼
              ┌────────────────────────────────┐
              │       Validation Layer         │
              │                                │
              │  Python validation             │
              │  Supplier / PO validation      │
              │  Duplicate detection           │
              │  Statistical anomaly detection │
              │  Isolation Forest ML           │
              └───────────────┬────────────────┘
                              │
                              ▼
                     Business Rule Engine
                              │
              ┌───────────────┼──────────────────┐
              │               │                  │
              ▼               ▼                  ▼
        AUTO_PROCESS     MANUAL_REVIEW          REJECT
              │               │                  │
              │               ▼                  ▼
              │         Human Review UI    Business Exception
              │               │
              │        ┌──────┴──────┐
              │        │             │
              │     APPROVE        REJECT
              │        │             │
              └────────┘             ▼
                  │             No ERP Posting
                  ▼
              REST API
                  │
                  ▼
           Simulated ERP
                  │
                  ▼
          Transaction Logging
```

---

## Technology Stack

| Area                   | Technology                                     |
| ---------------------- | ---------------------------------------------- |
| RPA                    | UiPath Studio                                  |
| Orchestration          | UiPath Orchestrator                            |
| Transaction Management | Orchestrator Queues                            |
| Programming            | Python                                         |
| Database               | SQLite / SQL                                   |
| Document Processing    | PDF text extraction + OCR fallback             |
| Validation             | Python + SQL + business rules                  |
| Statistical Analysis   | Median / MAD anomaly detection                 |
| Machine Learning       | Isolation Forest                               |
| API Integration        | REST / HTTP                                    |
| ERP Simulation         | Flask REST API                                 |
| Human Review           | Flask browser interface + UiPath UI automation |
| Version Control        | Git / GitHub                                   |
| CI                     | GitHub Actions                                 |

---

## Processing Routes

Every invoice is assigned one of three processing routes.

### AUTO_PROCESS

Invoices that satisfy the required validation and business rules continue automatically to the simulated ERP without human intervention.

### MANUAL_REVIEW

Invoices containing conditions requiring business judgment are presented to a reviewer together with the detected validation findings.

The reviewer can **approve or reject** the invoice.

Approved invoices can continue to ERP processing. Rejected invoices are prevented from posting.

### REJECT

Reject-level conditions stop processing automatically.

Duplicate invoices are treated as reject-level transactions to prevent potential duplicate posting.

Routing precedence is:

```text
REJECT > MANUAL_REVIEW > AUTO_PROCESS
```

Multiple applicable validation findings are preserved even when a higher-priority condition determines the final route.

---

## Validation and Intelligent Processing

Validation is performed across multiple layers rather than relying on a single extraction result.

### Document and Data Validation

Python validation includes checks for extracted invoice information such as:

- Invoice number
- Amount
- Invoice date
- VAT information
- Currency
- IBAN validity

### Business Validation

Database-backed validation includes:

- Supplier validation
- Purchase-order validation
- Amount comparison
- Currency comparison
- Duplicate detection
- Historical invoice analysis

### Statistical Anomaly Detection

Historical supplier invoices are analyzed using supplier-specific statistical information.

Median and **Median Absolute Deviation (MAD)** are used to identify unusual invoice amounts while reducing sensitivity to extreme historical values.

### Machine Learning

An **Isolation Forest** model provides an additional anomaly-detection layer using historical invoice data.

Machine-learning results contribute to risk analysis rather than independently authorizing financial transactions.

---

## Human-in-the-Loop Review

Not every financial decision should be automated.

Invoices requiring business judgment are routed to a browser-based review interface displaying:

- Extracted invoice information
- Detected validation issues
- Checks that could not be completed
- Approve / Reject actions

The review decision is persisted in SQLite and retrieved by UiPath before processing continues.

This allows routine invoices to remain automated while keeping humans in control of exceptional transactions.

---

## Exception Handling

The solution distinguishes between three exception categories.

| Type        | Example                         | Response                             |
| ----------- | ------------------------------- | ------------------------------------ |
| Business    | Duplicate invoice               | Reject or manual review              |
| Document    | Missing critical extracted data | Prevent automatic posting and review |
| Application | Database/API failure            | Log and retry when appropriate       |

Business problems are not unnecessarily retried.

Technical failures can use UiPath Orchestrator retry functionality because temporary infrastructure problems may recover.

Multi-fault invoices retain applicable validation findings while routing precedence determines the safest final outcome.

---

## Test Dataset

The project contains **17 synthetic invoice scenarios** covering normal and exceptional processing.

The dataset includes:

- Valid invoices
- Duplicate invoices
- Missing purchase order
- Unknown supplier
- Amount mismatch
- Currency mismatch
- Missing VAT information
- High-value invoice
- Poor-quality / OCR invoice
- Multi-fault manual-review scenario
- Multi-fault rejection scenario

The dataset intentionally contains a high proportion of exceptions to demonstrate validation, routing, human review, duplicate prevention, and exception-handling capabilities.

---

## FinalDemo Results

The final controlled UiPath Orchestrator demonstration processed **17 invoice scenarios**.

| Processing Route | Transactions |     Rate |
| ---------------- | -----------: | -------: |
| Straight-through |            6 |   35.29% |
| Human review     |            8 |   47.06% |
| Automatic reject |            3 |   17.65% |
| **Total**        |       **17** | **100%** |

Additional results:

- **8** invoices posted to the simulated ERP
- **2** human-reviewed invoices approved and posted
- **6** human-reviewed invoices rejected
- **9** transactions ended as expected Business Exceptions
- **0** Application Exceptions in the final controlled run

The test dataset is intentionally exception-heavy. These percentages demonstrate processing behavior and should not be interpreted as expected production invoice distributions.

---

## Business Value

The solution demonstrates how Accounts Payable automation can:

- Reduce repetitive invoice-processing work
- Enable straight-through processing for routine invoices
- Prevent known duplicate invoices from reaching ERP posting
- Direct human effort toward exceptional transactions
- Apply validation rules consistently
- Improve processing traceability
- Separate business failures from technical failures
- Provide a scalable queue-based processing architecture

Using a scenario assumption of **7 minutes of manual processing per invoice**, the six straight-through transactions in the FinalDemo represent approximately **42 minutes of potentially avoided routine manual processing**.

The seven-minute figure is an illustrative scenario assumption, not a measured production result.

---

## Repository Structure

```text
intelligent-invoice-automation/
│
├── api/
│   ├── manual_review_ui.py
│   └── mock_erp_api.py
│
├── database/
│   ├── migrations/
│   │   ├── 001_add_erp_reference.sql
│   │   └── 002_add_manual_reviews.sql
│   ├── invoice_automation.db
│   └── schema.sql
│
├── docs/
│   ├── AS_IS_Process.png
│   ├── Business_Case.md
│   ├── Business_Value.md
│   ├── Exception_Matrix.md
│   ├── Operational_Metrics.md
│   ├── Process_Definition_Document.md
│   ├── Runbook.md
│   ├── Solution_Design_Document.md
│   ├── TO_BE_Process.png
│   └── UAT_Report.md
│
├── python/
│   ├── anomaly_detection.py
│   ├── ml_anomaly_detection.py
│   └── validator.py
│
├── scripts/
│   ├── fix_supplier_ibans.py
│   ├── generate_data.py
│   └── generate_invoices.py
│
├── test-data/
│   ├── completed/
│   ├── incoming/
│   ├── processing/
│   ├── rejected/
│   ├── review/
│   └── invoice_scenarios.csv
│
├── uipath/
│   └── InvoiceAutomation/
│       └── [UiPath project files and workflows]
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Documentation

Detailed project documentation is available in [`docs/`](docs/).

### Business & Process Design

- [Business Case](docs/Business_Case.md)
- [Process Definition Document](docs/Process_Definition_Document.md)
- [AS-IS Process](docs/AS_IS_Process.png)
- [TO-BE Process](docs/TO_BE_Process.png)

### Solution Design & Operations

- [Solution Design Document](docs/Solution_Design_Document.md)
- [Exception Matrix](docs/Exception_Matrix.md)
- [Runbook](docs/Runbook.md)

### Testing & Results

- [User Acceptance Test Report](docs/UAT_Report.md)
- [Operational Metrics](docs/Operational_Metrics.md)
- [Business Value Analysis](docs/Business_Value.md)

---

## Design Principles

### Fail Safe

Invoices with unresolved critical information or reject-level findings should not be automatically posted.

### Human Control Where Necessary

Automation handles predictable work while business judgment remains with the reviewer.

### Separate Business and Technical Failures

Business-rule violations should not be repeatedly retried as if they were infrastructure failures. Temporary application failures can be retried independently.

### Preserve the Complete Issue Set

Multiple applicable validation findings are retained rather than terminating validation after the first detected problem.

### Observability

Processing outcomes, exceptions, human decisions, and ERP references remain traceable through transaction logging and Orchestrator monitoring.

### Transaction Isolation

Invoices are processed as individual Orchestrator transactions so that a failure affecting one invoice does not terminate the complete workload.

---

## Current Scope

This repository represents a **portfolio prototype using synthetic data and simulated enterprise integrations**.

The current document-processing pipeline is:

```text
PDF text extraction
        ↓
OCR fallback
        ↓
Structured extraction
        ↓
Validation
        ↓
Business decision
```

Full Document Understanding confidence-based processing is **not claimed as implemented functionality**.

Document Understanding remains a possible future enhancement.

The current implementation prioritizes working end-to-end automation, controlled exception handling, integration, testing, and observability.

---

## Future Improvements

Potential production-oriented extensions include:

- UiPath Document Understanding and confidence-based extraction
- Production ERP integration
- Enterprise credential and secret management
- Production database infrastructure
- Enhanced operational dashboards
- Power Platform integration
- Expanded automated test coverage
- Production-scale performance and load testing
- Enterprise deployment pipelines
- Additional security and data-governance controls

---

## Disclaimer

This project is a **portfolio prototype** created using synthetic invoice, supplier, purchase-order, and historical transaction data.

The ERP environment and human-review application are simulated components created to demonstrate enterprise integration and automation architecture.

Production deployment would require integration testing with actual enterprise systems, security and access-control review, production data governance, performance testing, operational monitoring, and formal business acceptance.

---

## Author

**Vera Stojcheva**

Software & Systems Engineering  
Software Product Management and Business
