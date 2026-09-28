# RAG Pack Specification v1.0.0

An open, version-controlled standard for domain-scoped, deterministic knowledge artifacts in high-assurance AI workflows.

---

## 1. Abstract

Standard Retrieval-Augmented Generation (RAG) relies on heuristic sliding-window chunking and dense vector embeddings. While effective for open-domain information retrieval, this approach suffers from fatal **Vector Bleed** when applied to regulated domains—such as statutory law, municipal ordinances, financial accounting standards, and enterprise contracts.

The **RAG Pack** specification defines a structured, machine-verifiable format (YAML/JSON) that guarantees:
1. **Domain & Jurisdictional Isolation:** Explicit geographical, regulatory, and contractual boundaries.
2. **Explicit Topic Closure:** Exhaustive contracts specifying both `covered_topics` and `known_uncovered_topics` to prevent silent conversational hallucination.
3. **Pre-Extracted Machine Slots:** Strongly typed numerical limits, statutory deadlines, percentages, and multipliers.
4. **Preemption & Hierarchy Graphs:** Directed preemption edges establishing regulatory supremacy (floors vs. ceilings).
5. **Physical Citation Coordinates:** Layout-true geometry (`bbox`, `char_start`, `char_end`, `page_number`) anchored to official gazettes or executed contracts.
6. **Bounded Context Budgets:** Hard limits strictly enforced under **850 tokens per chunk** for zero-waste L1/L2 agent context injection.

---

## 2. Root Schema

Every RAG Pack root document MUST be a valid YAML dictionary containing the following keys:

| Field | Type | Description | Mandatory |
|---|---|---|---|
| `pack_id` | `string` | Unique identifier (e.g. `ca_oakland_pack_v1`). | **YES** |
| `version` | `string` | Semantic version string (e.g. `1.0.0`). | **YES** |
| `publisher` | `string` | Authoritative body or publisher (e.g. `City of Oakland / Municode`). | **YES** |
| `description` | `string` | Human-readable summary of the pack's legal/regulatory scope. | **YES** |
| `retrieved_at` | `ISO-8601 string` | Timestamp when the source authorities were retrieved. | Recommended |
| `state` | `string` | State or provincial code (e.g. `CA`). | Cond. (Legal) |
| `municipality` | `string` | City or municipal corporation name (e.g. `Oakland`). | Cond. (Legal) |
| `county` | `string` | County or regional administrative district. | Cond. (Legal) |
| `domain` | `string` | Industry or technical discipline (e.g. `Financial Accounting & Revenue Recognition`). | Cond. (Commercial) |
| `code_families` | `list[string]` | Governing statutory codes (e.g. `[California Civil Code, Oakland Municipal Code]`). | Optional |
| `coverage` | `object` | Scope boundary contract (see Section 3). | **YES** |
| `statutes` \| `standards` \| `clauses` | `list[object]` | Authoritative rule entries (see Section 4). | **YES** |

---

## 3. Scope Boundary Contract (`coverage`)

To prevent models from guessing when queried on adjacent but unindexed domains, every pack MUST declare both covered and uncovered topics:

```yaml
coverage:
  covered_topics:
    - "Security Deposits"
    - "Just Cause Evictions"
    - "Rent Increases"
    - "Owner Move-In"
  known_uncovered_topics:
    - "Commercial Lease Evictions"
    - "Mobile Home Residency Law"
    - "Agricultural Tenancies"
    - "Short-Term Vacation Rentals"
```

### Invariant:
When an agent or reasoning engine determines that a query maps to an item in `known_uncovered_topics`, it **MUST** emit a formal refusal or scope boundary warning rather than attempting probabilistic retrieval across adjacent packs.

---

## 4. Authority Entry Schema

Each item in `statutes`, `standards`, or `clauses` represents an authoritative provision and MUST adhere to the following schema:

```yaml
- citation: "Oakland Municipal Code § 8.22.030"
  section_number: "8.22.030"
  title: "Oakland Just Cause for Eviction Ordinance — Permissible Grounds for Eviction"
  topic: "Just Cause Evictions"
  authority_class: "municipal_ordinance" # 'controlling_statute' | 'municipal_ordinance' | 'standard_codification' | 'contractual_clause'
  hierarchy_level: "section" # 'title' | 'chapter' | 'section' | 'subsection'
  effective_date: "2002-11-05"
  source_url: "https://library.municode.com/..."
  publisher: "City of Oakland / Municode"
  edition: "Measure EE / OMC Supp. 104"
  raw_content: |
    No landlord shall endeavor to recover possession...
  statutory_slots:
    minimum_ownership_percent_omi: 33.0
    requires_relocation_payment: true
    requires_written_warning_notice: true
  preempts:
    - "Cal. Civ. Code § 1946.2"
  preempted_by: []
  exceptions_ref: "Oakland Municipal Code § 8.22.030(B)"
  defines_terms:
    - "Covered Unit"
    - "Disabled"
```

### 4.1. Pre-Extracted Slots (`statutory_slots`)
Slots MUST be key-value pairs representing objective parameters:
- **Numerical limits & deadlines:** `deposit_cap_months: 1.0`, `accounting_days: 21`.
- **Thresholds & multipliers:** `statutory_damages_multiplier: 2.0`, `base_cap_percent: 5.0`.
- **Boolean procedural triggers:** `requires_written_warning_notice: true`.

### 4.2. Preemption & Hierarchy Edges
- `preempts`: List of citations that this provision overrides or supersedes within its jurisdiction.
- `preempted_by`: List of higher-order state or federal authorities that constrain this provision (e.g. Costa-Hawkins preempting local vacancy control).

---

## 5. Token Budget Invariant

To ensure that packs can be loaded directly into agentic working memory (e.g. Model Context Protocol tools or L1/L2 prompt headers):
- **Chunk Limit:** No single authority entry's `raw_content` may exceed **850 estimated tokens** (`len(text) // 4 <= 850`).
- **Pack Limit:** A standard municipal or domain pack should typically pack within **1,500 – 2,500 total tokens**, providing 100% complete jurisdictional grounding for an entire dispute category.

---

## 6. Physical Citation Coordinates (KruschNexus Spine)

When compiled via layout-true ingestion engines like `krusch-nexus`, authority entries MAY include physical citation coordinates:

```yaml
citation_coordinates:
  page_number: 14
  pdf_page: 16
  bbox: [72.0, 310.4, 540.0, 480.2]
  char_start: 12048
  char_end: 12890
```

This guarantees bit-for-bit auditability: a user can click any generated legal or financial claim and view the exact highlight on the original government or corporate PDF.
