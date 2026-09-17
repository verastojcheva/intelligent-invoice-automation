# Solution Design Document

## Enterprise Intelligent Invoice Processing Automation

**Document Type:** Solution Design Document (SDD)  
**Primary Platform:** UiPath  
**Environment:** Portfolio prototype / simulated enterprise environment  
**Author:** Vera Stojcheva

---

## 1. Purpose and Scope

This document describes the technical design of the Enterprise Intelligent Invoice Processing Automation.

The solution automates supplier invoice processing using UiPath as the central automation platform, supported by Python, SQLite, OCR, REST APIs, UiPath Orchestrator, and a browser-based human-review interface.

The implemented solution covers:

- Invoice discovery and transaction creation
- Queue-based invoice processing
- PDF text extraction with OCR fallback
- Structured field extraction
- Python-based data validation
- Supplier and purchase-order validation
- Duplicate detection
- Statistical and ML-based anomaly detection
- Multi-fault validation
- Business-rule routing
- Human-in-the-loop review
- REST API-based ERP posting
- Transaction and exception logging
- Business and Application Exception handling
- Retry of appropriate technical failures

Business-process requirements are defined separately in the [Process Definition Document](Process_Definition_Document.md).

---

## 2. Solution Architecture

UiPath coordinates the complete invoice-processing lifecycle.

```text
                         Invoice PDFs
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
                    Structured Extraction
                              │
                              ▼
                 ┌────────────────────────┐
                 │    Validation Layer    │
                 │                        │
                 │ Python validation      │
                 │ SQL business checks    │
                 │ Duplicate detection    │
                 │ Statistical anomaly    │
                 │ Isolation Forest ML    │
                 └───────────┬────────────┘
                             │
                             ▼
                     Business Rules
                             │
             ┌───────────────┼───────────────┐
             │               │               │
             ▼               ▼               ▼
       AUTO_PROCESS    MANUAL_REVIEW        REJECT
             │               │               │
             │               ▼               ▼
             │          Review UI       No ERP Posting
             │               │
             │         APPROVE / REJECT
             │               │
             └──── APPROVE ──┘
                     │
                     ▼
                  REST API
                     │
                     ▼
                Simulated ERP
                     │
                     ▼
              Transaction Logging
```

The architecture separates transaction orchestration, document processing, validation, business decisioning, human review, and external-system integration.

This separation allows individual components to be maintained or replaced without redesigning the complete automation.

---

## 3. UiPath Design

### 3.1 Main Process

The active high-level UiPath process is:

```text
GetInvoices
    ↓
Dispatcher
    ↓
Performer
```

`GetInvoices` identifies invoice files available for processing.

The **Dispatcher** creates the transaction workload.

The **Performer** processes the resulting queue transactions.

Separating workload creation from transaction processing allows invoices to be handled independently and supports Orchestrator queue monitoring and retry behavior.

---

### 3.2 Dispatcher

The Dispatcher creates an individual UiPath Orchestrator queue item for each invoice.

Its primary responsibilities are:

- Receive discovered invoice files
- Create queue transactions
- Store the information required to locate/process each invoice
- Submit the workload to the configured Orchestrator queue

Each invoice therefore becomes an independent transaction rather than being processed as part of one indivisible batch.

---

### 3.3 Performer

The Performer retrieves queue items and executes the invoice-processing logic.

For each transaction, it:

1. Retrieves the invoice queue item.
2. Extracts invoice information.
3. Executes data and business validation.
4. Runs applicable anomaly checks.
5. Aggregates validation findings.
6. Determines the processing route.
7. Executes automatic ERP processing, human review, or rejection.
8. Logs the result.
9. Sets the corresponding Orchestrator transaction status.

The Performer is therefore responsible for the complete lifecycle of an individual invoice transaction.

---

### 3.4 Orchestrator Queue

UiPath Orchestrator provides transaction management for the solution.

The queue provides:

- Independent invoice transactions
- Transaction status
- Business Exception classification
- Application Exception classification
- Retry support
- Execution history
- Operational monitoring

The controlled final demonstration used the `FinalDemo` queue.

Internal invoice routing and Orchestrator status are intentionally separate concepts.

For example, an invoice may initially receive:

```text
MANUAL_REVIEW
```

and later complete successfully after human approval and ERP posting.

A rejected transaction can instead finish as a Business Exception because the automation worked correctly but the invoice was not eligible for posting.

---

## 4. Document Extraction

The implemented document-processing pipeline uses direct PDF extraction with OCR fallback.

```text
Invoice PDF
     │
     ▼
Read PDF Text
     │
     ▼
Usable text?
   ┌─┴─┐
  YES  NO
   │    │
   │    ▼
   │   OCR
   │    │
   └─┬──┘
     ▼
Structured Field Extraction
     │
     ▼
Validation
```

