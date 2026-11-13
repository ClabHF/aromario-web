#!/usr/bin/env python3
"""One-off Awin feed retrieval for Lapert/Lunzo.

The Awin data-feed key is read only from the AWIN_FEED_APIKEY environment
variable (a GitHub Actions secret).  Feed-list URLs and download URLs are kept
in memory only: they are never printed, written to disk, or included in errors.
Outputs contain product CSV files and non-sensitive verification metadata.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


TARGETS = {
    "54357": ("lapert-cz", "Lapert CZ"),
    "54359": ("lapert-sk", "Lapert SK"),
    "114104": ("lunzo-at", "Lunzo AT"),
    "54355": ("lunzo-cz", "Lunzo CZ"),
    "69786": ("lunzo-de", "Lunzo DE"),
    "40452": ("lunzo-hu", "Lunzo HU"),
    "40456": ("lunzo-ro", "Lunzo RO"),
    "54353": ("lunzo-sk", "Lunzo SK"),
    "40454": ("lunzo-pl", "Lunzo PL"),
}

OUT_DIR = Path("salida_awin_lapert_lunzo")
PUBLISHER_ID = "3146426"
BRAND_COLUMNS = {
    "brand",
    "brand_name",
    "manufacturer",
    "manufacturer_name",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def get_key() -> str:
    key = os.environ.get("AWIN_FEED_APIKEY", "").strip()
    if not key:
        fail("AWIN_FEED_APIKEY secret is not available")
    return key


def open_url(url: str, timeout: int):
    """Open a URL without allowing exception text or logs to expose it."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Aromario feed retrieval)",
            "Accept": "*/*",
        },
    )
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from None
    except Exception as exc:
        raise RuntimeError(f"request failed ({type(exc).__name__})") from None


def fetch_csv(url: str, source: str) -> list[dict[str, str]]:
    try:
        with open_url(url, timeout=300) as response:
            raw = response.read()
    except RuntimeError as exc:
        fail(f"could not download the Awin {source} feed list: {exc}")
    text = raw.decode("utf-8-sig", "replace")
    try:
        return list(csv.DictReader(io.StringIO(text)))
    except Exception:
        fail(f"the Awin {source} feed list was not readable as CSV")


def fetch_feed_lists(key: str) -> dict[str, list[dict[str, str]]]:
    """Fetch the current Darwin list and the legacy productdata list.

    The legacy endpoint used by the nightly scripts returns an older/smaller
    list.  The current Awin documentation points to the Darwin feed-list URL;
    both use the same data-feed key.  URLs are never logged or saved.
    """
    sources = {
        "darwin": (
            "https://ui.awin.com/productdata-darwin-download/publisher/"
            f"{PUBLISHER_ID}/{key}/1/feedList"
        ),
        "legacy": f"https://productdata.awin.com/datafeed/list/apikey/{key}",
    }
    result: dict[str, list[dict[str, str]]] = {}
    errors: list[str] = []
    for source, url in sources.items():
        try:
            result[source] = fetch_csv(url, source)
        except RuntimeError as exc:
            errors.append(str(exc))
    if not result:
        fail("; ".join(errors) if errors else "no Awin feed list could be downloaded")
    return result


def normalized(row: dict[str, str]) -> dict[str, str]:
    result = {}
    for key, value in row.items():
        if key is None:
            continue
        result[key.strip().lower()] = (value or "").strip()
    return result


def select_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], list[str]]:
    selected: list[dict[str, object]] = []
    seen_fids: set[str] = set()
    fields_by_fid: dict[str, dict[str, str]] = {}

    for original in rows:
        row = normalized(original)
        advertiser_id = row.get("advertiser id", "")
        if advertiser_id not in TARGETS:
            continue
        fid = row.get("feed id", "")
        if not fid or fid in seen_fids:
            continue
        seen_fids.add(fid)
        fields_by_fid[fid] = row
        slug, label = TARGETS[advertiser_id]
        selected.append(
            {
                "advertiser_id": advertiser_id,
                "slug": slug,
                "label": label,
                "advertiser_name": row.get("advertiser name", ""),
                "feed_id": fid,
                "feed_name": row.get("feed name", ""),
                "datafeed_format": row.get("datafeed format", ""),
                "language": row.get("language", ""),
                "vertical": row.get("vertical", ""),
                "membership_status": row.get("membership status", ""),
                "products_declared": row.get("no of products", ""),
                "last_imported": row.get("last imported", ""),
            }
        )

    selected.sort(key=lambda item: (str(item["slug"]), int(str(item["feed_id"]))))
    missing = [
        advertiser_id
        for advertiser_id in TARGETS
        if not any(item["advertiser_id"] == advertiser_id for item in selected)
    ]
    # Keep private download URLs only in process memory.
    for item in selected:
        item["_download_url"] = fields_by_fid[str(item["feed_id"])].get("url", "")
    return selected, missing


