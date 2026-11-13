#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. Made with AI agents working in MV2's name.
"""withdrawn_ror_census: DOIs that carry a withdrawn ROR organisation ID.

PREREG-ROR-1. For every ROR record whose status is "withdrawn" (ROR API v2;
ROR defines withdrawn as "a record that was created in error, such as a
duplicate record"), this script:
  * reads the record's status in ROR data v1.16 (2022-12-06), the release that
    restored about 1,200 records as withdrawn;
  * counts Crossref works carrying the ID (filter ror-id), in total and created
    from 2023-01-01;
  * counts DataCite DOIs carrying it as a creator or contributor affiliation or
    as a funder, in total, created 2023-2026 (and per year), and from Zenodo;
  * checks Zenodo's affiliation vocabulary for the ID and, when Zenodo DOIs
    carry it, where it ranks against its successor when Zenodo's affiliation
    search is given the record's own name.
Outputs (in --out-dir): withdrawn.csv, summary.json, sanity.json.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

VERSION = "0.1.0"
MAILTO = "mv2@munimtech.com"
UA = "withdrawn-ror-census/%s (MV2, Munim, Inc.; mailto:%s)" % (VERSION, MAILTO)
ROR_API = "https://api.ror.org/v2/organizations"
CROSSREF = "https://api.crossref.org/works"
DATACITE = "https://api.datacite.org/dois"
ZENODO_AFF = "https://zenodo.org/api/affiliations"
V116_URL = ("https://zenodo.org/api/records/7407214/files/"
            "v1.16-2022-12-06-ror-data.zip/content")
V116_NAME = "v1.16-2022-12-06-ror-data.zip"
V116_MD5 = "90539b28d31919f202a10e1b5831c3d1"
POST_YEARS = (2023, 2024, 2025, 2026)
SANITY_HMS = "03wevmz92"            # Harvard Medical School (withdrawn)
SANITY_HMS_SUCCESSOR = "03vek6s52"  # Harvard University
FIELDS = ["id", "name", "v116_status", "successors", "parents",
          "cr_total", "cr_post", "dc_total", "dc_post",
          "dc_2023", "dc_2024", "dc_2025", "dc_2026", "zen_post",
          "dc_clients", "zen_vocab", "zen_rank", "zen_succ_rank",
          "zen_above_successor", "error"]

_ROR_RE = re.compile(r"(?:https?://)?(?:www\.)?ror\.org/(0[a-z0-9]{8})\s*$", re.I)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def short_ror(x):
    """'https://ror.org/03wevmz92' or '03WEVMZ92' -> '03wevmz92'; else ''."""
    if not x:
        return ""
    x = str(x).strip()
    m = _ROR_RE.match(x)
    if m:
        return m.group(1).lower()
    if re.fullmatch(r"0[a-z0-9]{8}", x, re.I):
        return x.lower()
    return ""


def parse_ror_v2(item):
    names = item.get("names") or []
    disp = ""
    for n in names:
        if "ror_display" in (n.get("types") or []):
            disp = n.get("value") or ""
            break
    if not disp and names:
        disp = names[0].get("value") or ""
    succ, par = [], []
    for r in item.get("relationships") or []:
        t = (r.get("type") or "").lower()
        rid = short_ror(r.get("id"))
        if t == "successor" and rid:
            succ.append(rid)
        elif t == "parent" and rid:
            par.append(rid)
    return {"id": short_ror(item.get("id")), "name": disp,
            "status": item.get("status") or "",
            "successors": succ, "parents": par}


def statuses_from_records(records):
    out = {}
    for r in records:
        rid = short_ror(r.get("id"))
        if rid:
            out[rid] = r.get("status") or ""
    return out


def datacite_query(rid):
    u = "https://ror.org/" + rid
    fields = ("creators.affiliation.affiliationIdentifier",
              "contributors.affiliation.affiliationIdentifier",
              "fundingReferences.funderIdentifier")
    return " OR ".join('%s:"%s"' % (f, u) for f in fields)


def clean_query(name):
    s = re.sub(r"[^\w\s]", " ", name or "")
    return re.sub(r"\s+", " ", s).strip()


def rank_in_hits(hits, rid):
    for i, h in enumerate(hits, 1):
        if short_ror(h.get("id")) == rid:
            return i
        for ident in h.get("identifiers") or []:
            if ident.get("scheme") == "ror" and short_ror(ident.get("identifier")) == rid:
                return i
    return None


def above(rank, succ_rank):
    """True if the withdrawn record is listed and ranks above every successor."""
    return rank is not None and (succ_rank is None or rank < succ_rank)


def _n(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def summarize(rows):
    w1 = [r for r in rows if r.get("v116_status") == "withdrawn"]

    def S(key, rs):
        return sum(_n(r.get(key)) for r in rs)

    used = [r for r in w1 if _n(r.get("dc_post")) > 0]
    used_any = [r for r in w1 if _n(r.get("dc_post")) > 0 or _n(r.get("cr_post")) > 0]
    dc_post, zen_post, cr_post = S("dc_post", w1), S("zen_post", w1), S("cr_post", w1)
    years = {str(y): S("dc_%d" % y, w1) for y in POST_YEARS}
    vocab_w = [r for r in rows if r.get("zen_vocab") == "withdrawn"]
    big = [r for r in w1 if _n(r.get("zen_post")) >= 10]
    big_above = [r for r in big if r.get("zen_above_successor") == "1"]
    with_succ = [r for r in used_any if r.get("successors")]
    top = sorted(w1, key=lambda r: -(_n(r.get("dc_post")) + _n(r.get("cr_post"))))[:40]
    m = {
        "n_withdrawn_now": len(rows),
        "n_w1": len(w1),
        "n_errors": sum(1 for r in rows if r.get("error")),
        "w1_used_dc_post": len(used),
        "w1_used_any_post": len(used_any),
        "w1_dc_post_pairs": dc_post,
        "w1_zen_post_pairs": zen_post,
        "w1_cr_post_pairs": cr_post,
        "w1_dc_post_by_year": years,
        "zen_share": (zen_post / dc_post) if dc_post else None,
        "cr_to_dc_ratio": (cr_post / dc_post) if dc_post else None,
        "succ_share_used_any": (len(with_succ) / len(used_any)) if used_any else None,
        "vocab_withdrawn_share": (len(vocab_w) / len(rows)) if rows else None,
        "n_big_zen": len(big),
        "big_above_share": (len(big_above) / len(big)) if big else None,
        "all_dc_post_pairs": S("dc_post", rows),
        "all_cr_post_pairs": S("cr_post", rows),
        "top": [{k: r.get(k) for k in ("id", "name", "successors", "dc_post",
                                        "zen_post", "cr_post", "zen_rank",
                                        "zen_succ_rank")} for r in top],
    }
    p = {
        "P2_60_to_500_w1_ids_used": 60 <= len(used) <= 500,
        "P3_ge_3000_dc_pairs": dc_post >= 3000,
        "P4_zenodo_share_ge_60pct": bool(dc_post) and zen_post / dc_post >= 0.60,
        "P5_2025_ge_3x_2023": years["2025"] >= 3 * years["2023"],
        "P6_crossref_lt_half_datacite": cr_post < 0.5 * dc_post,
        "P7_ge_80pct_used_have_successor": bool(used_any) and len(with_succ) / len(used_any) >= 0.80,
        "P8_ge_95pct_in_zenodo_vocab_withdrawn": bool(rows) and len(vocab_w) / len(rows) >= 0.95,
        "P9_ge_half_big_rank_above_successor": bool(big) and len(big_above) / len(big) >= 0.5,
    }
    return {"version": VERSION, "metrics": m, "predictions": p}


def sanity(rows):
    by = {r.get("id"): r for r in rows}
    h = by.get(SANITY_HMS)
    c = {"hms_present": h is not None}
    if h is not None:
        c["hms_w1"] = h.get("v116_status") == "withdrawn"
        c["hms_dc_total_ge_1150"] = _n(h.get("dc_total")) >= 1150
        c["hms_zen_post_ge_950"] = _n(h.get("zen_post")) >= 950
        c["hms_cr_total_ge_220"] = _n(h.get("cr_total")) >= 220
        c["hms_zen_vocab_withdrawn"] = h.get("zen_vocab") == "withdrawn"
        c["hms_zen_rank_1"] = _n(h.get("zen_rank")) == 1
        c["hms_successor_harvard"] = SANITY_HMS_SUCCESSOR in (h.get("successors") or "").split(";")
        c["hms_years_sum_eq_post"] = sum(_n(h.get("dc_%d" % y)) for y in POST_YEARS) == _n(h.get("dc_post"))
    c["n_withdrawn_ge_1400"] = len(rows) >= 1400
    c["v116_matched"] = sum(1 for r in rows if r.get("v116_status") not in ("", "absent")) >= 1000
    c["errors_le_1pct"] = sum(1 for r in rows if r.get("error")) <= max(1, len(rows) // 100)
    return {"all_pass": all(c.values()), "checks": c}


# ---------------------------------------------------------------- network

def get_json(url, params=None, pause=0.0, tries=6):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe=":,")
    last = None
    for k in range(tries):
        if pause:
            time.sleep(pause)
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = "HTTP %d" % e.code
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(120, 5 * 2 ** k))
                continue
            raise
        except (OSError, ValueError) as e:
            last = repr(e)
            time.sleep(min(120, 5 * 2 ** k))
    raise RuntimeError("giving up on %s: %s" % (url, last))


def download(url, path):
    tmp = path + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(tmp, path)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_v116_status(path):
    with zipfile.ZipFile(path) as z:
        js = sorted((i for i in z.infolist() if i.filename.endswith(".json")),
                    key=lambda i: -i.file_size)
        with z.open(js[0]) as f:
            try:
                import ijson
                return statuses_from_records(ijson.items(f, "item"))
            except ImportError:
                return statuses_from_records(json.load(f))


def fetch_withdrawn(pause):
    items, page, total = [], 1, 0
    while True:
        d = get_json(ROR_API, {"filter": "status:withdrawn", "page": page}, pause=pause)
        batch = (d or {}).get("items") or []
        total = (d or {}).get("number_of_results", 0)
        items.extend(parse_ror_v2(x) for x in batch)
        if not batch or len(items) >= total:
            break
        page += 1
    return items, total


def crossref_count(rid, post, pause=0.15):
    f = "ror-id:" + rid + (",from-created-date:2023-01-01" if post else "")
    d = get_json(CROSSREF, {"filter": f, "rows": 0, "mailto": MAILTO}, pause=pause)
    return int(d["message"]["total-results"])


def datacite_count(rid, pause=0.15, created=None, client=None, facets=False):
    p = {"query": datacite_query(rid), "page[size]": 0}
    if created:
        p["created"] = ",".join(str(y) for y in created)
    if client:
        p["client-id"] = client
    if facets:
        p["disable-facets"] = "false"
    d = get_json(DATACITE, p, pause=pause)
    meta = d.get("meta") or {}
    return int(meta.get("total") or 0), meta


def zenodo_vocab(rid, pause=1.0):
    d = get_json(ZENODO_AFF + "/" + rid, pause=pause)
    if d is None:
        return "absent"
    return d.get("status") or "no-status"


def zenodo_ranks(name, rid, successors, pause=1.0):
    d = get_json(ZENODO_AFF, {"q": clean_query(name), "size": 10}, pause=pause)
    hits = ((d or {}).get("hits") or {}).get("hits") or []
    r = rank_in_hits(hits, rid)
    sr = [x for x in (rank_in_hits(hits, s) for s in successors) if x]
    return r, (min(sr) if sr else None)


def census_row(it, v116):
    rid = it["id"]
    row = {"id": rid, "name": it["name"], "successors": ";".join(it["successors"]),
           "parents": ";".join(it["parents"]), "v116_status": v116.get(rid, "absent"),
           "cr_total": 0, "cr_post": 0, "dc_total": 0, "dc_post": 0, "zen_post": 0,
           "dc_clients": "", "zen_vocab": "", "zen_rank": "", "zen_succ_rank": "",
           "zen_above_successor": "", "error": ""}
    for y in POST_YEARS:
        row["dc_%d" % y] = 0
    try:
        row["cr_total"] = crossref_count(rid, False)
        if row["cr_total"]:
            row["cr_post"] = crossref_count(rid, True)
        tot, meta = datacite_count(rid, facets=True)
        row["dc_total"] = tot
        row["dc_clients"] = ";".join("%s=%s" % (c.get("id"), c.get("count"))
                                     for c in (meta.get("clients") or [])[:5])
        if tot:
            row["dc_post"] = datacite_count(rid, created=POST_YEARS)[0]
            for y in POST_YEARS:
                row["dc_%d" % y] = datacite_count(rid, created=[y])[0]
            row["zen_post"] = datacite_count(rid, created=POST_YEARS, client="cern.zenodo")[0]
        row["zen_vocab"] = zenodo_vocab(rid)
        if row["zen_post"] > 0:
            r, s = zenodo_ranks(it["name"], rid, it["successors"])
            row["zen_rank"] = r or ""
            row["zen_succ_rank"] = s or ""
            row["zen_above_successor"] = "1" if above(r, s) else "0"
    except Exception as e:  # keep going; counted in sanity
        row["error"] = repr(e)[:300]
    return row


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", default="/data/ror")
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--limit", type=int, default=0, help="debug: first N records only")
    a = ap.parse_args(argv)
    os.makedirs(a.data_dir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    log("withdrawn_ror_census", VERSION)
    zp = os.path.join(a.data_dir, V116_NAME)
    if not os.path.exists(zp) or md5(zp) != V116_MD5:
        log("downloading", V116_URL)
        download(V116_URL, zp)
    zmd5 = md5(zp)
    log("v1.16 md5", zmd5, "expected", V116_MD5)
    v116 = load_v116_status(zp)
    log("v1.16 records", len(v116), "withdrawn",
        sum(1 for s in v116.values() if s == "withdrawn"))
    items, total = fetch_withdrawn(pause=6.5)
    log("ROR API withdrawn records", len(items), "of", total)
    if a.limit:
        items = items[:a.limit]
    rows = []
    for i, it in enumerate(items, 1):
        rows.append(census_row(it, v116))
        if i % 50 == 0:
            log(i, "done; last", it["id"], rows[-1]["dc_total"], rows[-1]["cr_total"])
            write_csv(rows, os.path.join(a.out_dir, "withdrawn_partial.csv"))
    write_csv(rows, os.path.join(a.out_dir, "withdrawn.csv"))
    s = summarize(rows)
    s["v116_md5"] = zmd5
    s["ror_api_total"] = total
    s["run_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    sn = sanity(rows)
    with open(os.path.join(a.out_dir, "sanity.json"), "w", encoding="utf-8") as f:
        json.dump(sn, f, indent=1)
    log("sanity", json.dumps(sn))
    log("predictions", json.dumps(s["predictions"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