The automation first attempts to read text directly from the PDF.

When usable text is unavailable, OCR is used as a fallback.

The resulting text is used to extract invoice fields required by downstream validation.

The implemented prototype does **not** use UiPath Document Understanding confidence-based extraction. Missing or unusable critical data is handled through validation and routing rather than through artificial confidence thresholds.

---

## 5. Validation Design

Validation is divided into several complementary layers.

### 5.1 Invoice Data Validation

Python-based validation checks extracted information including:

- Invoice number
- Amount
- Invoice date
- VAT information
- Currency
- IBAN validity

The validation logic supports multiple findings for the same invoice rather than stopping after the first detected issue.

---

### 5.2 Business Data Validation

SQLite data is used for business-level checks including:

- Supplier lookup
- Purchase-order lookup
- Invoice/PO amount comparison
- Invoice/PO currency comparison
- Duplicate detection
- Historical invoice lookup

Checks that cannot be performed because prerequisite information is unavailable can be recorded as skipped rather than incorrectly treated as passed.

---

### 5.3 Statistical Anomaly Detection

`python/anomaly_detection.py` analyzes supplier-specific historical invoice amounts.

The implementation uses:

- Historical paid invoices
- Median
- Median Absolute Deviation (MAD)
- Robust Z-score

A fallback comparison is used when MAD is zero.

The statistical model is intended to identify invoice amounts that differ significantly from the supplier's historical pattern.

---

### 5.4 Machine-Learning Anomaly Detection

`python/ml_anomaly_detection.py` provides an additional anomaly-analysis layer using **Isolation Forest**.

The model evaluates invoice amounts against historical supplier data.

The ML result contributes to risk analysis; it does not independently approve or post an invoice.

This keeps final transaction routing under deterministic business-rule control.

---

## 6. Business Decision Engine

After validation, the automation assigns one of three processing routes:

```text
AUTO_PROCESS
MANUAL_REVIEW
REJECT
```

### AUTO_PROCESS

The required validation conditions have been satisfied and no review/reject condition applies.

The transaction proceeds directly to ERP processing.

### MANUAL_REVIEW

One or more conditions require human judgment.

The transaction is sent to the human-review workflow.

### REJECT

A reject-level condition is present.

The transaction is prevented from ERP posting.

---

### 6.1 Multi-Fault Handling

Validation findings are aggregated so that an invoice can contain several issues simultaneously.

For example:

```text
MISSING_VAT
HIGH_VALUE
PO_CURRENCY_MISMATCH
```

can all be associated with one transaction.

Routing uses the following precedence:

```text
REJECT > MANUAL_REVIEW > AUTO_PROCESS
```

Therefore, if an invoice contains:

```text
PO_AMOUNT_MISMATCH
PO_CURRENCY_MISMATCH
DUPLICATE_INVOICE
```

the final route is `REJECT`, while the other detected issues remain available for traceability.

Detailed business and exception rules are documented in the [Exception Matrix](Exception_Matrix.md).

---

## 7. Human Review Design

Invoices classified as `MANUAL_REVIEW` are passed to the human-review workflow.

A browser-based Flask application presents the reviewer with relevant transaction information, including:

- Invoice information
- Validation findings
- Skipped checks
- Approve action
- Reject action

Each review receives a unique review reference.

The decision is persisted in the `ManualReviews` database table.

UiPath checks for the recorded decision and resumes processing when a decision becomes available.

### Approved

```text
MANUAL_REVIEW
      ↓
Human APPROVE
      ↓
ERP Processing
```

### Rejected

```text
MANUAL_REVIEW
      ↓
Human REJECT
      ↓
No ERP Posting
```

This design allows human judgment to remain part of the automated transaction lifecycle without requiring manual processing of every invoice.

---

## 8. ERP Integration

The prototype includes a simulated ERP REST API implemented with Flask.

Approved invoices are sent from UiPath to the API using an HTTP request.

```text
UiPath
   ↓
HTTP POST
   ↓
Flask REST API
   ↓
Simulated ERP
   ↓
ERP Reference
   ↓
UiPath
```

A successful posting returns an ERP reference, which is stored with the transaction log.

Transactions routed to `REJECT`, or manually rejected during review, do not proceed to the ERP integration.

The simulated API allows the prototype to demonstrate REST-based enterprise integration without requiring access to a production ERP.

---

## 9. Database Design

SQLite provides the relational data layer for the prototype.

The database contains:

- Supplier master data
- Purchase-order data
- Historical invoices
- Automation transaction logs
- Human-review decisions

Database schema and migrations are maintained under:

```text
database/
```

### 9.1 AutomationLog

`AutomationLog` stores transaction-processing information including:

