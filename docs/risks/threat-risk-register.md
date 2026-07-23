# Threat and risk register (Phase 0)

| ID | Category | Risk | Likelihood | Impact | Mitigation | Owner phase |
|----|----------|------|------------|--------|------------|-------------|
| T1 | Legal | Copyright infringement via full-article republication | Medium | High | Snippets + attribution; assessments; legal gate before connectors | 1+ |
| T2 | Legal | Scraping against ToS / robots | Medium | High | Assessment template; no fetch before approval | 1 |
| T3 | Security | Cross-tenant data leak | Medium | Critical | Tenant-scoped queries + isolation tests | 2 |
| T4 | Security | Secret leakage in logs/frontend | Medium | High | Redaction helpers; server-only keys; `.gitignore` | 0+ |
| T5 | Security | Malicious uploads | Medium | High | MIME/size checks; virus scan later; signed URLs | 6+ |
| T6 | Ops | Source breakage / silent miss | High | High | Fetch-run metrics, alerts, volume anomaly detection | 3+ |
| T7 | Ops | OCR cost overrun | Medium | Medium | Text-layer first; pin model; provenance + budgets | 7 |
| T8 | Ops | Embedding/LLM cost overrun | Medium | Medium | Deterministic match first; thresholds; eval gates | 4–5 |
| T9 | Product | False positives on Arabic names | High | Medium | Layered matching; exclusions; human review | 4–5 |
| T10 | Access | Paywalled / licensed sources | Medium | Medium | Keep registry row; status `requires_license` | 1/8 |
| T11 | Supply | Provider model ID drift | Medium | Medium | Env-pinned models; no hardcoded IDs | 0/5/7 |
| T12 | Delivery | Immutable report mutation | Low | High | Versioned snapshots + stored final PDF | 6 |
| T13 | Product | Logo false positives treated as final | High | High | Cascade + human review only; never auto-include | 9 |
| T14 | Ops | Logo cloud API cost overrun | Medium | Medium | Local screen first; pin external model; cost approval gate | 9 |
| T15 | Legal/Ops | X scrape / ToS violation | Medium | High | Official API only; checklist gates; no HTML scrape | 10 |
| T16 | Ops | X usage-based API cost overrun | High | Medium | Cost approval flag; approved outlets only; poll caps | 10 |

Unresolved decisions carried forward: LLM provider, email provider, production cloud, exact auth token strategy (implement Phase 2).
