# Exception Matrix

## Enterprise Intelligent Invoice Processing Automation

This document defines the exception-handling model used by the Enterprise Intelligent Invoice Processing Automation. It describes the main business, document, and application exceptions, their expected processing routes, human-review requirements, and retry behavior.

The solution distinguishes between:

- **Business Exceptions** — the automation works correctly, but the invoice violates a business rule or requires business judgment.
- **Document Exceptions** — required information cannot be reliably obtained from the invoice document.
- **Application Exceptions** — a technical component, integration, or automation activity fails.

This distinction prevents business-rule problems from being unnecessarily retried while allowing temporary technical failures to recover through configured retry mechanisms.

---

## 1. Exception Matrix

| Exception / Condition                       | Classification | Processing Route / Response                                                                   | Human Review             | Automatic Retry |
| ------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------- | ------------------------ | --------------- |
| Duplicate invoice                           | Business       | REJECT — prevent ERP posting                                                                  | No                       | No              |
| Missing purchase order                      | Business       | MANUAL_REVIEW                                                                                 | Yes                      | No              |
| Unknown supplier                            | Business       | MANUAL_REVIEW                                                                                 | Yes                      | No              |
| PO amount mismatch                          | Business       | MANUAL_REVIEW                                                                                 | Yes                      | No              |
| PO currency mismatch                        | Business       | MANUAL_REVIEW                                                                                 | Yes                      | No              |
| Missing VAT information                     | Business       | MANUAL_REVIEW                                                                                 | Yes                      | No              |
| High-value invoice                          | Business       | MANUAL_REVIEW                                                                                 | Yes                      | No              |
| Unusual invoice amount                      | Business       | Contributes to review decision according to configured validation rules                       | When review is triggered | No              |
| Missing invoice number                      | Document       | Prevent automatic posting and route for review                                                | Yes                      | No              |
| Missing invoice date                        | Document       | Prevent automatic posting and route for review                                                | Yes                      | No              |
| Missing or unusable critical extracted data | Document       | Prevent automatic posting and route for review/document-exception handling                    | Yes                      | No              |
| OCR/extraction produces incomplete data     | Document       | Validate available data, record unavailable checks, and route according to resulting findings | When required            | No              |
| Database unavailable                        | Application    | Stop affected transaction and record application exception                                    | No                       | Yes             |
| Database connection failure                 | Application    | Log technical failure and retry according to Orchestrator configuration                       | No                       | Yes             |
| ERP API timeout                             | Application    | Prevent posting and record application exception                                              | No                       | Yes             |
| ERP API unavailable                         | Application    | Prevent posting, log technical failure, and retry according to configuration                  | No                       | Yes             |
| Invalid/unexpected ERP response             | Application    | Prevent successful transaction completion and record application exception                    | No                       | Yes             |
| Unexpected automation/runtime error         | Application    | Record application exception and allow configured transaction retry                           | No                       | Yes             |

---

## 2. Business Exceptions

A Business Exception occurs when the automation is operating correctly but the invoice does not satisfy a business rule or requires human judgment.

Examples include:

- Duplicate invoices
- Missing purchase orders
- Unknown suppliers
- Purchase-order amount mismatches
- Purchase-order currency mismatches
- Missing VAT information
- High-value invoices
- Other validation conditions requiring business review

Business exceptions are not automatically retried because repeating the same automation steps would not normally correct the underlying invoice or business-data problem.

Depending on the severity of the detected condition, the transaction is assigned one of two routes:

### MANUAL_REVIEW

The invoice contains a condition that prevents straight-through processing but can potentially be resolved or accepted through human judgment.

The reviewer receives the available invoice information together with the detected validation findings and can approve or reject the transaction.

### REJECT

The invoice contains a condition that should prevent further processing.

Duplicate invoices are treated as reject-level conditions because automatically posting a known duplicate could create a duplicate-payment risk.

---

## 3. Document Exceptions

A Document Exception occurs when required information cannot be reliably obtained from the source invoice.

The automation first attempts direct PDF text extraction.

If usable text is unavailable, OCR is used as a fallback.

The resulting extracted information is then validated before any posting decision is made.

If critical information remains missing or unusable, the transaction is not treated as a valid straight-through invoice.

Instead, the automation can:

- Preserve the information that was successfully extracted
- Record missing fields as validation findings
- Record checks that could not be performed
- Prevent automatic ERP posting
- Route the transaction for human review or document-exception handling

For example, if the invoice number cannot be extracted, duplicate validation may not be possible. Rather than assuming that the duplicate check passed, the unavailable check can be recorded and the invoice prevented from being automatically posted.

This creates a fail-safe behavior for incomplete document extraction.

---

## 4. Application Exceptions

Application Exceptions represent technical failures rather than problems with the invoice itself.

Examples include:

- Database connectivity failure
- ERP API timeout
- ERP/API unavailability
- Unexpected integration response
- Automation runtime failure

These failures may be temporary.

Application Exceptions are therefore eligible for retry according to the configured UiPath Orchestrator transaction behavior.

A technical failure should not be converted into a Business Exception simply because the invoice could not be processed.

This distinction allows operational monitoring to differentiate between:

**"The invoice is invalid or requires business attention"**

and

**"The automation could not complete the transaction because a technical component failed."**

