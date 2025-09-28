#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Workiz multi-account fetcher (THIS YEAR; created OR scheduled window)
- Jobs: statuses = ['Submitted','In Progress','Done','Done Pending Approval','Canceled']
- Include a job if: (created in THIS_YEAR) OR (scheduled in THIS_YEAR)
- Leads: no status filter (this year)
- Robust pagination with retries/backoff
- Exports:
    - jobs_*.csv  (only kept jobs)
    - leads_*.csv
    - counts_summary_*.csv  (per-account job counts by status + leads)
- Console debug per account: Account, endpoint (redacted), lead count, job count by status
- No "missing" audit in this version

Requires: requests, pandas
"""

import os
import json
import time
import uuid as _uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any

import requests
import pandas as pd

# ====================== CONFIG ======================

# Cross-platform, Linux-safe default export root. Override with env var WORKIZ_EXPORT_ROOT
EXPORT_ROOT = os.getenv("WORKIZ_EXPORT_ROOT", "/workspace/workiz_exports")
os.makedirs(EXPORT_ROOT, exist_ok=True)

NOW = datetime.now(timezone.utc)
THIS_YEAR = NOW.year
THIS_YEAR_START = f"{THIS_YEAR}-01-01"

# Wider window so we can see older-created jobs that may be scheduled in THIS_YEAR.
# We'll locally keep only those with scheduled date in THIS_YEAR (union with created-in-year).
WIDE_START = f"{THIS_YEAR-1}-01-01"  # e.g., 2024-01-01 when THIS_YEAR==2025

JOB_STATUSES = ["Submitted", "In Progress", "Done", "Done Pending Approval", "Canceled"]

# Request/Retry tuning
PAGE_SIZE = 100
TIMEOUT_S = 45
MAX_RETRIES = 4
BACKOFF_BASE_S = 1.5

# Optional: a rough expected jobs number to eyeball — purely informative.
EXPECTED_TOTAL_JOBS = 15000  # your “looking for ~15k jobs” note

# ====================== ACCOUNTS ======================

accounts: List[Dict[str, str]] = [
    {"name": "Rolling Suds (Corp) of East Nashville", "token": "api_y1ehsg2xywnxmglozlemkqhfqzdy94ve"},
    {"name": "Rolling Suds Cincinnati-Dayton", "token": "api_1jdtpxkcy7iq8shb3ilebojfh10qe7r9"},
    {"name": "Rolling Suds Corpus Christi - Victoria TX", "token": "api_mj0ib972pck4j0uzpi7wsqd11dmow6x4"},
    {"name": "Rolling Suds Cranberry-McKnight", "token": "api_upcrgvn29c3vdxihjylez321hjwzagne"},
    {"name": "Rolling Suds Durham-North Raleigh", "token": "api_gwzqtub5e8s7dktx5tfg8x7n13tuymiz"},
    {"name": "Rolling Suds of Sarasota - Bradenton", "token": "api_c0qfmnxr97hnv4q5aj4b08z9tsiw593d"},
    {"name": "Rolling Suds of Alexandria-Arlington", "token": "api_by5i0kw8e6ul5793nevcbtwlr8w5ypbt"},
    {"name": "Rolling Suds of AR-Fayetteville", "token": "api_fw61xy38hrsovt63otyb7m3kaqw6vz01"},
    {"name": "Rolling Suds of Athens, GA", "token": "api_xahbsp587xe096l3xuqp6l32wsmxqc0a"},
    {"name": "Rolling Suds of Austin-Westlake", "token": "api_phojd5q4glxirfno0lecbjiqa7lkctdm"},
    {"name": "Rolling Suds of Beaverton", "token": "api_4bv8mdlthv6k1buw19y2qprmb6ckao14"},
    {"name": "Rolling Suds of Boca Raton-Pompano Beach", "token": "api_8zscmo9iis0h9qro6tz2houmlbgeokpa"},
    {"name": "Rolling Suds of Boise - Meridian", "token": "api_y5j87ir36t5824g1cmekwfv0450xwoyb"},
    {"name": "Rolling Suds of Carlsbad-San Diego", "token": "api_v6xng28qibcyxnme12gj8va42ro79czi"},
    {"name": "Rolling Suds of Charlotte", "token": "api_qt9p7sduxn7k4lodvgar9dkmx9wz6ja3"},
    {"name": "Rolling Suds of Chattanooga", "token": "api_mh1kio30mqbg87zocwygase4b24l8xew"},
    {"name": "Rolling Suds of Cincinnati-Northeast Mason", "token": "api_v0dj1xphed6o27widb548eovql96musf"},
    {"name": "Rolling Suds of Columbia-Lexington", "token": "api_71avpk5l5jk704vakr9f34luolhq62pe"},
    {"name": "Rolling Suds of Columbus", "token": "api_v23qhjyo5376p8yf4s8xi1mvzdjs740u"},
    {"name": "Rolling Suds of Dallas-Irving", "token": "api_70ljft5axn4ey8oi4gje1z8q3k4rl0ui"},
    {"name": "Rolling Suds Of Denver-Parker", "token": "api_z37xdsr4smrdab34pjfr7atdnp8wu0v6"},
    {"name": "Rolling Suds of East Bay", "token": "api_a2jymlvgfxmdt0e9vxqh6i9ss81kavre"},
    {"name": "Rolling Suds of Fairfield - Westchester", "token": "api_vzr5naspelzd7fasiz4om30xh5im4cx6"},
    {"name": "Rolling Suds of FL- Fort Myers & Naples", "token": "api_w1druyk4lizfu9dtyr6tvwzneygr41vf"},
    {"name": "Rolling Suds of FL Jacksonville", "token": "api_jygxf60unfrxzsm0z26y5tdsu7xcl13w"},
    {"name": "Rolling Suds of Folsom-Citrus Heights", "token": "api_nkws972ghxpd6cskrm96y4tp4w5kn162"},
    {"name": "Rolling Suds of Ft Worth Metro", "token": "api_4vhet7qxvjhtn2fkwi8s0tydy4i7cxsf"},
    {"name": "Rolling Suds of Ft. Lauderdale", "token": "api_7wfvo2u1oc3rtuxl56pjmswo46f98dbw"},
    {"name": "Rolling Suds of Greater Pittsburgh-Youngstown", "token": "api_vaj41styk1p83zljpk3ce5utqpnk6ilj"},
    {"name": "Rolling Suds of Hollywood-West Beverly Hills", "token": "api_bxrswq43k9odt7e2x408gikl6530jgzh"},
    {"name": "Rolling Suds of Irvine-Newport Beach", "token": "api_ey21r3iv3i57jpqzovhrqmfp8nzvl5ky"},
    {"name": "Rolling Suds of Kansas City", "token": "api_6c32soh59se5j1y3rk0wyltnvso27hjf"},
    {"name": "Rolling Suds of Kansas City-Overland", "token": "api_nd65wzlsyr0a2n3sm7wrpov3xv7w42o9"},
    {"name": "Rolling Suds Of Katy - Cypress", "token": "api_2pos5yevs5gpqz6u475nrafx9kbiz35q"},
    {"name": "Rolling Suds of Kennesaw-Cartersville", "token": "api_8m9oah1dl639cxeox9qyc2w8c2emt9gb"},
    {"name": "Rolling Suds Of Lakewood-Summit County", "token": "api_jsg7u3ihismwf2c36cnkx410vghzcqob"},
    {"name": "Rolling Suds of Lancaster-Harrisburg", "token": "api_dqve3icfpejynr6k4ait3pulug2sexiz"},
    {"name": "Rolling Suds of Las Vegas-Summerlin", "token": "api_6w592somkr3n64smy6hoxjluslux0awb"},
    {"name": "Rolling Suds of Long Island-Port Washington", "token": "api_817c4i2s4lnkmv0yhpcz1ein2o9d4uf6"},
    {"name": "Rolling Suds of Louisville", "token": "api_o1u4gscb5jalncb7lu67s3ad4an953c2"},
    {"name": "Rolling Suds of Montgomery County", "token": "api_bl3ytw1p9ij1eh5t5ny9w1uev57l0dyt"},
    {"name": "Rolling Suds of Naperville – Wheaton", "token": "api_wsx9bk03yrias70lio6102kfumodvbpy"},
    {"name": "Rolling Suds of Nashville-Brentwood", "token": "api_gcbwur168jim597de48w7agj4ug0r3td"},
    {"name": "Rolling Suds of NC-Wilmington", "token": "api_5kp7e6ay5a1beinf1po3c5j4yewfbztk"},
    {"name": "Rolling Suds of Needham", "token": "api_eu73xb2zyfbh59po9d7azohwjih9r5c3"},
    {"name": "Rolling Suds of New Orleans", "token": "api_4s60d5euy1ip6tflujnhy0ivfyqx3v7h"},
    {"name": "Rolling Suds of North Atlanta-Marietta", "token": "api_a9n3iyzhdm2po6zaf2pkrqlo2sn37dq8"},
    {"name": "Rolling Suds Of North Indianapolis", "token": "api_elc6paudvxk07q8mb7ejzu95g8i7241f"},
    {"name": "Rolling Suds Of North Tampa", "token": "api_rpha1tob16hyaoq7ubi3dptl2z5m9hun"},
    {"name": "Rolling Suds of Northeast Charlotte", "token": "api_2b6cal3173velkq0rc5ejw7o0ewqarc2"},
    {"name": "Rolling Suds of Northern Chicago (converted)", "token": "api_vy9kqm2r0snh1ouw4hvlo61n7onybcas"},
    {"name": "Rolling Suds of NY/CT-Greenwich", "token": "api_bfgo3lrtk4x7d3tmq61lxzcvlxdn0r5y"},
    {"name": "Rolling Suds of OH-Columbus", "token": "api_8mexk4q7wfaexpjdmlxurtkcwb92g10k"},
    {"name": "Rolling Suds of OKC", "token": "api_hzjtducbekhy0gv3ius0ket7gz58rn3v"},
    {"name": "Rolling Suds of Omaha - Papillion", "token": "api_dg5hpqbfwgakcp16pn3dmw6j8igv2hxt"},
    {"name": "Rolling Suds of Orland Park-Plainfield", "token": "api_aksch1n6ecbo3g1hrw1tvyx7c9j0uols"},
    {"name": "Rolling Suds of PA-Reading", "token": "api_8mexk4q7wfaexpjdmlxurtkcwb92g10k"},
    {"name": "Rolling Suds of Pensacola", "token": "api_83dmbilv4fxgpv8a94n0bmhqebf0d9jq"},
    {"name": "Rolling Suds of Plano-McKinney", "token": "api_ytjmx905gz46yd1stubcm7iriwc6u5pl"},
    {"name": "Rolling Suds of Raleigh-Durham", "token": "api_8fhs90a62fopku4vbgdph24zazcxjrig"},
    {"name": "Rolling Suds of Richmond", "token": "api_91gy3cpm1vdtlrsb3u4kdzq267n5tbjq"},
    {"name": "Rolling Suds of Rochester-Henrietta", "token": "api_oun92d3jutkf5d9wnd9mlks45iekxhpw"},
    {"name": "Rolling Suds of Salt Lake CIty-Park City", "token": "api_njl1tkwa25uytsnhpm597gdv03hicfl4"},
    {"name": "Rolling Suds of San Diego-La Jolla", "token": "api_blkcnzdjevfdu38auhtniw7gx46lzk7i"},
    {"name": "Rolling Suds of San Marcos, TX", "token": "api_a0qo2m5uutco6z3qa45lcy8rowr5fq86"},
    {"name": "Rolling Suds of San Ramon - Danville", "token": "api_a2jymlvgfxmdt0e9vxqh6i9ss81kavre"},
    {"name": "Rolling Suds of Santa Monica-Palos Verdes", "token": "api_by29xaomfzk45m2uo5xb93acjnto756c"},
    {"name": "Rolling Suds of SC/GA-Savannah-Charleston", "token": "api_3geptfcv1kbfhsvoblmdg7uzgl0k8xmw"},
    {"name": "Rolling Suds of Schaumburg-Rosemont", "token": "api_wdehl5cnkux7ir4nb0t3ckmpteupawgm"},
    {"name": "Rolling Suds of Seattle", "token": "api_xvnqe7ul10qwyc7k94q18n2w678sg5hz"},
    {"name": "Rolling Suds of Tampa-St Petersburg", "token": "api_deguqz6rxc7yoa9ul5xyq6a4pxzm61la"},
    {"name": "Rolling Suds of Tulsa", "token": "api_o3scphv9wgd0mjatp2z1lwog0xth23as"},
    {"name": "Rolling Suds of Ventura", "token": "api_zvhi3k2tulwo394yftqrme97inem7y4t"},
    {"name": "Rolling Suds of West Baltimore-Ellicott", "token": "api_fmi08kzwr7tx1h5g5n603wzbg6p30hkt"},
    {"name": "Rolling Suds of West Orlando", "token": "api_e6w85nz7fb51winmgdsipa6hb1w35kd0"},
    {"name": "Rolling Suds of Wilmington-Dover", "token": "api_t5bvcnxqg6pzrh3t39wtr6ao3pf94tc2"},
    {"name": "Rolling Suds Of Woodlands - North Houston (conroe)", "token": "api_qguh41fe9q4bjophjp5gbu4224stbnec"},
    {"name": "Rolling Suds San Jose - Santa Clara", "token": "api_8rqhinb1q58tikdl1p3mtu0h9itqc7dy"},
    {"name": "Rolling Suds TX-New Braunfels", "token": "api_h3gyjavnxwtbf2clwftvno98o34qsmuz"},
    {"name": "Rollings Suds of Birmingham", "token": "api_pwayob3iybx1sqwueyvb5spu9u2owc1z"},
    {"name": "RS-AZ-Phoenix", "token": "api_pmcbgtah1cepk5sf4uim5j8ttci5oy8g"},
    {"name": "RS-CO North Denver", "token": "api_o2ice7k8x2y0tdn8o67yzp0igfscjroe"},
    {"name": "RS-MO-St.Louis", "token": "api_i0q5lwchiuncry4ay27ombtaadhus36v"},
    {"name": "RS-MS Jackson-Tupelo", "token": "api_t6r1a7wzot84vx21ayhks69i5hwu39of"},
    {"name": "Rolling Suds of Carrollton - Highland Park", "token": "api_3gihew52zeu631cjiknbsgz7gz8jfxsw"},
]

# ====================== HTTP HELPERS ======================

def _sleep_backoff(attempt: int):
    time.sleep(BACKOFF_BASE_S * (attempt ** 1.5))


def _normalize_payload(obj: Any) -> List[Dict[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        if isinstance(obj.get("data"), list):
            return obj["data"]
        if isinstance(obj.get("aaData"), list):
            return obj["aaData"]
        if obj.get("error") is True:
            return []
    return []


def _get(
    base_url: str,
    path: str,
    params: List[Tuple[str, Any]],
    base_url_redacted: str,
    what: str,
) -> Tuple[int, Any, str]:
    url = f"{base_url}{path}"
    tries = 0
    while tries < MAX_RETRIES:
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT_S)
            # Build a redacted debug URL with identical params
            dbg_req = requests.Request("GET", f"{base_url_redacted}{path}", params=params).prepare()
            dbg_url = dbg_req.url
            status = r.status_code
            try:
                body = r.json()
            except Exception:
                body = r.text
            print(f"[DEBUG] GET {dbg_url} -> {status}")
            if status == 200:
                return status, body, dbg_url
            if status in (429, 500, 502, 503, 504):
                tries += 1
                _sleep_backoff(tries)
                continue
            body_txt = body if isinstance(body, str) else json.dumps(body)
            print(f"❌ [{status}] {path} — Body: {body_txt[:220]}")
            return status, body, dbg_url
        except requests.RequestException as e:
            tries += 1
            print(f"[WARN] {what}: network error {e} (attempt {tries}/{MAX_RETRIES})")
            _sleep_backoff(tries)
    return 0, {"error": True, "msg": "network error after retries"}, ""


def _page_through(
    base_url: str,
    path: str,
    base_params: List[Tuple[str, Any]],
    base_url_redacted: str,
    item_label: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    offset = 0
    seen = set()
    while True:
        params = base_params + [("offset", offset), ("records", PAGE_SIZE)]
        status, body, _ = _get(base_url, path, params, base_url_redacted, item_label)
        if status != 200:
            break
        page = _normalize_payload(body)
        if not isinstance(page, list):
            print("⚠️ Unexpected payload shape; stopping.")
            break
        n = len(page)
        print(f"    [{item_label}] page @offset {offset}: {n} rows")
        if n > 0:
            sig_first = page[0].get("uuid") or page[0].get("UUID") or page[0].get("id") or str(page[0])[:40]
            sig_last = page[-1].get("uuid") or page[-1].get("UUID") or page[-1].get("id") or str(page[-1])[-40:]
            sig = f"{offset}:{n}:{sig_first}:{sig_last}"
            if sig in seen:
                print("⚠️ Repeated page signature; stopping pagination.")
                break
            seen.add(sig)
        out.extend(page)
        if n < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.15)
    return out


# ====================== DATE / KEEP LOGIC ======================

def parse_dt(val: Any):
    if not val or not isinstance(val, str):
        return None
    try:
        v = val.strip()
        if v.endswith("Z"):
            v = v.replace("Z", "+00:00")
        if " " in v and "T" not in v:
            v = v.replace(" ", "T")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def in_this_year(dt: datetime) -> bool:
    return bool(dt and dt.year == THIS_YEAR)


CREATED_KEYS = ["created_at", "createdAt", "time_created", "jobDateTime", "date_created", "CreatedDate"]
SCHEDULED_KEYS = ["scheduled_start", "scheduledAt", "start_time", "ScheduledStart"]


def get_field(row: Dict[str, Any], keys: List[str]):
    for k in keys:
        if k in row and row[k]:
            return row[k]
    return None


def red_token(tok: str) -> str:
    return f"{tok[:4]}…{tok[-4:]}" if len(tok) > 10 else tok


def get_uuid(row: Dict[str, Any]) -> str:
    return str(row.get("uuid") or row.get("UUID") or row.get("id") or row.get("Id") or _uuid.uuid4())


def add_account(rows: List[Dict[str, Any]], account_name: str, kind: str) -> None:
    for r in rows:
        r["Account"] = account_name
        r["_kind"] = kind


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def keep_created_or_scheduled_this_year(row: Dict[str, Any]) -> bool:
    created_dt = parse_dt(get_field(row, CREATED_KEYS))
    scheduled_dt = parse_dt(get_field(row, SCHEDULED_KEYS))
    return in_this_year(created_dt) or in_this_year(scheduled_dt)


# ====================== FETCHERS ======================

def fetch_jobs_for_status(
    base_url: str,
    base_url_redacted: str,
    status_value: str,
    start_date: str,
) -> List[Dict[str, Any]]:
    # NOTE: Workiz `start_date` filters by CREATED DATE
    params = [("start_date", start_date), ("only_open", "false"), ("status", status_value)]
    print(f"🔎 Jobs status='{status_value}' (start_date={start_date})")
    return _page_through(base_url, "/job/all/", params, base_url_redacted, "job")


def fetch_leads(base_url: str, base_url_redacted: str) -> List[Dict[str, Any]]:
    params = [("start_date", THIS_YEAR_START)]
    print("📩 Leads (no status filter)")
    return _page_through(base_url, "/lead/all/", params, base_url_redacted, "lead")


# ====================== MAIN ======================

def main():
    run_stamp = now_stamp()

    all_jobs: List[Dict[str, Any]] = []
    all_leads: List[Dict[str, Any]] = []
    per_account_summary: List[Dict[str, Any]] = []

    grand_jobs_kept = 0
    grand_leads = 0

    for acc in accounts:
        name = acc["name"]
        token = acc["token"]
        base_url = f"https://api.workiz.com/api/v1/{token}"
        token_r = red_token(token)
        base_url_r = f"https://api.workiz.com/api/v1/{token_r}"

        print(f"\n-> Fetch for {name}")

        # Strategy:
        # 1) Pull created-in-year window per status (start_date = THIS_YEAR_START)
        # 2) Pull wide window per status (start_date = WIDE_START), then keep those scheduled-in-year
        # 3) Union, dedupe, then final keep=created_in_year OR scheduled_in_year (guarded but expected)
        raw_created: List[Dict[str, Any]] = []
        raw_wide: List[Dict[str, Any]] = []

        for st in JOB_STATUSES:
            # 1) Created-in-year
            rows_c = fetch_jobs_for_status(base_url, base_url_r, st, THIS_YEAR_START)
            add_account(rows_c, name, "job")
            for r in rows_c:
                r["_status_pull"] = st
            raw_created.extend(rows_c)

            # 2) Wide window for scheduled-in-year discovery
            rows_w = fetch_jobs_for_status(base_url, base_url_r, st, WIDE_START)
            add_account(rows_w, name, "job")
            for r in rows_w:
                r["_status_pull"] = st
            raw_wide.extend(rows_w)

        # Deduplicate by uuid across all pulls
        dedup_map: Dict[str, Dict[str, Any]] = {}
        for r in raw_created + raw_wide:
            u = get_uuid(r)
            if u not in dedup_map:
                dedup_map[u] = r

        # Final keep: created THIS_YEAR OR scheduled THIS_YEAR
        kept_rows = [r for r in dedup_map.values() if keep_created_or_scheduled_this_year(r)]

        # Per-status counts (based on kept rows)
        status_counts: Dict[str, int] = {st: 0 for st in JOB_STATUSES}
        for r in kept_rows:
            st = (r.get("status") or r.get("JobStatus") or r.get("_status_pull") or "").strip()
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts.setdefault(st, 0)
                status_counts[st] += 1

        # Leads
        leads_rows = fetch_leads(base_url, base_url_r)
        add_account(leads_rows, name, "lead")

        # Append to global
        all_jobs.extend(kept_rows)
        all_leads.extend(leads_rows)

        # Debug line (as requested): account name, endpoint, lead count, job count by status
        status_parts = " | ".join([f"{st}={status_counts.get(st,0)}" for st in JOB_STATUSES])
        print(
            f"<-- {name} | endpoint={base_url_r} | leads={len(leads_rows)} | jobs_by_status: {status_parts} | total_jobs={len(kept_rows)}"
        )

        per_account_summary.append({
            "Account": name,
            "Endpoint": base_url_r,
            "Leads": len(leads_rows),
            **{f"Jobs_{st}": status_counts.get(st, 0) for st in JOB_STATUSES},
            "Jobs_Total": len(kept_rows),
        })

        grand_jobs_kept += len(kept_rows)
        grand_leads += len(leads_rows)

    # ====================== EXPORTS ======================

    jobs_df = pd.DataFrame(all_jobs)
    leads_df = pd.DataFrame(all_leads)
    summary_df = pd.DataFrame(per_account_summary).sort_values("Account")

    f_jobs = os.path.join(EXPORT_ROOT, f"jobs_{run_stamp}.csv")
    f_leads = os.path.join(EXPORT_ROOT, f"leads_{run_stamp}.csv")
    f_counts = os.path.join(EXPORT_ROOT, f"counts_summary_{run_stamp}.csv")

    jobs_df.to_csv(f_jobs, index=False)
    leads_df.to_csv(f_leads, index=False)
    summary_df.to_csv(f_counts, index=False)

    # ====================== TOTALS ======================

    print("\n================ Per-account summary (counts) ================")
    for r in per_account_summary:
        parts = " | ".join([f"{k}={r[k]}" for k in summary_df.columns if k.startswith("Jobs_") and k != "Jobs_Total"])
        print(f"{r['Account']}: leads={r['Leads']} | {parts} | total_jobs={r['Jobs_Total']}")

    print("============== Grand totals ==============")
    print(f"TOTAL Jobs (kept created-or-scheduled): {grand_jobs_kept}")
    print(f"TOTAL Leads: {grand_leads}")
    print("=========================================")

    if EXPECTED_TOTAL_JOBS:
        diff = grand_jobs_kept - EXPECTED_TOTAL_JOBS
        if diff == 0:
            print(f"✅ Jobs match expected ({EXPECTED_TOTAL_JOBS}).")
        elif diff < 0:
            print(f"ℹ️ Currently {abs(diff)} below the ~{EXPECTED_TOTAL_JOBS} jobs target (informational only).")
        else:
            print(f"ℹ️ Currently {diff} above the ~{EXPECTED_TOTAL_JOBS} jobs target (informational only).")

    print(f"\n✅ Wrote {len(jobs_df):,} rows -> {f_jobs}")
    print(f"✅ Wrote {len(leads_df):,} rows -> {f_leads}")
    print(f"✅ Wrote {len(summary_df):,} rows -> {f_counts}")
    print("✅ Completed.")


if __name__ == "__main__":
    main()

