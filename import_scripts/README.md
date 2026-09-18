# Import Scripts

## Quick Start

```bash
pip install -r requirements.txt
python3 import_apex.py
```

Or just run `python3 import_apex.py` directly — missing dependencies are installed automatically.

## Configuration

Open `import_apex.py` and set the three variables at the top:

```python
ES_URL     = "https://your-cluster-id.es.region.aws.elastic.cloud:443"
ES_API_KEY = "your-elastic-api-key-here"
JINA_API_KEY = "your-jina-api-key-here"
```

- **ES_URL** — Elastic Cloud console › your deployment › Manage › Copy endpoint
- **ES_API_KEY** — Kibana › Stack Management › API Keys › Create
- **JINA_API_KEY** — [jina.ai/embeddings](https://jina.ai/embeddings) (free tier, only needed for `IMPORT_SVG_IMAGES = True`)

## Options

```python
RECREATE_INDICES  = False   # True = delete and recreate existing indices
IMPORT_SVG_IMAGES = False   # True = embed SVG files via Jina AI (extra mile)
BULK_BATCH_SIZE   = 200     # reduce to 50 if you get 413 errors
```

## What the Script Does

1. Installs missing Python dependencies
2. Reads `mappings_reference.json` and creates all indices
3. Imports `core/` → `extra_mile/` → `multimodal/` in order
4. If `IMPORT_SVG_IMAGES = True`: reads each SVG file from the image folders, calls the Jina AI REST API directly, and stores the resulting 1024-dim vector as `dense_vector` in `apex_multimodal_raw_images`

## Mappings

`mappings_reference.json` defines all index mappings. Fields that contain free text use `semantic_text` with inference endpoint `.jina-embeddings-v5-text-small` — embeddings are generated automatically at ingest time.

## Common Errors

| Error | Fix |
|---|---|
| Connection refused / timeout | Check firewall allows outbound HTTPS to Elastic Cloud on port 443 |
| `resource_already_exists_exception` | Set `RECREATE_INDICES = True` or delete the index manually in Kibana Dev Tools |
| `mapper_parsing_exception` | Mapping mismatch — delete the index and re-run |
| `413 Request Entity Too Large` | Reduce `BULK_BATCH_SIZE` to 50 |
| Jina `401 Unauthorized` | Check `JINA_API_KEY` is set correctly |
| Jina `429 Too Many Requests` | Increase the `time.sleep(1.0)` in `import_svg_images()` |
