# Process Definition Document

## Enterprise Intelligent Invoice Processing

**Process Owner:** Accounts Payable Manager  
**Process:** Supplier Invoice Processing  
**Automation Platform:** UiPath  
**Author:** Vera Stojcheva

---

## 1. Process Objective

The purpose of this process is to automate repetitive supplier invoice processing while keeping human control over invoices that require business judgment.

The process covers invoice receipt, information extraction, validation, business-rule checks, decisioning, human review when required, and ERP posting.

Invoices are assigned to one of three processing routes:

- **AUTO_PROCESS** — the invoice passes the required checks and can continue automatically.
- **MANUAL_REVIEW** — the invoice contains an issue that requires human judgment.
- **REJECT** — the invoice contains a reject-level condition and must not be posted.

---

## 2. Stakeholders

| Stakeholder                 | Role                                                                |
| --------------------------- | ------------------------------------------------------------------- |
| Accounts Payable Manager    | Process owner and responsible for invoice-processing rules          |
| Accounts Payable Specialist | Reviews exceptional invoices and makes approval/rejection decisions |
| Finance                     | Financial control and oversight                                     |
| Procurement                 | Supports supplier and purchase-order related issues                 |
| IT / Automation Team        | Supports and maintains the automated process                        |

---

## 3. Process Inputs and Outputs

### Inputs

- Supplier invoice PDF
- Supplier master data
- Purchase-order data
- Historical invoice data

Relevant invoice information includes:

- Invoice number
- Supplier
- Purchase-order number
- Amount
- Currency
- Invoice date
- VAT information
- IBAN where available

### Outputs

- Invoice posted to ERP
- Invoice routed for human review
- Invoice rejected
- Processing outcome and validation information recorded

---

## 4. AS-IS Process

In the manual process, an Accounts Payable employee performs the main invoice-processing activities.

```text
Supplier
   ↓
Invoice received
   ↓
AP employee
   ↓
Open invoice
   ↓
Extract information
   ↓
Supplier lookup
   ↓
PO lookup
   ↓
Amount validation
   ↓
Duplicate check
   ↓
ERP entry
   ↓
Approve / Escalate
   ↓
Archive
```

[View AS-IS Process Diagram](AS_IS_Process.png)

### Main Pain Points

- Repetitive manual processing of routine invoices
- Manual data-entry effort and potential transcription errors
- Employee time spent on predictable validation tasks
- Risk of inconsistent validation
- Duplicate-payment risk
- Limited structured visibility into processing outcomes and exceptions

---

## 5. TO-BE Process

The target process automates routine invoice handling and directs human attention toward exceptional transactions.

```text
Invoice
   ↓
Document Extraction
   ↓
Validation
   ↓
Supplier Check
   ↓
PO Check
   ↓
Duplicate Check
   ↓
Business Rules
   ↓
┌─────────────────┬───────────────────┬──────────────┐
│                 │                   │              │
AUTO_PROCESS   MANUAL_REVIEW        REJECT
│                 │                   │
▼                 ▼                   ▼
ERP           Human Review       No ERP Posting
                  │
             ┌────┴─────┐
             │          │
          APPROVE     REJECT
             │          │
             ▼          ▼
            ERP    No ERP Posting
```

[View TO-BE Process Diagram](TO_BE_Process.png)

The automation performs extraction and rule-based validation before determining the appropriate route.

Straightforward invoices can continue without human intervention. Exceptional invoices are either routed to an Accounts Payable specialist or rejected according to the applicable business rules.

---

## 6. Business Rules

The main business rules used to determine invoice routing are:

| Condition                                        | Route         |
| ------------------------------------------------ | ------------- |
| Required validations passed                      | AUTO_PROCESS  |
| Missing purchase order                           | MANUAL_REVIEW |
| Unknown supplier                                 | MANUAL_REVIEW |
| PO amount mismatch                               | MANUAL_REVIEW |
| PO currency mismatch                             | MANUAL_REVIEW |
| Missing VAT                                      | MANUAL_REVIEW |
| High-value invoice                               | MANUAL_REVIEW |
| Missing or unusable critical invoice information | MANUAL_REVIEW |
| Duplicate invoice                                | REJECT        |

An invoice may contain multiple validation findings.

When multiple conditions apply, the final route follows:

```text
REJECT > MANUAL_REVIEW > AUTO_PROCESS
```

For example, an invoice containing both a PO mismatch and a duplicate condition is rejected because the duplicate condition has higher routing priority.

Detailed exception classification and handling are documented in the [Exception Matrix](Exception_Matrix.md).

---

## 7. Functional Requirements

| ID    | Requirement                                                                                                  |
| ----- | ------------------------------------------------------------------------------------------------------------ |
| FR-01 | Retrieve incoming supplier invoices from the configured source                                               |
| FR-02 | Extract the required invoice information, using OCR fallback when necessary                                  |
| FR-03 | Validate extracted invoice data                                                                              |
| FR-04 | Validate the supplier against supplier-master data                                                           |
| FR-05 | Validate invoice information against purchase-order data                                                     |
| FR-06 | Detect previously processed duplicate invoices                                                               |
| FR-07 | Apply business rules and assign AUTO_PROCESS, MANUAL_REVIEW, or REJECT                                       |
| FR-08 | Preserve multiple applicable validation findings                                                             |
| FR-09 | Allow a human reviewer to approve or reject MANUAL_REVIEW transactions                                       |
| FR-10 | Send eligible AUTO_PROCESS and human-approved invoices to ERP processing                                     |
| FR-11 | Prevent rejected invoices from being posted to the ERP                                                       |
| FR-12 | Record the processing outcome and relevant validation information for each transaction                       |
| FR-13 | Handle individual invoices independently so that one failed transaction does not stop the remaining workload |

---

## 8. Acceptance Criteria

The process meets the defined requirements when:

- Valid invoices can be processed automatically without human intervention.
- Duplicate invoices are rejected and prevented from ERP posting.
- Review-level validation issues result in human review rather than automatic posting.
- Missing or unusable critical invoice information prevents straight-through processing.
- Human reviewers can approve or reject review transactions.
- Approved review transactions can continue to ERP processing.
- Rejected review transactions do not proceed to ERP posting.
- Multiple applicable validation findings can be retained for one invoice.
- Reject-level conditions take precedence over review-level conditions.
- Processing outcomes are recorded and individual invoice transactions remain isolated.

Acceptance testing and demonstrated results are documented in the [UAT Report](UAT_Report.md).

---

## 9. Process Scope

The implemented process is a portfolio prototype using synthetic invoice, supplier, purchase-order, and historical invoice data.

The process demonstrates:

- Automated invoice extraction
- OCR fallback
- Invoice and business-data validation
- Duplicate detection
- Business-rule decisioning
- Human-in-the-loop review
- ERP posting
- Exception handling
- Transaction traceability

The ERP and human-review environments are simulated for the prototype.

Full Document Understanding confidence-based extraction and production enterprise integrations are outside the implemented scope.

Technical implementation and architecture are documented separately in the [Solution Design Document](Solution_Design_Document.md).