Technical retry behavior was tested during development by deliberately introducing an application-level failure and observing the configured transaction retry behavior.

The final controlled `FinalDemo` execution contained zero Application Exceptions.

---

## 5. Multi-Fault Handling

An invoice can contain more than one problem.

The validation architecture therefore does not terminate validation immediately after detecting the first applicable issue.

Instead, applicable validation findings can be accumulated for the same transaction.

For example:

```text
MISSING_VAT
HIGH_VALUE
PO_CURRENCY_MISMATCH
```

can exist simultaneously.

This provides a more complete description of the transaction state and gives the human reviewer more useful information.

Without multi-fault aggregation, an invoice could be returned for one problem, corrected, processed again, and only then reveal another problem.

Collecting applicable findings during the same validation cycle reduces this type of repeated review.

---

## 6. Routing Precedence

Issue detection and final routing are treated as separate concerns.

### Issue aggregation

The automation attempts to preserve all applicable validation findings.

### Routing decision

The most restrictive applicable condition determines the final processing route.

The routing precedence is:

```text
REJECT > MANUAL_REVIEW > AUTO_PROCESS
```

This means that a reject-level finding takes precedence over review-level findings.

For example, a multi-fault invoice may contain:

```text
PO_AMOUNT_MISMATCH
PO_CURRENCY_MISMATCH
DUPLICATE_INVOICE
```

The amount and currency mismatches would normally require review.

However, `DUPLICATE_INVOICE` is a reject-level condition.

The final route is therefore:

```text
REJECT
```

The amount and currency findings are still preserved rather than discarded.

This design provides both:

1. A complete record of the detected problems.
2. A deterministic and safe final processing decision.

---

## 7. Retry Strategy

Retry behavior is determined by whether repeating the transaction could reasonably resolve the problem.

| Exception Type        | Automatic Retry | Rationale                                                                                     |
| --------------------- | --------------- | --------------------------------------------------------------------------------------------- |
| Business Exception    | No              | Repeating the automation does not correct invalid business data                               |
| Document Exception    | No              | Reprocessing the same source document normally does not restore genuinely missing information |
| Application Exception | Yes             | Temporary technical or integration problems may recover                                       |

For example:

A duplicate invoice should not be retried because it will remain a duplicate.

A missing purchase order should not be repeatedly processed because the business condition has not changed.

A temporary database or ERP connectivity failure may recover, making retry appropriate.

This prevents unnecessary automation workload while allowing transient technical problems an opportunity to recover.

---

## 8. Transaction Isolation

Invoices are processed as individual transactions through UiPath Orchestrator queues.

This means that an exception affecting one invoice does not automatically terminate processing of the complete invoice workload.

For example:

```text
Invoice 1 → SUCCESS
Invoice 2 → BUSINESS EXCEPTION
Invoice 3 → SUCCESS
Invoice 4 → APPLICATION EXCEPTION / RETRY
Invoice 5 → SUCCESS
```

Each transaction maintains its own processing outcome.

This provides better resilience, monitoring, recovery, and operational control than processing an entire invoice batch as one indivisible transaction.

---

## 9. Human Review

Human review is used when the automation identifies a condition that requires business judgment rather than an automatic rejection.

The review interface can provide the reviewer with:

- Invoice information
- Detected validation issues
- Checks that could not be completed
- Approve action
- Reject action

The review decision is persisted and used by the automation to determine subsequent processing.

### Approved

If the reviewer approves the transaction, the invoice can continue to downstream ERP processing.

### Rejected

If the reviewer rejects the transaction, ERP posting does not proceed.

This keeps human decision-making within the process without requiring every invoice to be manually reviewed.

---

## 10. Logging and Traceability

Exception handling is supported by transaction and review logging.

Relevant information can include:

- Invoice identifier
- Transaction status
- Exception classification
- Exception message
- Validation findings
- Skipped checks
- Processing timestamp
- Processing duration
- Human-review decision
- ERP reference for successfully posted invoices

UiPath Orchestrator additionally provides queue-level transaction monitoring and distinguishes successful, business-exception, and application-exception outcomes.

This provides traceability for both business and technical investigation.

---

## 11. Fail-Safe Processing Principle

The automation follows a fail-safe processing principle:

> An invoice should not be automatically posted when a condition requiring rejection, human judgment, or unresolved critical information has been detected.

The objective is not to maximize the number of invoices automatically posted at any cost.

Instead, the automation is designed to:

- Automatically process straightforward transactions
- Detect and preserve relevant validation findings
- Reject known reject-level conditions
- Route uncertain or exceptional transactions to a human
- Retry appropriate technical failures
- Maintain traceability of processing outcomes

This approach balances automation efficiency with the controls required for financial-process automation.

---

## 12. Summary

The exception-handling model separates invoice-related business problems from document-quality problems and technical automation failures.

Three main exception classes are used:

| Classification | Primary Response                               |
| -------------- | ---------------------------------------------- |
| Business       | Manual review or rejection                     |
| Document       | Prevent automatic posting and route for review |
| Application    | Log failure and retry when appropriate         |

Multi-fault aggregation ensures that applicable findings are preserved, while routing precedence ensures that the safest applicable processing route is selected.

Together with Orchestrator transaction isolation, human-in-the-loop processing, logging, and retry handling, this provides a structured exception-management approach for the invoice automation prototype.