- Transaction ID
- Invoice number
- Timestamp
- Status
- Processing time
- Exception type
- Exception message
- Validation issues
- Skipped checks
- ERP reference

### 9.2 ManualReviews

`ManualReviews` stores human-review outcomes including:

- Review reference
- Invoice number
- Decision
- Review timestamp

SQLite was selected for the prototype because it provides a portable relational database without requiring separate database infrastructure.

A production implementation would normally use an enterprise database platform.

---

## 10. Exception and Retry Design

The automation distinguishes between three types of exceptional conditions.

| Type                  | Meaning                                                   | Retry                |
| --------------------- | --------------------------------------------------------- | -------------------- |
| Business Exception    | Invoice/business condition prevents normal completion     | No                   |
| Document Exception    | Required document information cannot be reliably obtained | No                   |
| Application Exception | Technical component or integration fails                  | Yes, when configured |

Business problems are not retried because repeating the same automation normally cannot correct the underlying invoice condition.

Application failures can be retried through Orchestrator because temporary database, API, or infrastructure failures may recover.

This prevents technical failures from being incorrectly classified as invoice problems and prevents unnecessary retries of known business issues.

Detailed exception behavior is maintained in the [Exception Matrix](Exception_Matrix.md).

---

## 11. Logging and Monitoring

The solution uses both SQLite and UiPath Orchestrator for operational traceability.

### UiPath Orchestrator

Provides visibility into:

- Queue transactions
- Successful transactions
- Business Exceptions
- Application Exceptions
- Retry attempts
- Execution history

### SQLite

Provides detailed transaction information including:

- Validation findings
- Skipped checks
- Processing duration
- Exception information
- ERP references

Human-review decisions are also persisted separately.

Together, these records allow an invoice's processing outcome to be traced across automated validation, human review, exception handling, and ERP posting.

---

## 12. Configuration and Security

The current implementation is a portfolio prototype using synthetic data.

Production deployment would require environment-specific configuration and security controls.

The intended design principles are:

- Credentials and secrets must not be hard-coded in source code.
- Production credentials should use UiPath Orchestrator Assets or an approved secrets-management solution.
- Automation accounts should follow least-privilege access.
- Invoice and supplier data should be accessible only to authorized processes and users.
- Sensitive financial information should not be unnecessarily written to logs.
- Processing and human decisions should remain auditable.
- Production invoice and log retention periods should be formally defined.

The prototype does not contain real supplier or production financial data.

---

## 13. Deployment Components

The solution consists of four primary runtime components:

| Component          | Purpose                                       |
| ------------------ | --------------------------------------------- |
| UiPath project     | Main automation and transaction orchestration |
| Python modules     | Validation and anomaly analysis               |
| SQLite database    | Business data, logging, and review decisions  |
| Flask applications | Simulated ERP API and human-review interface  |

Python dependencies are defined in:

```text
requirements.txt
```

Database definitions and migrations are maintained under:

```text
database/
```

The UiPath project and workflows are maintained under:

```text
uipath/InvoiceAutomation/
```

API components are maintained under:

```text
api/
```

---

## 14. Technical Limitations

The prototype has the following deliberate limitations:

- SQLite is used instead of a production enterprise database.
- ERP integration is simulated through a Flask REST API.
- The human-review interface is a prototype rather than an enterprise task-management application.
- Document processing uses PDF text extraction with OCR fallback rather than full Document Understanding.
- Production authentication and authorization infrastructure is not implemented.
- Production credential and secrets management is not implemented.
- The solution has not been performance/load tested at production invoice volumes.

These limitations do not affect the purpose of the prototype: demonstrating the technical architecture and end-to-end processing behavior of the automation.

---

## 15. Maintenance Considerations

The automation may require maintenance when:

- Invoice formats change
- Supplier or purchase-order data structures change
- Business rules or thresholds change
- ERP API contracts change
- Python dependencies change
- UiPath packages are upgraded
- Database schemas change

Operational procedures, recovery steps, and routine monitoring responsibilities are documented separately in the [Runbook](Runbook.md).

---

## 16. Related Documentation

The SDD should be read together with the other project documents rather than duplicating their content.

| Document                                                      | Purpose                                                |
| ------------------------------------------------------------- | ------------------------------------------------------ |
| [Process Definition Document](Process_Definition_Document.md) | Defines the business process and requirements          |
| [Exception Matrix](Exception_Matrix.md)                       | Defines detailed exception classification and handling |
| [UAT Report](UAT_Report.md)                                   | Documents acceptance testing                           |
| [Operational Metrics](Operational_Metrics.md)                 | Documents measured demonstration results               |
| [Business Value Analysis](Business_Value.md)                  | Documents expected business impact                     |
| [Runbook](Runbook.md)                                         | Defines operational and maintenance procedures         |
