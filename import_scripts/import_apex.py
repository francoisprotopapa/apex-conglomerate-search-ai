#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex Conglomerate Dataset — Import Script for Elastic Cloud (ECH)
=================================================================
Usage:
    python3 import_apex.py

Requirements:
    pip install elasticsearch requests

What this script does:
    1. Connects to your Elastic Cloud cluster
    2. Creates all indices with the mappings defined in mappings_reference.json
    3. Imports all NDJSON files (core + extra_mile + multimodal) via _bulk API
    4. Optionally calls Jina AI REST API to embed SVG images as dense vectors

Inference endpoints:
    TEXT:       .jina-embeddings-v5-text-small  (hosted on the cluster)
    MULTIMODAL: jina-embeddings-v5-omni-small   (Jina AI REST API — requires JINA_API_KEY)
"""

import json
import sys
import subprocess
import importlib
import importlib.util
from pathlib import Path

# ================================================================
# AUTO-INSTALL DEPENDENCIES
# ================================================================

REQUIRED = {
    "elasticsearch": "elasticsearch>=8.0.0",
    "requests":      "requests>=2.28.0",
}

def _ensure_pip():
    """Make sure pip is available, bootstrap it if not."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return True
    # pip not found — try to bootstrap via ensurepip
    print("  pip not found — bootstrapping via ensurepip ...")
    result2 = subprocess.run(
        [sys.executable, "-m", "ensurepip", "--upgrade"],
        capture_output=True, text=True
    )
    if result2.returncode == 0:
        return True
    print("  ERROR: could not bootstrap pip.")
    print("  Please install pip manually:")
    print("    https://pip.pypa.io/en/stable/installation/")
    print("  Or install the packages manually:")
    for mod, pkg in REQUIRED.items():
        print(f"    {sys.executable} -m pip install '{pkg}'")
    sys.exit(1)