def safe_public_rows(selected: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in selected
    ]


def write_inventory(selected: list[dict[str, object]], missing: list[str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "advertisers_targeted": len(TARGETS),
        "feeds_found": len(selected),
        "advertisers_missing": missing,
        "feeds": safe_public_rows(selected),
    }
    (OUT_DIR / "inventario.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Awin Lapert/Lunzo feed inventory",
        "",
        f"Feeds found: {len(selected)}",
        f"Advertisers missing: {', '.join(missing) if missing else 'none'}",
        "",
    ]
    for item in selected:
        lines.append(
            f"- {item['label']} ({item['advertiser_id']}): FID {item['feed_id']}; "
            f"format={item['datafeed_format']}; language={item['language']}; "
            f"products_declared={item['products_declared']}; feed_name={item['feed_name']}"
        )
    (OUT_DIR / "inventario.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_gzip_csv(path: Path) -> dict[str, object]:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)

    row_count = 0
    header: list[str] = []
    # gzip.open also proves the gzip stream can be traversed to EOF.
    with gzip.open(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            header = []
        for _ in reader:
            row_count += 1

    header_clean = [column.strip() for column in header]
    header_lower = {column.lower() for column in header_clean}
    brand_column = next(
        (column for column in header_clean if column.lower() in BRAND_COLUMNS), ""
    )
    return {
        "bytes": path.stat().st_size,
        "rows": row_count,
        "header": header_clean,
        "brand_column": brand_column,
        "brand_column_present": bool(brand_column),
        "gzip_ok": True,
        "sha256": sha.hexdigest(),
    }


def write_diagnostic(sources: dict[str, list[dict[str, str]]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    diagnostic: dict[str, object] = {"sources": {}}
    for source, rows in sources.items():
        headers = []
        if rows:
            headers = [str(key).strip() for key in rows[0].keys() if key is not None]
        matches = []
        active_rows = []
        membership_counts: dict[str, int] = {}
        format_counts: dict[str, int] = {}
        region_counts: dict[str, int] = {}
        language_counts: dict[str, int] = {}
        advertiser_ids: set[str] = set()
        for original in rows:
            row = normalized(original)
            advertiser_id = row.get("advertiser id", "")
            if advertiser_id:
                advertiser_ids.add(advertiser_id)
            status = row.get("membership status", "")
            if status:
                membership_counts[status] = membership_counts.get(status, 0) + 1
            data_format = row.get("datafeed format", "")
            if data_format:
                format_counts[data_format] = format_counts.get(data_format, 0) + 1
            region = row.get("primary region", "")
            if region:
                region_counts[region] = region_counts.get(region, 0) + 1
            language = row.get("language", "")
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1
            public = {
                key: value
                for key, value in row.items()
                if "url" not in key and "link" not in key
            }
            if status.lower() == "active":
                active_rows.append(public)
            joined_values = " ".join(row.values()).lower()
            if "lapert" in joined_values or "lunzo" in joined_values:
                matches.append(public)
        diagnostic["sources"][source] = {
            "row_count": len(rows),
            "headers": headers,
            "unique_advertiser_ids": len(advertiser_ids),
            "membership_status_counts": membership_counts,
            "datafeed_format_counts": format_counts,
            "primary_region_counts": region_counts,
            "language_counts": language_counts,
            "active_rows": active_rows,
            "name_matches": matches,
            "target_ids_present": sorted(set(TARGETS) & advertiser_ids),
        }
        print(
            f"Diagnostic {source}: {len(rows)} rows, {len(advertiser_ids)} advertisers, "
            f"{len(matches)} Lapert/Lunzo name matches"
        )
    (OUT_DIR / "diagnostico.json").write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8"
    )


PROBE_COLUMNS = (
    "aw_product_id,product_name,brand_name,merchant_id,merchant_name,data_feed_id"
)


def probe_advertiser(key: str, advertiser_id: str) -> dict[str, object]:
    """Try the Create-a-Feed merchant filter (mid/<advertiser id>) for one
    advertiser and report only counts and feed IDs. Nothing is kept."""
    slug, label = TARGETS[advertiser_id]
    url = (
        f"https://productdata.awin.com/datafeed/download/apikey/{key}"
        f"/language/any/mid/{advertiser_id}/columns/{PROBE_COLUMNS}"
        "/format/csv/delimiter/%2C/compression/gzip/adultcontent/1/"
    )
    raw_path = OUT_DIR / f".probe_{advertiser_id}.raw"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open_url(url, timeout=1800) as response, raw_path.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    except RuntimeError as exc:
        return {"advertiser_id": advertiser_id, "advertiser": label, "error": str(exc)}

    size = raw_path.stat().st_size
    result: dict[str, object] = {
        "advertiser_id": advertiser_id,
        "advertiser": label,
        "bytes": size,
    }
    try:
        with raw_path.open("rb") as handle:
            magic = handle.read(2)
        opener = gzip.open if magic == b"\x1f\x8b" else open
        feed_ids: dict[str, int] = {}
        merchant_ids: set[str] = set()
        rows = 0
        header: list[str] = []
        sample_names: list[str] = []
        with opener(raw_path, "rt", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            for row in reader:
                rows += 1
                fid = (row.get("data_feed_id") or "").strip()
                if fid:
                    feed_ids[fid] = feed_ids.get(fid, 0) + 1
                mid = (row.get("merchant_id") or "").strip()
                if mid:
                    merchant_ids.add(mid)
                if len(sample_names) < 3 and row.get("product_name"):
                    sample_names.append(row["product_name"].strip())
        result.update(
            {
                "rows": rows,
                "header": header,
                "brand_column_present": any(
                    column.strip().lower() in BRAND_COLUMNS for column in header
                ),
                "merchant_ids": sorted(merchant_ids),
                "feed_ids": feed_ids,
                "sample_product_names": sample_names,
            }
        )
    except Exception as exc:
        result["error"] = f"unreadable response ({type(exc).__name__})"
    finally:
        if raw_path.exists():
            raw_path.unlink()
    print(
        f"Probe {label}: rows={result.get('rows')} feeds={result.get('feed_ids')} "
        f"error={result.get('error', '')}"
    )
    return result


def download_one(item: dict[str, object]) -> dict[str, object]:
    fid = str(item["feed_id"])
    slug = str(item["slug"])
    url = str(item.get("_download_url", ""))
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "productdata.awin.com":
        fail(f"FID {fid} has no usable Awin download URL in the feed list")

    final_path = OUT_DIR / f"{slug}_awin_F{fid}.csv.gz"
    temp_path = OUT_DIR / f".{slug}_F{fid}.part"
    raw_path = OUT_DIR / f".{slug}_F{fid}.raw"
    for path in (temp_path, raw_path):
        if path.exists():
            path.unlink()

    print(f"Downloading {item['label']} FID {fid}", flush=True)
    try:
        with open_url(url, timeout=1800) as response, raw_path.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
    except RuntimeError as exc:
        fail(f"download failed for {item['label']} FID {fid}: {exc}")

    if raw_path.stat().st_size == 0:
        fail(f"download was empty for {item['label']} FID {fid}")

    with raw_path.open("rb") as handle:
        magic = handle.read(2)
    if magic == b"\x1f\x8b":
        shutil.move(str(raw_path), str(final_path))
    else:
        # The list URL can return a plain CSV. Normalize it to CSV.GZ.
        with raw_path.open("rb") as source, gzip.open(
            temp_path, "wb", compresslevel=6
        ) as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        raw_path.unlink()
        shutil.move(str(temp_path), str(final_path))

    result = {
        "advertiser_id": item["advertiser_id"],
        "advertiser": item["label"],
        "slug": slug,
        "feed_id": fid,
        "feed_name": item["feed_name"],
        "datafeed_format": item["datafeed_format"],
        "language": item["language"],
        "products_declared": item["products_declared"],
        "file": final_path.name,
    }
    result.update(verify_gzip_csv(final_path))
    print(
        f"Verified {item['label']} FID {fid}: {result['rows']} rows, "
        f"{result['bytes']} bytes, brand={result['brand_column'] or 'MISSING'}",
        flush=True,
    )
    return result


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "inventory"
    if mode not in {"inventory", "download", "diagnose", "probe"}:
        fail("mode must be inventory, download, diagnose or probe")

    key = get_key()
    sources = fetch_feed_lists(key)
    rows = [row for source in ("darwin", "legacy") for row in sources.get(source, [])]
    selected, missing = select_rows(rows)
    write_inventory(selected, missing)
    print(f"Feed inventory: {len(selected)} feeds; missing advertisers: {len(missing)}")

    if mode == "diagnose":
        write_diagnostic(sources)
        return 0

    if mode == "probe":
        # 54355 = Lunzo CZ (target). 131715 = Scento Germany (control: it has a
        # known feed in the list, FID 118934). TARGETS lookup is bypassed for
        # the control by temporarily extending the map.
        TARGETS.setdefault("131715", ("scento-de", "Scento Germany (control)"))
        results = [probe_advertiser(key, "54355"), probe_advertiser(key, "131715")]
        (OUT_DIR / "probe.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 0

    if mode == "download":
        if missing:
            fail("cannot download: some target advertisers have no feeds in the list")
        results = []
        for item in selected:
            results.append(download_one(item))
        (OUT_DIR / "verificacion.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# Awin Lapert/Lunzo download verification",
            "",
            f"Files: {len(results)}",
            "",
        ]
        for item in results:
            lines.append(
                f"- {item['file']}: {item['rows']} rows; {item['bytes']} bytes; "
                f"brand_column={item['brand_column'] or 'MISSING'}; gzip=OK"
            )
        (OUT_DIR / "verificacion.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
