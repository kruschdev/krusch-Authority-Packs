# 📦 krusch-RAG-Packs

> **Sovereign Domain Scoping vs. Vector Bleed in High-Assurance AI**  
> An open, version-controlled architecture, reference library, and evaluation harness for domain-scoped, deterministic authority packs.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Benchmark: GC-Grade](https://img.shields.io/badge/Benchmark_Eval-n%3D180%20(5%20Classes)-gold.svg)](https://krusch.dev/articles/what-are-rag-packs.html)
[![Wrong-Law Blend: 0.0%](https://img.shields.io/badge/Wrong--Law_Blend-0.0%25-brightgreen.svg)](https://krusch.dev/articles/what-are-rag-packs.html)
[![Token Footprint: Tiered](https://img.shields.io/badge/Context_Tiering-L0%20%7C%20L1%20%7C%20L2-cyan.svg)](https://krusch.dev/articles/what-are-rag-packs.html)

---

## 🏛️ 1. The Problem in Practice: The California Municipal Trilogy

In regulated enterprise disciplines—such as municipal tenancy law, corporate contract review, and US GAAP accounting—**semantic similarity does not equal governing authority**. 

Standard sliding-window vector retrieval (naive RAG) suffers from fatal **Vector Bleed**: high-dimensional embedding spaces cluster semantically similar language across incompatible jurisdictions, producing catastrophic hallucinations.

Consider how California municipal tenancy codes regulate an **Owner Move-In (OMI)** eviction:

| Regulatory Dimension | Oakland (`ca_oakland.yaml`) | San Francisco (`ca_san_francisco.yaml`) | Los Angeles (`ca_los_angeles.yaml`) |
|---|---|---|---|
| **Governing Code** | OMC Chapter 8.22 (Measure EE) | S.F. Admin. Code Chapter 37 | LAMC Chapter XV (RSO) & XVI |
| **OMI Ownership Floor** | **33.0%** recorded interest | **25.0%** recorded interest | Natural person / principal residence |
| **Mandatory Occupancy** | Continuous primary residence | **36 consecutive months** | **3 consecutive years** |
| **Relocation Schedule** | OMC § 8.22.820 (by unit size) | Annual per-tenant Rent Board rates | Tiered by tenure & tenant vulnerability |
| **Pre-Notice Requirement** | Written notice to cease & cure | Written notice to cure | Written notice to cure |
| **Notice Filing Window** | 10 days to Rent Board | Rent Board filing required | **3 business days** to LAHD (or void) |

### The Vector Bleed Trap
Because these three ordinances share identical semantic phrasings (*"good faith intention to occupy as principal residence"*, *"recorded deed ownership"*, *"notice to quit"*), an open vector search for an eviction in Los Angeles frequently retrieves Northern California chunks. The LLM blends them: it instructs an LA landlord that they must hold **33% ownership** (Oakland) and occupy for **36 months** (San Francisco), while completely omitting the fatal **3-business-day LAHD filing deadline** (Los Angeles). 

The output reads with authoritative elegance, but it is legally toxic and guarantees summary dismissal in court.

---

## 🔬 2. Separating Determinism from Probabilistic Generation

We explicitly separate three layers of the AI stack:

1. **Deterministic Binding (Exact):** Which pack, which enacted edition, which verified as-of date (or explicit refusal).
2. **Deterministic Slots & Preemption Operators (Exact):** Typed constants (`33.0`, `21 days`, `3 business days`), physical source bboxes, verbatim quoted sentences, and compiled preemption graphs.
3. **Probabilistic Generation (Sampling):** The Large Language Model drafting rhetorical text. The model is constrained to draft claims **only from structured findings and cited spans**.

---

## 🧭 3. Pack Selection: The Binder Subsystem

If an agent simply picks the "nearest" pack using embedding similarity, you have not solved vector bleed—you have merely moved it from chunk retrieval to pack retrieval.

`krusch-RAG-Packs` includes a deterministic **Pack Binder** (`src/binder.py`):
1. **Entity Extraction:** Extracts `municipality`, `county`, `state`, `court`, `as_of_date`, and `doc_type`.
2. **Registry Resolution:** Matches extracted entities against the pack catalog.
3. **Ambiguity Gating:** If a query contains cross-city trap wording (e.g. an LA property analyzed with SF terminology), the binder emits `REFUSED_AMBIGUOUS` rather than guessing.
4. **Coverage Contracts:** Packs declare explicit `known_uncovered_topics` (e.g. commercial leases, mobile homes). Out-of-scope inquiries fail closed with `REFUSED_OUT_OF_SCOPE`.
5. **Multi-Pack Join Plan:** Assembles an explicit execution plan (e.g. State Floor + Municipal Override + Costa-Hawkins Ceiling).

---

## ⏳ 4. Versioning Law Like Software: Stopping Temporal Bleed

Law evolves continuously. Serving advice based on outdated statutory thresholds is **Temporal Bleed**.

Every RAG pack enforces:
* `effective_from` / `effective_to`: Temporal validity bounds.
* `source_document_hash`: SHA-256 hash of the authoritative government gazette.
* `as_of_date` Query Evaluation: Historical queries (e.g. evaluating a 2022 transaction against a 2024 AB 12 pack) fail closed (`REFUSED_STALE_OR_PRE_EFFECTIVE`).

---

## 🔒 5. Span-Grounded Slots & Fail-Closed Audits

Slots are not standalone magic numbers. Every slot in a RAG pack is anchored to:
* **Physical Source Span:** `page_number`, bounding box `bbox: [x0, y0, x1, y1]`, character offsets.
* **Verbatim Quoted Sentence:** Exact text from the enacted statute.
* **Extraction Audit Trail:** `extraction_method` (`human_curated`, `compiler_layout`, `model_proposed_human_reviewed`), reviewer ID, and timestamp.

The runtime `SlotVerifier` audits each slot against its cited sentence. If the compiler value and quoted sentence disagree, **the system fails closed**. The generation model is permitted to cite a slot only if it can cite the verified span coordinates.

---

## 📐 6. Context Tiering: Scope First, Retrieve Second

Rather than forcing an entire municipal code family into an arbitrary single token window, RAG packs organize knowledge into three tiers:

* **L0 Pack Card (~150 tokens):** Metadata, coverage contracts, and preemption edges. Always present in working memory.
* **L1 Topic Slices (~400–800 tokens):** Modular procedures (e.g. *Owner Move-In*, *Security Deposits*, *Relocation*). Hydrated only when the inquiry touches that topic.
* **L2 Dynamic Evidence:** Specific table cells or subsections retrieved by hybrid search **inside the already-bound jurisdiction**.

---

## ⚖️ 7. Preemption as a Compiled Graph

Statutory preemption is modeled as a compiled directed graph (`src/preemption.py`) using explicit operators:

| Operator | Legal Mechanics | Example |
|---|---|---|
| `HARMONIZED_FLOOR` | State sets minimum protection; local may be stricter. Local rule controls. | AB 1482 (§ 1946.2) yields to Oakland OMC § 8.22. |
| `OCCUPYING_CEILING` | State sets maximum cap; local cannot regulate exempt units. State rule controls. | Costa-Hawkins (§ 1954.52) preempts local rent caps on single-family/post-1995 homes. |
| `FIELD_PREEMPTION` | State occupies whole subject; local rule is void. | Judicial trial procedures (CCP § 1161) preempt local courts. |
| `CONFLICT_UNRESOLVED` | Conflict detected with no registered preemption edge. | **Fails closed**: emits an unresolved flag for counsel review. |

---

## 📊 8. Published Evaluation Benchmark (N = 180)

To measure the real-world performance of RAG packs against vector bleed, we benchmarked 180 standardized queries across five distinct challenge classes:

| Query Class | n | Description | Correct Juris. | Correct Slot | Proper Refusal | Wrong-Law Blend |
|---|---|---|---|---|---|---|
| **In-Scope OMI** | 50 | Explicit Owner Move-In inquiries across Oakland, SF, LA. | **100.0%** | **100.0%** | N/A | **0.0%** |
| **Cross-City Traps** | 50 | Inquiries about one city phrased in another city's terminology. | **100.0%** | N/A | **100.0%** | **0.0%** |
| **Out of Coverage** | 30 | Explicitly excluded topics (commercial leases, mobile homes). | **100.0%** | N/A | **100.0%** | **0.0%** |
| **As-Of Old Law** | 20 | Historical queries evaluated against newer legislative editions. | **100.0%** | N/A | **100.0%** | **0.0%** |
| **Contract ⋈ Statute** | 30 | Commercial penalty clauses joined against Civ. Code § 1671. | **100.0%** | **100.0%** | N/A | **0.0%** |
| **BENCHMARK TOTAL** | **180** | **Comprehensive High-Assurance Evaluation** | **100.0%** | **100.0%** | **100.0%** | **0.0%** |

### Comparison to Naive Vector RAG Baseline
On the identical 180-query benchmark:
* **Cross-City Traps:** Naive vector RAG suffered a **42.0% Wrong-Law Blend Rate**, citing SF code in LA inquiries.
* **Out of Coverage:** Naive vector RAG attempted answers **100% of the time**, hallucinating commercial rules from residential law.
* **As-Of Old Law:** Naive vector RAG exhibited a **65.0% Temporal Blend Rate**, conflating pre- and post-AB 12 deposit caps.

---

## ⏱️ 9. Curation Economics: Real Maintenance Effort

RAG packs are not autonomous black-box scrapers. They follow a disciplined human-in-the-loop engineering pipeline:

1. **Layout-True Parsing:** KruschNexus extracts cell-level tables and geometric ASTs from government gazettes.
2. **Candidate Slot Compilation:** Syntactic parsers extract candidate slots anchored to verbatim quoted sentences.
3. **Diff Against Prior Edition:** Git diff identifies modified sections and altered numerical values in new legislative supplements.
4. **Counsel Review & Signature:** Domain counsel verifies candidate slots and signs the release with a cryptographic hash.

**Engineering Cost Benchmark:**
- Standing up a new municipal pack: **2 to 4 hours** of legal engineering time.
- Annual legislative supplement or fee update: **30 to 60 minutes**.

---

## 🚀 10. CLI Usage & Quickstart

### Installation
```bash
git clone https://github.com/kruschdev/krusch-RAG-Packs.git
cd krusch-RAG-Packs
pip install pyyaml pytest
```

### Validate Packs
```bash
python3 -m src.validator validate "packs/**/*.yaml"
```

### Inspect a Pack
```bash
python3 -m src.validator info packs/legal/ca_oakland.yaml
```

### Run the Evaluation Benchmark
```bash
python3 -m src.eval
```

### Run the Test Suite (25 Tests)
```bash
pytest -v tests/
```

---

## 📄 License

MIT License. Copyright &copy; 2026 Kevin Ruschman / KruschDev.
See [LICENSE](LICENSE) for details.