def _install_missing():
    missing = {
        mod: pkg for mod, pkg in REQUIRED.items()
        if importlib.util.find_spec(mod) is None
    }
    if not missing:
        return

    print("Installing missing dependencies ...")
    _ensure_pip()

    for mod, pkg in missing.items():
        print(f"  Installing {pkg} ...", end=" ", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("FAILED")
            print(f"  {result.stderr.strip()}")
            print(f"\n  Try manually:  {sys.executable} -m pip install '{pkg}'")
            sys.exit(1)
        print("OK")

    print("  All dependencies ready.\n")

_install_missing()

# ================================================================
# IMPORTS (after dependency check)
# ================================================================

import base64
import time
from elasticsearch import Elasticsearch, helpers
import requests

# ================================================================
# CONFIGURATION — fill these in before running
# ================================================================

# Elastic Cloud cluster URL  (Cloud console > Manage > Copy endpoint)
ES_URL = "https://your-cluster-id.es.region.aws.elastic.cloud:443"

# Elastic API key  (Kibana > Stack Management > API Keys > Create)
ES_API_KEY = "your-elastic-api-key-here"

# Jina AI API key — only needed for multimodal SVG image embedding
# Get yours free at: https://jina.ai/embeddings
JINA_API_KEY = "your-jina-api-key-here"

# Set to True to embed raw SVG files via Jina AI and store dense vectors
# in apex_multimodal_raw_images (extra mile challenge)
IMPORT_SVG_IMAGES = False

# If True: delete and recreate existing indices (WARNING: all data will be lost)
# If False: skip indices that already exist
RECREATE_INDICES = False

# Reduce to 50 if you hit 413 payload-too-large errors
BULK_BATCH_SIZE = 200

# ================================================================
# CONSTANTS
# ================================================================

BASE_DIR     = Path(__file__).parent.parent
MAPPINGS_FILE = Path(__file__).parent / "mappings_reference.json"

NDJSON_FILES = {
    "core": [
        BASE_DIR / "core" / "apex_customer_360.ndjson",
        BASE_DIR / "core" / "apex_customer_interactions.ndjson",
        BASE_DIR / "core" / "apex_financial_transactions.ndjson",
        BASE_DIR / "core" / "apex_operational_telemetry.ndjson",
        BASE_DIR / "core" / "apex_pharma_batches.ndjson",
    ],
    "extra_mile": [
        BASE_DIR / "extra_mile" / "apex_policy_vault.ndjson",
        BASE_DIR / "extra_mile" / "apex_unstructured_vault.ndjson",
        BASE_DIR / "extra_mile" / "apex_technical_docs.ndjson",
        BASE_DIR / "extra_mile" / "apex_it_knowledge_base.ndjson",
        BASE_DIR / "extra_mile" / "apex_knowledge_graph.ndjson",
        BASE_DIR / "extra_mile" / "apex_security_acls.ndjson",
    ],
    "multimodal": [
        BASE_DIR / "multimodal" / "apex_multimodal_assets.ndjson",
        BASE_DIR / "multimodal" / "apex_technical_diagrams.ndjson",
        BASE_DIR / "multimodal" / "apex_it_diagrams.ndjson",
    ],
}

SVG_FOLDERS = {
    "svg_samples":   BASE_DIR / "multimodal" / "svg_samples",
    "tech_diagrams": BASE_DIR / "multimodal" / "tech_diagrams",
    "it_diagrams":   BASE_DIR / "multimodal" / "it_diagrams",
}

SVG_INDEX    = "apex_multimodal_raw_images"
JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL   = "jina-embeddings-v5-omni-small"
JINA_DIMS    = 1024


# ================================================================
# CONNECTION
# ================================================================

def connect():
    print(f"\nConnecting to {ES_URL} ...")
    es = Elasticsearch(ES_URL, api_key=ES_API_KEY, request_timeout=120)
    info = es.info()
    print(f"  Connected — cluster: {info['cluster_name']}, "
          f"ES {info['version']['number']}")
    return es


# ================================================================
# LOAD MAPPINGS
# ================================================================

def load_mappings():
    if not MAPPINGS_FILE.exists():
        print(f"ERROR: mappings_reference.json not found at {MAPPINGS_FILE}")
        print("Make sure mappings_reference.json is in the same folder as this script.")
        sys.exit(1)

    with open(MAPPINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    # Remove the _note metadata key
    return {k: v for k, v in data.items() if not k.startswith("_")}


# ================================================================
# CREATE INDICES
# ================================================================

def create_indices(es, mappings):
    """
    Create all indices defined in mappings_reference.json.

    RECREATE_INDICES = False (default):
        Skip indices that already exist — safe, preserves existing data.

    RECREATE_INDICES = True:
        Delete and recreate any existing index — all data in that index
        will be lost. Useful when you want a clean start or changed the mapping.
    """
    print("\n--- Creating Indices ---")
    if RECREATE_INDICES:
        print("  NOTE: RECREATE_INDICES = True — existing indices will be deleted")

    for index_name, index_def in mappings.items():
        _create_one(es, index_name, index_def)

    # SVG image index — only if multimodal import is enabled
    if IMPORT_SVG_IMAGES:
        svg_mapping = {
            "mappings": {
                "properties": {
                    "asset_id":      {"type": "keyword"},
                    "folder":        {"type": "keyword"},
                    "asset_type":    {"type": "keyword"},
                    "filename":      {"type": "keyword"},
                    "description":   {"type": "text"},
                    "svg_raw":       {"type": "text", "index": False},
                    "image_vector":  {
                        "type": "dense_vector",
                        "dims": JINA_DIMS,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "@timestamp": {"type": "date"},
                }
            }
        }
        _create_one(es, SVG_INDEX, svg_mapping)


def _create_one(es, index_name, index_def):
    """Create a single index, respecting the RECREATE_INDICES flag."""
    exists = es.indices.exists(index=index_name)

    if exists and not RECREATE_INDICES:
        print(f"  {index_name:<45} already exists — skipped")
        return

    if exists and RECREATE_INDICES:
        try:
            es.indices.delete(index=index_name)
            print(f"  {index_name:<45} deleted")
        except Exception as e:
            print(f"  {index_name:<45} ERROR deleting: {e}")
            return

    try:
        es.indices.create(index=index_name, body=index_def)
        print(f"  {index_name:<45} created OK")
    except Exception as e:
        print(f"  {index_name:<45} ERROR creating: {e}")


# ================================================================
# BULK NDJSON IMPORT
# ================================================================

def bulk_import_ndjson(es, filepath):
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  WARNING: file not found — {filepath.name}, skipping")
        return 0, 0

    actions = []
    total = 0
    errors = 0

    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    for i in range(0, len(lines) - 1, 2):
        meta = json.loads(lines[i])
        doc  = json.loads(lines[i + 1])
        action = {
            "_index":  meta["index"]["_index"],
            "_source": doc,
        }
        if doc_id := meta["index"].get("_id"):
            action["_id"] = doc_id
        actions.append(action)

        if len(actions) >= BULK_BATCH_SIZE:
            ok, errs = _flush(es, actions, filepath.name)
            total += ok; errors += errs; actions = []

    if actions:
        ok, errs = _flush(es, actions, filepath.name)
        total += ok; errors += errs

    return total, errors


def _flush(es, actions, label):
    try:
        success, failed = helpers.bulk(
            es, actions, raise_on_error=False, raise_on_exception=False)
        if failed:
            print(f"    WARNING: {len(failed)} failed docs in {label}")
        return success, len(failed)
    except Exception as exc:
        print(f"    ERROR during bulk: {exc}")
        return 0, len(actions)


# ================================================================
# MULTIMODAL — JINA AI DIRECT CALL
# ================================================================

def embed_svg_via_jina(svg_content: str, asset_id: str):
    """
    Call the Jina AI embeddings REST API directly with a base64-encoded SVG.
    Returns a list of 1024 floats, or None on error.

    API: https://api.jina.ai/v1/embeddings
    Model: jina-embeddings-v5-omni-small
    Input type: image (base64)
    """
    svg_b64 = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")

    payload = {
        "model": JINA_MODEL,
        "input": [{"image": svg_b64}],
        "normalized": True,
    }
    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        resp = requests.post(JINA_API_URL, headers=headers,
                             json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except requests.HTTPError as e:
        print(f"    ERROR {asset_id}: HTTP {e.response.status_code} "
              f"— {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"    ERROR {asset_id}: {e}")
        return None


def import_svg_images(es):
    if not JINA_API_KEY or JINA_API_KEY == "your-jina-api-key-here":
        print("  SKIPPED — set JINA_API_KEY to enable multimodal SVG embedding")
        return

    asset_type_map = {
        "svg_samples":   "chromatography_chart",
        "tech_diagrams": "technical_engineering_diagram",
        "it_diagrams":   "it_architecture_diagram",
    }

    actions  = []
    total_ok = 0
    total_err = 0

    for folder_key, folder_path in SVG_FOLDERS.items():
        if not folder_path.exists():
            print(f"    Folder not found: {folder_path.name} — skipping")
            continue

        svg_files = sorted(folder_path.glob("*.svg"))
        print(f"\n    {folder_key}: {len(svg_files)} SVG files")

        for svg_path in svg_files:
            svg_raw = svg_path.read_text(encoding="utf-8")
            print(f"      {svg_path.name} — calling Jina AI ...", end=" ", flush=True)

            vector = embed_svg_via_jina(svg_raw, svg_path.stem)
            if vector is None:
                print("FAILED")
                total_err += 1
                continue

            print(f"OK ({len(vector)}d)")
            total_ok += 1

            actions.append({
                "_index": SVG_INDEX,
                "_id":    svg_path.stem,
                "_source": {
                    "asset_id":     svg_path.stem,
                    "folder":       folder_key,
                    "asset_type":   asset_type_map.get(folder_key, "diagram"),
                    "filename":     svg_path.name,
                    "description":  f"{asset_type_map.get(folder_key,'diagram')} — {svg_path.stem}",
                    "svg_raw":      svg_raw,
                    "image_vector": vector,
                    "@timestamp":   "2025-01-01T00:00:00Z",
                },
            })

            time.sleep(1.0)   # respect Jina free-tier rate limit (~60 req/min)

            if len(actions) >= BULK_BATCH_SIZE:
                _flush(es, actions, "svg_images")
                actions = []

    if actions:
        _flush(es, actions, "svg_images")

    print(f"\n  SVG images embedded and indexed: {total_ok} OK, {total_err} errors")


# ================================================================
# SUMMARY
# ================================================================

def print_summary(es):
    print("\n" + "=" * 60)
    print("IMPORT COMPLETE — Index Summary")
    print("=" * 60)
    try:
        print(es.cat.indices(
            index="apex_*", h="index,docs.count,store.size",
            v=True, s="index"))
    except Exception:
        print("  (could not retrieve stats — check Kibana)")

    print("\nNext steps:")
    print("  1. Kibana > Dev Tools > GET apex_customer_360/_count")
    print("  2. Test semantic search:")
    print('     GET apex_customer_interactions/_search')
    print('     { "query": { "semantic": { "field": "text",')
    print('                               "query": "fraud complaint urgent" } } }')
    print("  3. Configure RBAC in Kibana > Stack Management > Roles")
    print("  4. Build your agent in Elastic Agent Builder or a custom app")


# ================================================================
# MAIN
# ================================================================

def main():
    if "your-cluster-id" in ES_URL:
        print("ERROR: Please set ES_URL at the top of this script.")
        sys.exit(1)
    if "your-elastic-api-key" in ES_API_KEY:
        print("ERROR: Please set ES_API_KEY at the top of this script.")
        sys.exit(1)

    es = connect()

    # Load mappings and create all indices first
    mappings = load_mappings()
    create_indices(es, mappings)

    # Import all NDJSON files
    grand_total = 0
    grand_errors = 0

    for group, files in NDJSON_FILES.items():
        print(f"\n{'='*60}")
        print(f"Group: {group.upper()}")
        print("=" * 60)
        for filepath in files:
            print(f"\n  Importing {Path(filepath).name} ...")
            ok, err = bulk_import_ndjson(es, filepath)
            status = "OK" if err == 0 else f"WARN ({err} errors)"
            print(f"  {status} — {ok} documents indexed")
            grand_total  += ok
            grand_errors += err

    if IMPORT_SVG_IMAGES:
        print(f"\n{'='*60}")
        print("Group: MULTIMODAL SVG IMAGES — Jina AI embedding")
        print("=" * 60)
        import_svg_images(es)

    print(f"\n{'='*60}")
    print(f"DONE — Documents indexed: {grand_total}"
          + (f"  (errors: {grand_errors})" if grand_errors else ""))
    print("=" * 60)

    print_summary(es)


if __name__ == "__main__":
    main()
