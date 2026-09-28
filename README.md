# 📦 Authority Packs (`krusch-Authority-Packs`)

> **Controlled Rulebooks for Enterprise AI — by Jurisdiction and Effective Date**  
> An open architecture, specification, and evaluation harness for governed knowledge modules in high-assurance legal, financial, and enterprise workflows.

[![CI](https://github.com/kruschdev/krusch-Authority-Packs/actions/workflows/test.yml/badge.svg)](https://github.com/kruschdev/krusch-Authority-Packs/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Benchmark: GC-Grade](https://img.shields.io/badge/Benchmark_Eval-n%3D180%20(5%20Classes)-gold.svg)](https://krusch.dev/articles/authority-packs.html)
[![Wrong-Law Blend: 0.0%](https://img.shields.io/badge/Wrong--Law_Blend-0.0%25-brightgreen.svg)](https://krusch.dev/articles/authority-packs.html)
[![Product: Governed Modules](https://img.shields.io/badge/Category-Governed%20Knowledge%20Modules-cyan.svg)](https://krusch.dev/articles/authority-packs.html)

<p align="center">
  <img src="assets/authority_packs_hero.jpg" alt="Authority Packs Architecture &amp; Command Center" width="100%">
</p>

---

## 💼 The Commercial Reality: Buyers Don't Buy Retrieval

In enterprise procurement and regulated industries, you do not sell "RAG." Buyers do not buy retrieval mechanisms, sliding windows, or vector similarity. **Buyers purchase a bounded, versioned rulebook the AI system is legally permitted to use.**

### The Buyer Sentence
> *“Your model only sees the Oakland 2024 ordinance, the numeric caps we extracted, and the statutes that override it. If the question is outside the pack, it refuses.”*

### One-Line Positioning
> **“We don’t search the internet for the law. We ship the pack that is the law for that city, that year.”**

---

## 📋 Product Line: What You Actually Invoice

Internally, developers call these structures *RAG Packs* because they package knowledge for retrieval-augmented generation. But on an invoice, an RFP, or a commercial contract, the category label is **governed knowledge modules** (or **versioned authority datasets**), and the product name is an **Authority Pack**.

| SKU | What the Customer Thinks They Bought | What You Deliver |
|---|---|---|
| **Jurisdiction Pack**<br>`(Legal Vertical)` | “LA rent / Oakland just cause / SF OMI rulebook” | YAML specification + typed slots + preemption DAG + physical PDF citation coordinates + `as_of` temporal gate. |
| **Standards Pack**<br>`(Finance & Audit)` | “US GAAP ASC 606 revenue recognition pack” | Five-step deterministic contract checklist + numeric financing thresholds + distinctness criteria + out-of-scope refusal contract. |
| **Playbook Pack**<br>`(Enterprise Contracts)` | “Our corporate MSA / procurement policy” | Company clauses and authorized deviation bounds joined directly against statutory floors and ceiling packs. |
| **Pack Subscription**<br>`(Recurring SaaS)` | “Keep our AI current when the city council amends” | Continuous legislative monitoring, version bumps, amendment diffs, and updated effective-date graphs. **Sell the subscription to currency, not the static file.** |
| **Pack Audit**<br>`(Assurance & Defense)` | “Prove this AI advice came from the gazette” | Sub-line cell bounding box report (`[x0, y0, x1, y1]`), verbatim quote matches, and automated 180-query verification matrix. |

### Pitch Vocabulary Guide

| Terms to Use (Procurement &amp; GC Approved) | Terms to Avoid (Why They Create Friction) |
|---|---|
| **Authority Pack** | *RAG Pack* — Sounds like low-level developer plumbing; buyers don't buy infrastructure. |
| **Certified Pack / Controlled Pack** | *Knowledge Pack* — Generic vendor buzzword that every generic chatbot company claims. |
| **Effective-Date Pack** | *Sovereign Pack* — Fine in architectural essays; confusing on enterprise procurement forms. |
| **Scoped Rulebook** | *Deterministic AI Pack* — Overclaim; legal counsel and finance will push back on "deterministic AI". |
| **Compliance Module** | *Hallucination-Free Pack* — Uninsurable legal liability. Never promise 0% hallucination in open text. |

---

## 🏛️ The Problem in Practice: The California Municipal Trilogy

In California residential tenancy, state law sets default baselines, but the actual rules governing evictions, rent caps, and relocation payments are dictated by hyper-local municipal ordinances:

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

## 🔬 Separating Determinism from Probabilistic Generation

We explicitly separate three layers of the software stack:

1. **Deterministic Binding (Exact):** Which pack, which enacted edition, which verified as-of date (or explicit refusal).
2. **Deterministic Slots & Preemption Operators (Exact):** Typed constants (`33.0`, `21 days`, `3 business days`), physical source bboxes, verbatim quoted sentences, and compiled preemption graphs.
3. **Probabilistic Generation (Sampling):** The Large Language Model drafting rhetorical text. The model is constrained to draft claims **only from structured findings and cited spans**.

---

## 🧭 Pack Selection: The Binder Subsystem (`src/binder.py`)

If an agent simply picks the "nearest" pack using embedding similarity, you have not solved vector bleed—you have merely moved it from chunk retrieval to pack retrieval.

`src/binder.py` enforces an explicit **Pack Binder** pipeline:
1. **Entity Extraction:** Extracts `municipality`, `county`, `state`, `court`, `as_of_date`, and `doc_type`.
2. **Registry Resolution:** Matches extracted entities against the pack catalog.
3. **Ambiguity Gating:** If a query contains cross-city trap wording (e.g. an LA property analyzed with SF terminology), the binder emits `REFUSED_AMBIGUOUS` rather than guessing.
4. **Coverage Contracts:** Packs declare explicit `known_uncovered_topics` (e.g. commercial leases, mobile homes). Out-of-scope inquiries fail closed with `REFUSED_OUT_OF_SCOPE`.
5. **Multi-Pack Join Plan:** Assembles an explicit execution plan (e.g. State Floor + Municipal Override + Costa-Hawkins Ceiling).

---

## ⏳ Stopping Temporal Bleed: Versioning Law Like Software

Serving advice based on outdated statutory thresholds is **Temporal Bleed**.

Every Authority Pack enforces:
* `effective_from` / `effective_to`: Temporal validity bounds.
* `source_document_hash`: Cryptographic SHA-256 hash of the authoritative government gazette.
* `as_of_date` Query Evaluation: Historical queries (e.g. evaluating a 2022 transaction against a 2024 AB 12 pack) fail closed (`REFUSED_STALE_OR_PRE_EFFECTIVE`).

---

## 🔒 Span-Grounded Slots & Fail-Closed Audits (`src/slots.py`)

Slots are not standalone magic numbers. Every slot in an Authority Pack is anchored to:
* **Physical Source Span:** `page_number`, bounding box `bbox: [x0, y0, x1, y1]`, character offsets.
* **Verbatim Quoted Sentence:** Exact text from the enacted statute.
* **Extraction Audit Trail:** `extraction_method` (`human_curated`, `compiler_layout`, `model_proposed_human_reviewed`), reviewer ID, and timestamp.

The runtime `SlotVerifier` audits each slot against its cited sentence. If the compiler value and quoted sentence disagree, **the system fails closed**. The generation model is permitted to cite a slot only if it can cite the verified span coordinates.

---

## ⚖️ Preemption as a Compiled Graph (`src/preemption.py`)

Statutory preemption is modeled as a compiled directed graph using explicit operators:

| Operator | Legal Mechanics | Example |
|---|---|---|
| `HARMONIZED_FLOOR` | State sets minimum protection; local may be stricter. Local rule controls. | AB 1482 (§ 1946.2) yields to Oakland OMC § 8.22. |
| `OCCUPYING_CEILING` | State sets maximum cap; local cannot regulate exempt units. State rule controls. | Costa-Hawkins (§ 1954.52) preempts local rent caps on single-family/post-1995 homes. |
| `FIELD_PREEMPTION` | State occupies whole subject; local rule is void. | Judicial trial procedures (CCP § 1161) preempt local courts. |
| `CONFLICT_UNRESOLVED` | Conflict detected with no registered preemption edge. | **Fails closed**: emits an unresolved flag for counsel review. |

---

## 📊 Binder Conformance Suite: Gate Verification (N = 180)

Self-authored unit tests are essential regression guards, but they test code execution paths rather than gate boundary behavior under adversarial input. To measure the real-world boundary enforcement of Authority Packs against vector bleed, we benchmarked 180 standardized challenge queries across five distinct challenge classes (`src/eval.py`):

*Note on evaluation methodology:* This benchmark evaluates **deterministic gate conformance**—measuring whether the Pack Binder correctly routes, bounds, extracts physical slots, or fails closed on ambiguous, cross-jurisdiction, or stale queries before any text generation occurs. It measures boundary and gate enforcement, contrasting directly with unconstrained naive cosine vector RAG.

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

## ⏱️ Curation Economics: Real Maintenance Effort

Authority Packs follow a disciplined human-in-the-loop engineering pipeline:

1. **Layout-True Parsing:** KruschNexus extracts cell-level tables and geometric ASTs from government gazettes.
2. **Candidate Slot Compilation:** Syntactic parsers extract candidate slots anchored to verbatim quoted sentences.
3. **Diff Against Prior Edition:** Git diff identifies modified sections and altered numerical values in new legislative supplements.
4. **Dual-Sign Governance:** A pack release requires dual cryptographic sign-off before shipping: a lead extraction engineer audits physical span coordinates, and an accredited domain practitioner (e.g. active California bar member for municipal tenancy, or certified CPA for ASC 606) audits statutory slots before co-signing the SHA-256 release digest.

**Engineering Cost Benchmark:**
- Standing up a new municipal pack: **2 to 4 hours** of legal engineering time.
- Annual legislative supplement or fee update: **30 to 60 minutes**.

---

## 🚀 CLI Usage & Quickstart

### Installation
```bash
git clone https://github.com/kruschdev/krusch-Authority-Packs.git
cd krusch-Authority-Packs
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

### Run Automated Unit Tests (26 Tests)
```bash
pytest -v tests/
```

---

## 📄 License

MIT License. Copyright &copy; 2026 Kevin Ruschman / KruschDev.
See [LICENSE](LICENSE) for details.
