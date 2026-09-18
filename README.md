# Apex Conglomerate — Search AI Dataset

A synthetic multi-industry dataset built for hands-on exploration of [Elastic Search AI](https://www.elastic.co/search-labs) capabilities: semantic search, hybrid retrieval, NLP enrichment, agentic RAG, multimodal search, and document-level security.

Originally created for the **Elastic Search AI Hack-Lab** with SVA — a full-day hackathon challenging Data Scientists and AI Engineers to build production-ready GenAI applications from scratch.

---

## The Company

**Apex Conglomerate** is a fictional multinational operating across five industries: financial services (ApexPay), industrial manufacturing (ApexIndustrial), pharmaceuticals (ApexPharma), telecommunications (ApexConnect), and technology consulting (ApexTech). Nine Elasticsearch indices capture a slice of its data universe — connected by shared identifiers, hiding a few surprises.

---

## Dataset Overview

```
apex-conglomerate-dataset/
├── core/                    start here
├── extra_mile/              go deeper
├── multimodal/              images + text
└── import_scripts/          get it into Elastic
```

### Core Indices

| Index | Documents | What's inside |
|---|---|---|
| `apex_customer_360` | 500 | CRM profiles — segments, NPS, churn risk, lifetime value, account manager |
| `apex_customer_interactions` | 800 | Support transcripts in EN · DE · FR · IT · ES — sentiment, intent, emotion |
| `apex_financial_transactions` | 1,200 | Payments — merchant, geo, device, velocity, anomaly scores |
| `apex_operational_telemetry` | 5,000 | IoT sensor readings — vibration, temperature, RUL, FFT features |
| `apex_pharma_batches` | 400 | QC batch records — chemical parameters, inspector notes in 5 languages |

### Extra Mile Indices

| Index | Documents | What's inside |
|---|---|---|
| `apex_policy_vault` | 17 chunks | Compliance policies — AML, GDPR, complaint handling — EN/DE/FR/IT/ES |
| `apex_unstructured_vault` | 18 chunks | Manuals, contracts, patents, and something classified |
| `apex_technical_docs` | 6 chunks | Asset maintenance documentation — bearing frequencies, failure modes |
| `apex_it_knowledge_base` | 132 chunks | IT knowledge from ServiceNow, Confluence, SharePoint — EN/DE/FR |
| `apex_knowledge_graph` | 364 nodes + edges | Entity relationships — customers, suppliers, accounts, transactions |
| `apex_security_acls` | 49 docs | RBAC roles, DLS filters, FLS restrictions |

### Multimodal

Three NDJSON files index into `apex_multimodal_assets`. Raw SVG files are also provided in subfolders for true image embedding.

```
multimodal/
├── apex_multimodal_assets.ndjson      pharma chromatography charts + IoT diagrams
├── apex_technical_diagrams.ndjson     FFT spectra, RUL trends, motor schematics
├── apex_it_diagrams.ndjson            ES cluster, K8s, CI/CD, observability diagrams
├── svg_samples/                       5 SVG files — chromatography charts
├── tech_diagrams/                     9 SVG files — engineering diagrams
└── it_diagrams/                       6 SVG files — IT architecture diagrams
```

---

## Cross-Index Links

The dataset is designed to be explored across indices. A few connections to get you started:

- `customer_id` appears in `apex_customer_360`, `apex_customer_interactions`, and `apex_financial_transactions`
- `supplier_id` links `apex_financial_transactions`, `apex_operational_telemetry`, and `apex_knowledge_graph`
- `asset_id` connects `apex_operational_telemetry` to `apex_multimodal_assets`
- `batch_id` links `apex_pharma_batches` to `apex_multimodal_assets`

There are more. Some of the most interesting things in this dataset only appear when you query across multiple indices.

---

## Getting Started

### Prerequisites

- Python 3.8+
- An Elasticsearch cluster (Elastic Cloud trial works — [start one here](https://cloud.elastic.co/registration))
- A Jina AI API key for multimodal embedding — [free at jina.ai](https://jina.ai/embeddings) (optional)

### Import

```bash
cd import_scripts
# edit the three variables at the top of the script
python3 import_apex.py
```

The script will:
1. Install missing Python dependencies automatically
2. Create all indices with the provided mappings
3. Import all documents

See [`import_scripts/`](import_scripts/) for full details.

---

## Inference Endpoints

The mappings reference two inference endpoints:

**Text embedding** — served by the cluster itself, no external key needed:
```
.jina-embeddings-v5-text-small
```

**Multimodal embedding** — Jina AI hosted API, requires `JINA_API_KEY`:
```
jina-embeddings-v5-omni-small
```

Indices with free-text fields (`apex_customer_interactions`, `apex_pharma_batches`, `apex_policy_vault`, `apex_unstructured_vault`, `apex_technical_docs`, `apex_it_knowledge_base`, `apex_multimodal_assets`) use `semantic_text` fields — embeddings are generated automatically at ingest time once the inference endpoint is configured.

---

## What to Build

There is no single right answer. Some directions worth exploring:

**Start simple.** The core indices work immediately after import — no embeddings required for `apex_customer_360`, `apex_financial_transactions`, and `apex_operational_telemetry`. Get data in, run your first queries, understand the structure.

**Add meaning.** Configure an inference endpoint and re-map your indices with `semantic_text`. Query `apex_customer_interactions` with a concept rather than a keyword. Try a query in German against an English document.

**Connect things.** The most interesting questions in this dataset span multiple indices. Can you answer the question: *"Why did this customer churn, and is there a systemic risk across the portfolio?"* — using only Elasticsearch queries?

**Secure it.** The `apex_security_acls` index defines roles, DLS filters, and FLS restrictions that map onto the data. A well-built agent should respect these — and prove it when challenged.

**Go further.** The `extra_mile/` folder exists for a reason. So do the SVG files.

---

## A Note on the Data

Some documents in this dataset are not what they appear to be on the surface. Pay attention to anomalies. There are assets that have been running longer than they should. There are transactions that form a pattern. There is a document in `apex_unstructured_vault` that references something called **Project Prometheus** — and it is not the only one.

Whether you find these things depends on how deeply you look.

---

## Stack

Built to work with:

- [Elasticsearch 8.x](https://www.elastic.co/elasticsearch) — hybrid search, semantic_text, kNN, RRF
- [Elastic Inference Service (EIS)](https://www.elastic.co/guide/en/elasticsearch/reference/current/inference-apis.html) — model hosting and inference endpoints
- [Jina AI](https://jina.ai) — multilingual text and multimodal embeddings
- [Elastic Agent Builder](https://www.elastic.co/guide/en/kibana/current/assistant.html) — agentic RAG
- [Elastic EUI](https://eui.elastic.co) — UI component library for custom frontends

---

## License

Dataset content is entirely synthetic and fictional. All company names, customer names, transaction data, and documents are generated for educational purposes. Any resemblance to real entities is coincidental.

MIT License — see [LICENSE](LICENSE).

---

*Built by the Elastic Solutions Architecture team.*
