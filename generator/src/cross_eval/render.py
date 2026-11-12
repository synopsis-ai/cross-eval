"""Renders the simulated history into each system's tables, with each system's own IDs, naming,
types, coverage and mess. Returns {system: {table: Table}}."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .world import (
    AS_OF,
    CREW_ROLES,
    DEPTS,
    EVENT_TYPES,
    META_CAMPAIGNS,
    OFFICES,
    START,
    US_OFFICES,
    World,
    employed_on,
)

SYSTEMS = ["salesforce", "netsuite", "adp", "google_ads", "meta_ads", "cuewright"]


@dataclass
class Table:
    cols: list  # [(name, type)], type in str/int/float/bool/date
    rows: list = field(default_factory=list)


def us_date(d: date | None) -> str | None:
    return None if d is None else f"{d.month:02d}/{d.day:02d}/{d.year}"


def ns_date(d: date | None) -> str | None:
    return None if d is None else f"{d.month}/{d.day}/{d.year}"


def ns_ts(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{dt.month}/{dt.day}/{dt.year} {h}:{dt.minute:02d} {'am' if dt.hour < 12 else 'pm'}"


def sf_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def as_dt(d: date, r: random.Random) -> datetime:
    return datetime(d.year, d.month, d.day, r.randint(13, 22), r.randint(0, 59), r.randint(0, 59))


def money(cents: int) -> float:
    return round(cents / 100, 2)


def money_str(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def slug(name: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in name)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def emp_numbers(w: World, r: random.Random) -> dict:
    nums = r.sample(range(100, 2999), len(w.people))
    return {p["pid"]: n for p, n in zip(w.people, nums)}


def render(w: World) -> dict[str, dict[str, Table]]:
    r = random.Random(w.seed + 2)
    empno = emp_numbers(w, r)
    out = {s: {} for s in SYSTEMS}
    users = render_salesforce(w, r, out["salesforce"])
    render_cuewright(w, r, out["cuewright"], empno)
    render_netsuite(w, r, out["netsuite"])
    render_adp(w, r, out["adp"], empno)
    render_google(w, r, out["google_ads"])
    render_meta(w, r, out["meta_ads"])
    return out


def sf_user_ids(w: World, r: random.Random) -> dict:
    ids = {}
    for p in w.people:
        if p["kind"] in ("salaried", "contractor"):
            ids[p["pid"]] = "005" + "8c0" + "".join(r.choice("0123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(12))
    return ids


def render_salesforce(w: World, r: random.Random, t: dict) -> dict:
    uid = sf_user_ids(w, r)
    w.sf_user_ids = uid
    t["salesforce_user"] = Table([("id", "str"), ("username", "str"), ("name", "str"), ("first_name", "str"), ("last_name", "str"),
                                  ("email", "str"), ("title", "str"), ("department", "str"), ("office_c", "str"), ("is_active", "bool"),
                                  ("created_date", "str")])
    for p in w.people:
        if p["pid"] not in uid:
            continue
        email = f"{p['first'].lower()}.{p['last'].lower()}@bloomproductions.example"
        t["salesforce_user"].rows.append({
            "id": uid[p["pid"]], "username": email, "name": f"{p['first']} {p['last']}", "first_name": p["first"], "last_name": p["last"],
            "email": email, "title": p["title"], "department": p["dept"], "office_c": OFFICES[p["office"]]["city"],
            "is_active": employed_on(p, AS_OF), "created_date": sf_ts(as_dt(max(p["hire"], date(2019, 1, 7)), r)),
        })
    mkt = next(p for p in w.people if p["title"] == "Marketing Manager")

    acct = Table([("id", "str"), ("is_deleted", "bool"), ("name", "str"), ("type", "str"), ("industry", "str"), ("billing_city", "str"),
                  ("billing_state", "str"), ("billing_country", "str"), ("website", "str"), ("owner_id", "str"), ("account_source", "str"),
                  ("number_of_employees", "int"), ("created_date", "str"), ("last_modified_date", "str"), ("customer_tier_c", "str"),
                  ("netsuite_customer_id_c", "str"), ("region_c", "str"), ("first_event_date_c", "date")])
    won_clients = {o["client"] for o in w.opps if o["won"]} | {c["cid"] for c in w.clients if c["preexisting"]}
    first_show = {}
    for sh in sorted(w.shows, key=lambda s: s["start"]):
        first_show.setdefault(sh["client"], sh["start"])
    emp_band = {"S": (50, 400), "M": (400, 2500), "L": (2500, 12000), "XL": (12000, 80000)}
    for a in w.accounts:
        c = w.client(a["client"])
        cust = w.customers.get(c["cid"])
        acct.rows.append({
            "id": a["id"], "is_deleted": False, "name": a["name"], "type": "Customer" if c["cid"] in won_clients else "Prospect",
            "industry": c["industry"], "billing_city": c["city"], "billing_state": c["region"],
            "billing_country": "Canada" if c["country"] == "CA" else "United States",
            "website": f"www.{c['stem'].lower()}.example", "owner_id": uid[a["owner"]], "account_source": a["source"],
            "number_of_employees": r.randint(*emp_band[c["size"]]), "created_date": sf_ts(a["created"]),
            "last_modified_date": sf_ts(a["created"] + timedelta(days=r.randint(0, 400))) if a["created"].date() < AS_OF - timedelta(days=400) else sf_ts(a["created"]),
            "customer_tier_c": {"S": "Tier 3", "M": "Tier 2", "L": "Tier 1", "XL": "Strategic"}[c["size"]] if not a["dup"] else None,
            "netsuite_customer_id_c": str(cust["id"]) if cust and not a["dup"] and r.random() < 0.5 else None,
            "region_c": OFFICES[c["office"]]["city"], "first_event_date_c": first_show.get(c["cid"]) if not a["dup"] else None,
        })
    for _ in range(len(w.accounts) // 60):
        acct.rows.append({"id": "0018c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)), "is_deleted": True,
                          "name": r.choice(["Test Account", "DELETE ME", "asdf", "Duplicate - do not use"]), "type": "Prospect",
                          "owner_id": r.choice(list(uid.values())), "created_date": sf_ts(as_dt(r.choice([START, AS_OF - timedelta(days=90)]), r))})
    t["salesforce_account"] = acct

    con = Table([("id", "str"), ("is_deleted", "bool"), ("account_id", "str"), ("first_name", "str"), ("last_name", "str"), ("name", "str"),
                 ("email", "str"), ("title", "str"), ("phone", "str"), ("lead_source", "str"), ("created_date", "str")])
    for ct in w.contacts:
        c = w.client(ct["client"])
        con.rows.append({"id": ct["id"], "is_deleted": False, "account_id": c["account"], "first_name": ct["first"], "last_name": ct["last"],
                         "name": f"{ct['first']} {ct['last']}", "email": ct["email"], "title": ct["title"],
                         "phone": f"({r.randint(200, 989)}) {r.randint(200, 989)}-{r.randint(1000, 9999)}", "lead_source": c["channel"],
                         "created_date": sf_ts(ct["created"])})
    t["salesforce_contact"] = con

    google_by_id = {c["id"]: c for c in w.google_campaigns}
    lead = Table([("id", "str"), ("is_deleted", "bool"), ("first_name", "str"), ("last_name", "str"), ("company", "str"), ("email", "str"),
                  ("status", "str"), ("lead_source", "str"), ("is_converted", "bool"), ("converted_date", "date"),
                  ("converted_account_id", "str"), ("converted_contact_id", "str"), ("converted_opportunity_id", "str"), ("owner_id", "str"),
                  ("created_date", "str"), ("utm_source_c", "str"), ("utm_medium_c", "str"), ("utm_campaign_c", "str"), ("gclid_c", "str"),
                  ("fb_lead_id_c", "str"), ("fb_campaign_id_c", "str"), ("event_type_interest_c", "str")])
    reps = [uid[p["pid"]] for p in w.people if p["title"] == "Account Executive" and p["pid"] in uid]
    for l in w.leads:
        converted = bool(l.get("converted"))
        row = {"id": l["id"], "is_deleted": False, "first_name": l["first"], "last_name": l["last"], "company": l["company"],
               "email": f"{l['first'][0].lower()}{l['last'].lower()}@{'mail.example' if l['junk'] and r.random() < 0.5 else l['company'].split()[0].lower() + '.example'}",
               "status": "Converted" if converted else r.choice(["Open", "Working", "Nurturing", "Unqualified", "Unqualified", "Disqualified"]),
               "lead_source": l["source"], "is_converted": converted, "converted_date": l.get("converted"),
               "converted_account_id": l.get("converted_account"), "converted_contact_id": l.get("converted_contact"),
               "converted_opportunity_id": l.get("converted_opp"), "owner_id": r.choice(reps), "created_date": sf_ts(l["created"]),
               "event_type_interest_c": r.choice([None, None] + [e["label"] for e in EVENT_TYPES.values()])}
        if l["source"] == "Google Ads":
            row.update({"utm_source_c": "google", "utm_medium_c": "cpc", "utm_campaign_c": slug(google_by_id[l["google"]]["name"]) if l["google"] else None,
                        "gclid_c": "Cj0KCQ" + "".join(r.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-") for _ in range(40))})
        elif l["source"] == "Paid Social":
            row.update({"utm_source_c": r.choice(["facebook", "fb", "ig", "instagram"]), "utm_medium_c": "paid_social",
                        "fb_lead_id_c": str(r.randint(10 ** 15, 10 ** 16 - 1)), "fb_campaign_id_c": l["meta"]})
        lead.rows.append(row)
    for _ in range(len(w.leads) // 100):
        lead.rows.append({"id": "00Q8c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)), "is_deleted": True,
                          "first_name": "Test", "last_name": "Lead", "company": "Test", "lead_source": r.choice(["Google Ads", "Website", "Paid Social"]),
                          "status": "Open", "is_converted": False, "created_date": sf_ts(as_dt(r.choice([START + timedelta(days=200), AS_OF - timedelta(days=40)]), r))})
    t["salesforce_lead"] = lead

    sf_camp_by_platform = {c["platform_id"]: c for c in w.sf_campaigns if c["platform_id"]}
    opp = Table([("id", "str"), ("is_deleted", "bool"), ("account_id", "str"), ("name", "str"), ("stage_name", "str"), ("amount", "float"),
                 ("probability", "float"), ("close_date", "date"), ("type", "str"), ("lead_source", "str"), ("is_closed", "bool"), ("is_won", "bool"),
                 ("forecast_category_name", "str"), ("owner_id", "str"), ("campaign_id", "str"), ("created_date", "str"), ("fiscal_year", "int"),
                 ("fiscal_quarter", "int"), ("event_type_c", "str"), ("event_date_c", "date"), ("show_number_c", "str"), ("loss_reason_c", "str"),
                 ("venue_c", "str"), ("next_step", "str")])
    prob = {"Prospecting": 10, "Qualification": 25, "Proposal": 50, "Negotiation": 75, "Closed Won": 100, "Closed Lost": 0}
    fc = {"Prospecting": "Pipeline", "Qualification": "Pipeline", "Proposal": "Best Case", "Negotiation": "Commit", "Closed Won": "Closed", "Closed Lost": "Omitted"}
    shows = {s["sid"]: s for s in w.shows}
    venues = {v["vid"]: v for v in w.venues}
    hist = Table([("id", "str"), ("opportunity_id", "str"), ("stage_name", "str"), ("amount", "float"), ("close_date", "date"),
                  ("probability", "float"), ("created_date", "str")])
    for o in w.opps:
        c = w.client(o["client"])
        sh = shows.get(o["show"]) if o["show"] else None
        camp = None
        if o["google"]:
            camp = sf_camp_by_platform[o["google"]]["id"]
        elif o["meta"]:
            camp = sf_camp_by_platform[o["meta"]]["id"]
        et = EVENT_TYPES[o["etype"]]["label"]
        opp.rows.append({
            "id": o["id"], "is_deleted": False, "account_id": o["account"], "name": f"{c['base']} - {et} {o['event'].year}",
            "stage_name": o["stage"], "amount": float(o["amount"]), "probability": float(prob[o["stage"]]), "close_date": o["close"],
            "type": "New Business" if o["new"] else "Existing Business", "lead_source": o["lead_source"], "is_closed": o["closed"],
            "is_won": o["won"], "forecast_category_name": fc[o["stage"]], "owner_id": uid[o["owner"]], "campaign_id": camp,
            "created_date": sf_ts(o["created_ts"]), "fiscal_year": o["close"].year, "fiscal_quarter": (o["close"].month - 1) // 3 + 1,
            "event_type_c": et, "event_date_c": o["event"], "show_number_c": sh["number"] if sh and r.random() < 0.6 else None,
            "loss_reason_c": o["loss_reason"], "venue_c": venues[sh["venue"]]["name"] if sh and r.random() < 0.5 else None,
            "next_step": None if o["closed"] else r.choice(["Send revised quote", "Site visit", "Follow up after budget review", "Schedule production meeting"]),
        })
        stages = ["Prospecting", "Qualification", "Proposal", "Negotiation"]
        final = o["stage"]
        path = stages[: stages.index(final) + 1] if final in stages else stages[: r.randint(1, 4)] + [final]
        span = max(1, (min(o["close"], AS_OF) - o["created"]).days)
        for i, st in enumerate(path):
            d = o["created"] + timedelta(days=span * i // max(1, len(path) - 1)) if i < len(path) - 1 else (o["close"] if final in ("Closed Won", "Closed Lost") else o["created"] + timedelta(days=span * i // max(1, len(path))))
            hist.rows.append({"id": "0088c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)), "opportunity_id": o["id"],
                              "stage_name": st, "amount": float(o["amount"]), "close_date": o["close"], "probability": float(prob[st]),
                              "created_date": sf_ts(as_dt(min(d, AS_OF), r))})
    for _ in range(len(w.opps) // 50):
        d = r.choice([date(2024, 11, 4), date(2025, 5, 12), date(2025, 9, 22), date(2026, 2, 9)])
        opp.rows.append({"id": "0068c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)), "is_deleted": True,
                         "account_id": r.choice(w.accounts)["id"], "name": r.choice(["TEST - ignore", "Duplicate opp", "Copy of opportunity"]),
                         "stage_name": "Closed Won", "amount": float(r.randint(20, 300) * 1000), "probability": 100.0, "close_date": d,
                         "type": "New Business", "lead_source": "Website", "is_closed": True, "is_won": True, "forecast_category_name": "Closed",
                         "owner_id": r.choice(reps), "created_date": sf_ts(as_dt(d - timedelta(days=30), r)), "fiscal_year": d.year,
                         "fiscal_quarter": (d.month - 1) // 3 + 1})
    t["salesforce_opportunity"] = opp
    t["salesforce_opportunity_history"] = hist

    camp = Table([("id", "str"), ("name", "str"), ("type", "str"), ("status", "str"), ("start_date", "date"), ("end_date", "date"),
                  ("is_active", "bool"), ("ad_platform_c", "str"), ("platform_campaign_id_c", "str"), ("owner_id", "str"), ("budgeted_cost", "float")])
    for c in w.sf_campaigns:
        active = c["end"] is None or c["end"] >= AS_OF
        camp.rows.append({"id": c["id"], "name": c["name"], "type": c["type"], "status": "In Progress" if active else "Completed",
                          "start_date": c["start"], "end_date": c["end"], "is_active": active, "ad_platform_c": c["platform"],
                          "platform_campaign_id_c": c["platform_id"] if c["platform_id"] and r.random() < 0.85 else None,
                          "owner_id": uid[mkt["pid"]], "budgeted_cost": float(r.randint(5, 80) * 1000)})
    t["salesforce_campaign"] = camp
    member = Table([("id", "str"), ("campaign_id", "str"), ("lead_id", "str"), ("contact_id", "str"), ("status", "str"),
                    ("has_responded", "bool"), ("created_date", "str")])
    for l in w.leads:
        pid = l.get("google") or l.get("meta")
        if pid and r.random() < 0.9:
            member.rows.append({"id": "00v8c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)),
                                "campaign_id": sf_camp_by_platform[pid]["id"], "lead_id": l["id"], "contact_id": l.get("converted_contact"),
                                "status": "Responded", "has_responded": True, "created_date": sf_ts(l["created"])})
    t["salesforce_campaign_member"] = member

    role = Table([("id", "str"), ("opportunity_id", "str"), ("contact_id", "str"), ("role", "str"), ("is_primary", "bool")])
    contacts_by_client: dict[int, list] = {}
    for ct in w.contacts:
        contacts_by_client.setdefault(ct["client"], []).append(ct)
    task = Table([("id", "str"), ("who_id", "str"), ("what_id", "str"), ("subject", "str"), ("status", "str"), ("priority", "str"),
                  ("activity_date", "date"), ("owner_id", "str"), ("type", "str"), ("created_date", "str")])
    for o in w.opps:
        cts = contacts_by_client[o["client"]]
        for i, ct in enumerate(r.sample(cts, min(len(cts), r.randint(1, 2)))):
            role.rows.append({"id": "00K8c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)), "opportunity_id": o["id"],
                              "contact_id": ct["id"], "role": r.choice(["Decision Maker", "Economic Buyer", "Influencer", "Event Lead"]), "is_primary": i == 0})
        last = min(o["close"], AS_OF)
        for _ in range(r.randint(2, 10)):
            d = o["created"] + timedelta(days=r.randint(0, max(0, (last - o["created"]).days)))
            kind = r.choice(["Call", "Email", "Email", "Meeting"])
            task.rows.append({"id": "00T8c0" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12)), "who_id": r.choice(cts)["id"],
                              "what_id": o["id"], "subject": r.choice({"Call": ["Discovery call", "Budget check-in", "Follow-up call"],
                                                                       "Email": ["Sent proposal", "Sent revised quote", "Shared case study", "Follow up"],
                                                                       "Meeting": ["Site walkthrough", "Production meeting", "Design review"]}[kind]),
                              "status": "Completed" if d < AS_OF else "Not Started", "priority": r.choice(["Normal", "Normal", "High"]),
                              "activity_date": d, "owner_id": uid[o["owner"]], "type": kind, "created_date": sf_ts(as_dt(d, r))})
    t["salesforce_opportunity_contact_role"] = role
    t["salesforce_task"] = task
    return uid


def render_cuewright(w: World, r: random.Random, t: dict, empno: dict) -> None:
    uid = getattr(w, "sf_user_ids")
    clients = Table([("clnt_id", "int"), ("clnt_nm", "str"), ("bill_nm", "str"), ("crm_acct_ref", "str"), ("clnt_since", "str"),
                     ("actv_flg", "str"), ("hq_city", "str"), ("hq_st", "str"), ("terms_cd", "str")])
    booked = {}
    for sh in sorted(w.shows, key=lambda s: s["booked"]):
        booked.setdefault(sh["client"], sh["booked"])
    dup_ids = {}
    for c in w.clients:
        if c["cid"] not in booked:
            continue
        ref = c["account"] if r.random() < 0.65 else None
        if ref and r.random() < 0.3:
            ref = ref[:15]
        clients.rows.append({"clnt_id": 500 + c["cid"], "clnt_nm": c["cw_name"], "bill_nm": c["erp_name"].title() if r.random() < 0.5 else c["legal"],
                             "crm_acct_ref": ref, "clnt_since": us_date(booked[c["cid"]]), "actv_flg": "Y", "hq_city": c["city"], "hq_st": c["region"],
                             "terms_cd": "N45" if c["pay_days"] > 60 else "N30"})
        n_shows = sum(1 for s in w.shows if s["client"] == c["cid"])
        if n_shows >= 3 and r.random() < 0.08:
            dup_ids[c["cid"]] = 900 + c["cid"]
            c["cw_dup"] = True
            clients.rows.append({"clnt_id": 900 + c["cid"], "clnt_nm": c["base"].upper() if c["cw_name"] != c["base"].upper() else c["stem"],
                                 "bill_nm": c["legal"], "crm_acct_ref": None, "clnt_since": us_date(booked[c["cid"]] + timedelta(days=200)),
                                 "actv_flg": "Y", "hq_city": c["city"], "hq_st": c["region"], "terms_cd": "N30"})
    t["cuewright_clients"] = clients

    users = Table([("user_id", "int"), ("emp_no", "str"), ("full_nm", "str"), ("role_cd", "str"), ("office_cd", "str"), ("email", "str"), ("actv_flg", "str")])
    role_cd = {"Producer": "PROD", "Account Executive": "SALES"}
    for p in w.people:
        if p["kind"] in ("salaried", "contractor") and p["title"] in role_cd:
            users.rows.append({"user_id": 100 + p["pid"], "emp_no": (f"E-{empno[p['pid']]}" if p["kind"] == "salaried" else f"T-{empno[p['pid']]}"),
                               "full_nm": f"{p['first']} {p['last']}", "role_cd": role_cd[p["title"]], "office_cd": p["office"],
                               "email": f"{p['first'].lower()}.{p['last'].lower()}@bloomproductions.example", "actv_flg": "Y" if employed_on(p, AS_OF) else "N"})
    t["cuewright_users"] = users

    venues = Table([("venue_id", "int"), ("venue_nm", "str"), ("venue_type", "str"), ("city", "str"), ("st_prov", "str"), ("country_cd", "str"), ("details", "str")])
    for v in w.venues:
        venues.rows.append({"venue_id": 3000 + v["vid"], "venue_nm": v["name"], "venue_type": v["type"], "city": v["city"], "st_prov": v["region"],
                            "country_cd": v["country"], "details": json.dumps({"dock": v["dock"], "power_amps": v["power_amps"],
                                                                               "rig_points": v["rig_points"], "union_house": v["union"]}, sort_keys=True)})
    t["cuewright_venues"] = venues

    shows = Table([("show_id", "int"), ("show_no", "str"), ("show_nm", "str"), ("clnt_id", "int"), ("venue_id", "int"), ("office_cd", "str"),
                   ("producer_id", "int"), ("evt_type_cd", "str"), ("status_cd", "str"), ("booked_dt", "str"), ("ld_in_dt", "str"),
                   ("show_start_dt", "str"), ("show_end_dt", "str"), ("strike_dt", "str"), ("cncl_dt", "str"), ("crm_opp_ref", "str"),
                   ("curr_cd", "str"), ("attendee_est", "int"), ("custom_fields", "str")])
    quotes = Table([("quote_id", "int"), ("show_id", "int"), ("version_no", "int"), ("is_final", "str"), ("quote_status", "str"),
                    ("disc_pct", "float"), ("issued_dt", "str"), ("prepared_by", "int")])
    qlines = Table([("quote_line_id", "int"), ("quote_id", "int"), ("line_no", "int"), ("dept_cd", "str"), ("item_cd", "str"), ("line_desc", "str"),
                    ("qty", "int"), ("days", "int"), ("unit_price", "float"), ("ext_price", "float")])
    cos = Table([("co_id", "int"), ("show_id", "int"), ("co_no", "str"), ("co_desc", "str"), ("co_amt", "str"), ("approved_dt", "str"), ("void_flg", "str")])
    pulls = Table([("pull_id", "int"), ("show_id", "int"), ("item_cd", "str"), ("qty", "int"), ("out_dt", "str"), ("ret_dt", "str")])
    qid = lid = coid = pid_ = 0
    for sh in w.shows:
        c = w.client(sh["client"])
        clnt = dup_ids[c["cid"]] if c["cid"] in dup_ids and sh["booked"] > min(s["booked"] for s in w.shows if s["client"] == c["cid"]) + timedelta(days=200) and r.random() < 0.6 else 500 + c["cid"]
        opp_ref = None
        if sh["opp"]:
            opp_ref = sh["opp"] if r.random() < 0.7 else sh["opp"][:15]
        sh["cw_client"] = clnt
        shows.rows.append({
            "show_id": 30000 + sh["sid"], "show_no": sh["number"], "show_nm": sh["name"], "clnt_id": clnt, "venue_id": 3000 + sh["venue"],
            "office_cd": sh["office"], "producer_id": 100 + sh["producer"], "evt_type_cd": sh["etype"], "status_cd": sh["status"],
            "booked_dt": us_date(sh["booked"]), "ld_in_dt": us_date(sh["load_in"]), "show_start_dt": us_date(sh["start"]),
            "show_end_dt": us_date(sh["end"]), "strike_dt": us_date(sh["strike"]), "cncl_dt": us_date(sh["cancel"]), "crm_opp_ref": opp_ref,
            "curr_cd": sh["currency"], "attendee_est": r.choice([150, 250, 400, 600, 900, 1200, 2500, 5000]),
            "custom_fields": json.dumps({"po_number": sh["po"], "rush": sh["rush"], "union_venue": w.venues[sh["venue"] - 1]["union"],
                                         "dock_door": w.venues[sh["venue"] - 1]["dock"]}, sort_keys=True),
        })
        versions = sh["quote_drafts"] + [sh["quote"]["lines"]]
        for vi, lines in enumerate(versions, start=1):
            qid += 1
            final = vi == len(versions)
            issued = sh["booked"] - timedelta(days=(len(versions) - vi) * r.randint(4, 12) + r.randint(1, 5))
            quotes.rows.append({"quote_id": 80000 + qid, "show_id": 30000 + sh["sid"], "version_no": vi, "is_final": "Y" if final else "N",
                                "quote_status": "ACCEPTED" if final else "SUPERSEDED", "disc_pct": float(sh["quote"]["disc"]),
                                "issued_dt": us_date(issued), "prepared_by": 100 + sh["producer"]})
            for li, l in enumerate(lines, start=1):
                lid += 1
                qlines.rows.append({"quote_line_id": lid, "quote_id": 80000 + qid, "line_no": li, "dept_cd": l["dept"], "item_cd": l["code"],
                                    "line_desc": l["desc"], "qty": l["qty"], "days": l["days"], "unit_price": money(l["unit_cents"]),
                                    "ext_price": money(l["ext_cents"])})
        for i, co in enumerate(sh["change_orders"], start=1):
            coid += 1
            cos.rows.append({"co_id": coid, "show_id": 30000 + sh["sid"], "co_no": f"{sh['number']}-CO{i}", "co_desc": co["desc"],
                             "co_amt": money_str(co["amount_cents"]), "approved_dt": us_date(co["approved"]), "void_flg": "Y" if co["void"] else "N"})
        if not sh["cancel"]:
            for l in sh["quote"]["lines"]:
                if l["dept"] in ("AUD", "VID", "LTG", "STG", "RIG"):
                    pid_ += 1
                    pulls.rows.append({"pull_id": pid_, "show_id": 30000 + sh["sid"], "item_cd": l["code"], "qty": l["qty"] + (1 if r.random() < 0.3 else 0),
                                       "out_dt": us_date(sh["load_in"] - timedelta(days=1)), "ret_dt": us_date(sh["strike"] + timedelta(days=1)) if sh["strike"] < AS_OF else None})
    t["cuewright_shows"] = shows
    t["cuewright_quotes"] = quotes
    t["cuewright_quote_lines"] = qlines
    t["cuewright_change_orders"] = cos
    t["cuewright_pull_lines"] = pulls

    crew = Table([("crew_id", "int"), ("emp_no", "str"), ("first_nm", "str"), ("last_nm", "str"), ("primary_role_cd", "str"), ("home_office_cd", "str"),
                  ("crew_type", "str"), ("email", "str"), ("phone", "str"), ("actv_flg", "str")])
    for p in w.people:
        if p["dept"] != "Crew":
            continue
        emp = p["kind"] == "hourly"
        work = f"{p['first'].lower()}.{p['last'].lower()}@bloomproductions.example"
        crew.rows.append({"crew_id": 20000 + p["pid"], "emp_no": f"E-{empno[p['pid']]}" if emp else f"F-{empno[p['pid']]}",
                          "first_nm": p["preferred"] or p["first"], "last_nm": p["last"], "primary_role_cd": p["role"], "home_office_cd": p["office"],
                          "crew_type": "EMP" if emp else "FL",
                          "email": work if emp and r.random() < 0.8 else f"{p['first'][0].lower()}{p['last'].lower()}{r.randint(1, 99)}@mail.example",
                          "phone": f"{r.randint(200, 989)}-{r.randint(200, 989)}-{r.randint(1000, 9999)}", "actv_flg": "Y" if employed_on(p, AS_OF) else "N"})
    t["cuewright_crew"] = crew
    calls = Table([("call_id", "int"), ("show_id", "int"), ("crew_id", "int"), ("role_cd", "str"), ("work_dt", "str"), ("call_ts", "str"),
                   ("wrap_ts", "str"), ("hrs_worked", "float"), ("meal_brk_min", "int"), ("travel_flg", "str")])
    for cc in w.crew_calls:
        off = f"{'-' if cc['offset'] < 0 else '+'}{abs(cc['offset']):02d}:00"
        calls.rows.append({"call_id": 500000 + cc["id"], "show_id": 30000 + cc["show"], "crew_id": 20000 + cc["pid"], "role_cd": cc["role"],
                           "work_dt": cc["date"].isoformat(), "call_ts": cc["call"].strftime("%Y-%m-%dT%H:%M:%S") + off,
                           "wrap_ts": cc["wrap"].strftime("%Y-%m-%dT%H:%M:%S") + off, "hrs_worked": cc["hours"],
                           "meal_brk_min": 30 if cc["hours"] > 6 else 0, "travel_flg": "Y" if cc["travel"] else "N"})
    t["cuewright_crew_calls"] = calls

    items = Table([("item_cd", "str"), ("item_desc", "str"), ("dept_cd", "str"), ("daily_rate", "float"), ("repl_cost", "float")])
    for it in w.gear_items:
        items.rows.append({"item_cd": it["code"], "item_desc": it["desc"], "dept_cd": it["dept"], "daily_rate": float(it["rate"]), "repl_cost": float(it["repl"])})
    t["cuewright_gear_items"] = items
    open_repairs = {x["tag"] for x in w.repairs if x["status"] in ("OPEN", "IN_REPAIR")}
    assets = Table([("asset_tag", "str"), ("item_cd", "str"), ("serial_no", "str"), ("purch_dt", "str"), ("home_office_cd", "str"),
                    ("asset_status", "str"), ("retired_dt", "str")])
    for a in w.gear_assets:
        status = "RETIRED" if a["retired"] else ("REPAIR" if a["tag"] in open_repairs else r.choice(["IN", "IN", "IN", "OUT"]))
        assets.rows.append({"asset_tag": a["tag"], "item_cd": a["code"], "serial_no": a["serial"], "purch_dt": us_date(a["bought"]),
                            "home_office_cd": a["office"], "asset_status": status, "retired_dt": us_date(a["retired"])})
    t["cuewright_gear_assets"] = assets
    rep = Table([("tkt_id", "int"), ("asset_tag", "str"), ("show_id", "int"), ("opened_dt", "str"), ("closed_dt", "str"), ("tkt_status", "str"),
                 ("issue_desc", "str"), ("repair_cost", "float")])
    for x in w.repairs:
        rep.rows.append({"tkt_id": 9000 + x["id"], "asset_tag": x["tag"], "show_id": 30000 + x["show"], "opened_dt": us_date(x["opened"]),
                         "closed_dt": us_date(x["closed"]), "tkt_status": x["status"], "issue_desc": x["issue"],
                         "repair_cost": money(x["cost_cents"]) if x["cost_cents"] else None})
    t["cuewright_repair_tickets"] = rep
    xr = Table([("rt_cd", "str"), ("rt_desc", "str"), ("rt_amt", "float"), ("rt_unit", "str"), ("eff_dt", "str")])
    for code, (dept, lo, hi, title) in CREW_ROLES.items():
        for eff in (date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)):
            xr.rows.append({"rt_cd": f"L{code}", "rt_desc": f"{title} bill rate", "rt_amt": float(round((lo + hi) * 1.6 * (1 + 0.04 * (eff.year - 2024)))),
                            "rt_unit": "HR", "eff_dt": us_date(eff)})
    t["cuewright_xrtcd"] = xr
    gl = Table([("dept_cd", "str"), ("gl_acct", "str"), ("gl_desc", "str")])
    for dept, acct in (("AUD", "4000"), ("VID", "4010"), ("LTG", "4020"), ("STG", "4030"), ("RIG", "4040"), ("LAB", "4100"), ("FRT", "4200")):
        gl.rows.append({"dept_cd": dept, "gl_acct": acct, "gl_desc": f"{DEPTS[dept]} revenue"})
    t["cuewright_xglmap"] = gl


NS_ACCOUNTS = [
    (1, "1000", "Operating Cash", "Bank"), (2, "1200", "Accounts Receivable", "AcctRec"), (3, "1500", "Production Equipment", "FixedAsset"),
    (4, "2000", "Accounts Payable", "AcctPay"), (5, "2100", "Customer Deposits", "OthCurrLiab"),
    (6, "4000", "Rental Revenue : Audio", "Income"), (7, "4010", "Rental Revenue : Video", "Income"), (8, "4020", "Rental Revenue : Lighting", "Income"),
    (9, "4030", "Rental Revenue : Staging", "Income"), (10, "4040", "Rental Revenue : Rigging", "Income"), (11, "4100", "Labor Revenue", "Income"),
    (12, "4200", "Freight Revenue", "Income"), (13, "4300", "Change Order Revenue", "Income"), (14, "4400", "Cancellation Fees", "Income"),
    (15, "5100", "Freelance Labor", "COGS"), (16, "5200", "Freight Expense", "COGS"), (17, "5300", "Subrental Expense", "COGS"),
    (18, "6000", "Payroll Expense", "Expense"), (19, "6100", "Contractor Fees", "Expense"), (20, "6200", "General Overhead", "Expense"),
]
DEPT_ACCT = {"AUD": "4000", "VID": "4010", "LTG": "4020", "STG": "4030", "RIG": "4040", "LAB": "4100", "FRT": "4200"}
NS_DEPT_IDS = {"AUD": 1, "VID": 2, "LTG": 3, "STG": 4, "RIG": 5, "LAB": 6, "FRT": 7}
NS_ITEMS = [(101, "Audio Rental", "AUD"), (102, "Video Rental", "VID"), (103, "Lighting Rental", "LTG"), (104, "Staging Rental", "STG"),
            (105, "Rigging Rental", "RIG"), (106, "Production Labor", "LAB"), (107, "Freight", "FRT"), (108, "Change Order", None),
            (109, "Cancellation Fee", None)]


def render_netsuite(w: World, r: random.Random, t: dict) -> None:
    acct_id = {num: i for i, num, _, _ in NS_ACCOUNTS}
    t["netsuite_subsidiary"] = Table([("id", "int"), ("name", "str"), ("currency", "int"), ("country", "str"), ("iselimination", "str")],
                                     [{"id": 1, "name": "Bloom Productions", "currency": 1, "country": "US", "iselimination": "F"}])
    t["netsuite_currency"] = Table([("id", "int"), ("symbol", "str"), ("name", "str")],
                                   [{"id": 1, "symbol": "USD", "name": "US Dollar"}, {"id": 3, "symbol": "CAD", "name": "Canadian Dollar"}])
    cur = {"USD": 1, "CAD": 3}
    t["netsuite_account"] = Table([("id", "int"), ("acctnumber", "str"), ("fullname", "str"), ("accttype", "str"), ("isinactive", "str")],
                                  [{"id": i, "acctnumber": n, "fullname": nm, "accttype": ty, "isinactive": "F"} for i, n, nm, ty in NS_ACCOUNTS])
    dep = Table([("id", "int"), ("name", "str"), ("isinactive", "str")])
    for code, i in NS_DEPT_IDS.items():
        dep.rows.append({"id": i, "name": DEPTS[code], "isinactive": "F"})
    dep.rows.append({"id": 8, "name": "General & Administrative", "isinactive": "F"})
    t["netsuite_department"] = dep
    t["netsuite_item"] = Table([("id", "int"), ("itemid", "str"), ("itemtype", "str"), ("incomeaccount", "int"), ("department", "int"), ("isinactive", "str")],
                               [{"id": i, "itemid": nm, "itemtype": "Service", "incomeaccount": acct_id[DEPT_ACCT[d]] if d else acct_id["4300" if i == 108 else "4400"],
                                 "department": NS_DEPT_IDS[d] if d else None, "isinactive": "F"} for i, nm, d in NS_ITEMS])
    item_by_dept = {d: i for i, _, d in NS_ITEMS if d}
    per = Table([("id", "int"), ("periodname", "str"), ("startdate", "str"), ("enddate", "str"), ("isquarter", "str"), ("isyear", "str"), ("closed", "str")])
    period_id = {}
    pid = 0
    for y in (2024, 2025, 2026):
        pid += 1
        per.rows.append({"id": pid, "periodname": f"FY {y}", "startdate": ns_date(date(y, 1, 1)), "enddate": ns_date(date(y, 12, 31)), "isquarter": "F", "isyear": "T", "closed": "T" if y < 2026 else "F"})
        for q in range(1, 5):
            pid += 1
            qs = date(y, 3 * q - 2, 1)
            qe = date(y + (q == 4), (3 * q) % 12 + 1, 1) - timedelta(days=1)
            per.rows.append({"id": pid, "periodname": f"Q{q} {y}", "startdate": ns_date(qs), "enddate": ns_date(qe), "isquarter": "T", "isyear": "F", "closed": "T" if qe < AS_OF else "F"})
            for m in range(3 * q - 2, 3 * q + 1):
                pid += 1
                ms = date(y, m, 1)
                me = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
                period_id[(y, m)] = pid
                per.rows.append({"id": pid, "periodname": ms.strftime("%b %Y"), "startdate": ns_date(ms), "enddate": ns_date(me), "isquarter": "F", "isyear": "F", "closed": "T" if me < AS_OF - timedelta(days=10) else "F"})
    t["netsuite_accounting_period"] = per

    cust = Table([("id", "int"), ("entityid", "str"), ("companyname", "str"), ("email", "str"), ("subsidiary", "int"), ("currency", "int"),
                  ("terms", "str"), ("datecreated", "str"), ("custentity_sf_account_id", "str"), ("custentity_industry", "str"), ("isinactive", "str")])
    for cid, cu in sorted(w.customers.items(), key=lambda kv: kv[1]["id"]):
        c = w.client(cid)
        sf = None
        if cu["sf_link"]:
            sf = c["account"][:15] if cu["sf_15"] else c["account"]
        cust.rows.append({"id": cu["id"], "entityid": f"C{cu['id']} {c['erp_name']}", "companyname": c["erp_name"],
                          "email": f"ap@{c['stem'].lower()}.example", "subsidiary": 1, "currency": cur[cu["currency"]],
                          "terms": "Net 45" if c["pay_days"] > 60 else "Net 30", "datecreated": ns_ts(as_dt(cu["created"], r)),
                          "custentity_sf_account_id": sf, "custentity_industry": c["industry"], "isinactive": "F"})
    t["netsuite_customer"] = cust
    vend = Table([("id", "int"), ("entityid", "str"), ("companyname", "str"), ("isperson", "str"), ("firstname", "str"), ("lastname", "str"),
                  ("currency", "int"), ("category", "str"), ("is1099eligible", "str"), ("datecreated", "str")])
    cat = {"freelance": "Freelance Crew", "contractor": "Contractor", "freight": "Freight", "subrental": "Subrental", "equipment": "Equipment", "other": "Other"}
    for v in w.vendors:
        p = w.person(v["pid"]) if v["pid"] else None
        vend.rows.append({"id": v["id"], "entityid": v["name"], "companyname": v["name"] if not p or "LLC" in v["name"] else None,
                          "isperson": "T" if p and "LLC" not in v["name"] else "F", "firstname": p["first"] if p else None,
                          "lastname": p["last"] if p else None, "currency": cur[v["currency"]], "category": cat[v["kind"]],
                          "is1099eligible": "T" if v["kind"] in ("freelance", "contractor") and v["currency"] == "USD" else "F",
                          "datecreated": ns_ts(as_dt(max(START - timedelta(days=400), (p["hire"] if p else START - timedelta(days=700))), r))})
    t["netsuite_vendor"] = vend

    shows = {s["sid"]: s for s in w.shows}
    tx = Table([("id", "int"), ("tranid", "str"), ("type", "str"), ("trandate", "str"), ("entity", "int"), ("subsidiary", "int"), ("currency", "int"),
                ("exchangerate", "float"), ("foreigntotal", "float"), ("foreignamountremaining", "float"), ("status", "str"), ("voided", "str"),
                ("duedate", "str"), ("postingperiod", "int"), ("memo", "str"), ("custbody_show_number", "str"), ("createddate", "str")])
    lines = Table([("uniquekey", "int"), ("transaction", "int"), ("linesequencenumber", "int"), ("mainline", "str"), ("item", "int"), ("account", "int"),
                   ("department", "int"), ("memo", "str"), ("quantity", "float"), ("rate", "float"), ("foreignamount", "float"), ("netamount", "float")])
    links = Table([("previousdoc", "int"), ("nextdoc", "int"), ("linktype", "str"), ("foreignamount", "float"), ("linkdate", "str")])
    uk = 0

    def add_line(t_, seq, main, acct, amount_cents, item=None, dept=None, memo=None, qty=None, rate=None):
        nonlocal uk
        uk += 1
        lines.rows.append({"uniquekey": uk, "transaction": t_["id"], "linesequencenumber": seq, "mainline": "T" if main else "F", "item": item,
                           "account": acct_id[acct], "department": NS_DEPT_IDS.get(dept) if dept else None, "memo": memo, "quantity": qty, "rate": rate,
                           "foreignamount": money(amount_cents), "netamount": round(amount_cents * t_["fx"] / 100, 2)})

    applied_deposits = {id(doc) for x in w.transactions if x["type"] == "DepAppl" for doc, _ in x["applies"] if doc["type"] == "CustDep"}
    for x in w.transactions:
        sh = shows.get(x.get("show"))
        show_ref = None
        memo = x.get("memo")
        if sh:
            roll = r.random()
            if x["type"] == "VendBill":
                memo = f"Crew - Show {sh['number']}" if x["category"] == "freelance" else f"{x['category'].title()} - Show {sh['number']}"
                show_ref = sh["number"] if roll < 0.85 else None
            elif x["type"] in ("CustInvc", "CustDep"):
                if roll < 0.75:
                    show_ref = sh["number"]
                elif roll < 0.85:
                    show_ref = f"#{sh['number']}"
                else:
                    memo = memo or f"Show {sh['number']} - {sh['name']}"
            else:
                show_ref = sh["number"] if roll < 0.5 else None
        entity = x.get("cust") or x.get("vendor")
        status = {"CustDep": "Fully Applied" if id(x) in applied_deposits else "Not Deposited", "DepAppl": "Applied",
                  "CustPymt": "Deposited", "Journal": "Approved for Posting"}.get(x["type"])
        remaining = None
        due = None
        if x["type"] == "CustInvc":
            status = "Voided" if x["void"] else ("Paid In Full" if x["paid_in_full"] else "Open")
            remaining = money(x["remaining"]) if not x["void"] else 0.0
            due = ns_date(x["date"] + timedelta(days=30))
        elif x["type"] == "VendBill":
            status = "Paid In Full" if x["date"] < AS_OF - timedelta(days=r.randint(20, 45)) else "Open"
            due = ns_date(x["date"] + timedelta(days=30))
        tx.rows.append({"id": x["id"], "tranid": x.get("tranid"), "type": x["type"], "trandate": ns_date(x["date"]), "entity": entity, "subsidiary": 1,
                        "currency": cur[x["currency"]], "exchangerate": x["fx"], "foreigntotal": money(x["total"]), "foreignamountremaining": remaining,
                        "status": status, "voided": "T" if x["void"] else "F", "duedate": due, "postingperiod": period_id[(x["date"].year, x["date"].month)],
                        "memo": memo, "custbody_show_number": show_ref, "createddate": ns_ts(as_dt(x["date"], r))})
        if x["type"] == "CustInvc":
            add_line(x, 0, True, "1200", x["total"])
            for i, l in enumerate(x["lines"], start=1):
                if l["kind"] == "dept":
                    add_line(x, i, False, DEPT_ACCT[l["dept"]], -l["amount"], item=item_by_dept[l["dept"]], dept=l["dept"], qty=1.0, rate=money(l["amount"]))
                elif l["kind"] == "co":
                    add_line(x, i, False, "4300", -l["amount"], item=108, memo=l["desc"], qty=1.0, rate=money(l["amount"]))
                else:
                    add_line(x, i, False, "4400", -l["amount"], item=109, qty=1.0, rate=money(l["amount"]))
        elif x["type"] == "CustDep":
            add_line(x, 0, True, "1000", x["total"])
            add_line(x, 1, False, "2100", -x["total"])
        elif x["type"] == "DepAppl":
            add_line(x, 0, True, "2100", x["total"])
            add_line(x, 1, False, "1200", -x["total"])
            for doc, amt in x["applies"]:
                links.rows.append({"previousdoc": doc["id"], "nextdoc": x["id"], "linktype": "Deposit Application", "foreignamount": money(amt), "linkdate": ns_date(x["date"])})
        elif x["type"] == "CustPymt":
            add_line(x, 0, True, "1000", x["total"])
            add_line(x, 1, False, "1200", -x["total"])
            for doc, amt in x["applies"]:
                links.rows.append({"previousdoc": doc["id"], "nextdoc": x["id"], "linktype": "Payment", "foreignamount": money(amt), "linkdate": ns_date(x["date"])})
        elif x["type"] == "VendBill":
            add_line(x, 0, True, "2000", -x["total"])
            for i, l in enumerate(x["lines"], start=1):
                add_line(x, i, False, l["acct"], l["amount"], dept=l["dept"], memo=memo)
        elif x["type"] == "Journal":
            for i, l in enumerate(x["lines"]):
                add_line(x, i, i == 0, l["acct"], l["amount"], memo=x["memo"])
    t["netsuite_transaction"] = tx
    t["netsuite_transaction_line"] = lines
    t["netsuite_next_transaction_line_link"] = links


def render_adp(w: World, r: random.Random, t: dict, empno: dict) -> None:
    loc = {"CHI": "Chicago", "NSH": "Nashville", "DEN": "Denver"}
    workers = Table([("associate_oid", "str"), ("worker_id", "str"), ("legal_given_name", "str"), ("legal_family_name", "str"), ("preferred_given_name", "str"),
                     ("work_email", "str"), ("hire_date", "str"), ("termination_date", "str"), ("worker_status", "str"), ("pay_type", "str"),
                     ("flsa_status", "str"), ("pay_frequency", "str"), ("home_work_location_code", "str"), ("home_work_location_name", "str"),
                     ("job_title", "str"), ("department_name", "str"), ("addresses", "str")])
    assign = Table([("assignment_id", "str"), ("associate_oid", "str"), ("effective_date", "date"), ("job_title", "str"),
                    ("hourly_rate_amount", "float"), ("annual_rate_amount", "float"), ("currency_code", "str"), ("primary_indicator", "bool")])
    aoid = {}
    for p in w.people:
        if p["kind"] not in ("hourly", "salaried"):
            continue
        aoid[p["pid"]] = "G3" + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(14))
        hourly = p["kind"] == "hourly"
        city = loc[p["office"]]
        workers.rows.append({
            "associate_oid": aoid[p["pid"]], "worker_id": f"{empno[p['pid']]:06d}", "legal_given_name": p["first"], "legal_family_name": p["last"],
            "preferred_given_name": p["preferred"], "work_email": f"{p['first'].lower()}.{p['last'].lower()}@bloomproductions.example",
            "hire_date": p["hire"].isoformat(), "termination_date": p["term"].isoformat() if p["term"] else None,
            "worker_status": "Terminated" if p["term"] and p["term"] < AS_OF else "Active", "pay_type": "Hourly" if hourly else "Salaried",
            "flsa_status": "Non-Exempt" if hourly else "Exempt", "pay_frequency": "Weekly" if hourly else "Biweekly",
            "home_work_location_code": p["office"], "home_work_location_name": city, "job_title": p["title"], "department_name": p["dept"],
            "addresses": json.dumps([{"type": "Home", "city": city, "state": OFFICES[p["office"]]["state"], "postalCode": f"{r.randint(10000, 99999)}"}]),
        })
        for i, (eff, rate) in enumerate(p["rates"]):
            assign.rows.append({"assignment_id": f"{aoid[p['pid']]}-{i + 1}", "associate_oid": aoid[p["pid"]], "effective_date": eff, "job_title": p["title"],
                                "hourly_rate_amount": money(rate) if hourly else None, "annual_rate_amount": float(rate) if not hourly else None,
                                "currency_code": "USD", "primary_indicator": True})
    t["adp_workers"] = workers
    t["adp_work_assignments"] = assign
    stm = Table([("pay_statement_id", "str"), ("associate_oid", "str"), ("pay_date", "date"), ("pay_period_start_date", "date"),
                 ("pay_period_end_date", "date"), ("gross_pay_amount", "float"), ("net_pay_amount", "float"), ("total_hours", "float"), ("check_number", "str")])
    earn = Table([("pay_statement_id", "str"), ("line_number", "int"), ("earning_code", "str"), ("earning_name", "str"), ("hours", "float"),
                  ("rate", "float"), ("amount", "float")])
    names = {"REG": "Regular", "OT": "Overtime", "SAL": "Salary", "COM": "Commission"}
    for s in w.pay_statements:
        sid = f"PS{s['pay_date']:%Y%m%d}{s['id']:06d}"
        stm.rows.append({"pay_statement_id": sid, "associate_oid": aoid[s["pid"]], "pay_date": s["pay_date"], "pay_period_start_date": s["start"],
                         "pay_period_end_date": s["end"], "gross_pay_amount": money(s["gross"]), "net_pay_amount": money(s["net"]),
                         "total_hours": float(sum(e["hours"] for e in s["earnings"] if e["code"] in ("REG", "OT", "SAL"))), "check_number": f"DD{s['id']:07d}"})
        for i, e in enumerate(s["earnings"], start=1):
            earn.rows.append({"pay_statement_id": sid, "line_number": i, "earning_code": e["code"], "earning_name": names[e["code"]], "hours": float(e["hours"]),
                              "rate": money(e["rate_cents"]) if e["rate_cents"] else None, "amount": money(e["amount"])})
    t["adp_pay_statements"] = stm
    t["adp_pay_statement_earnings"] = earn


def render_google(w: World, r: random.Random, t: dict) -> None:
    cid = 4825519027
    camp = Table([("id", "int"), ("customer_id", "int"), ("name", "str"), ("status", "str"), ("advertising_channel_type", "str"), ("start_date", "str"),
                  ("end_date", "str"), ("bidding_strategy_type", "str"), ("campaign_budget_amount_micros", "int")])
    groups = Table([("id", "int"), ("campaign_id", "int"), ("name", "str"), ("status", "str"), ("type", "str")])
    for c in w.google_campaigns:
        camp.rows.append({"id": int(c["id"]), "customer_id": cid, "name": c["name"], "status": "ENABLED" if c["end"] is None else "PAUSED",
                          "advertising_channel_type": c["type"], "start_date": c["start"].isoformat(),
                          "end_date": c["end"].isoformat() if c["end"] else "2037-12-30",
                          "bidding_strategy_type": "MAXIMIZE_CONVERSIONS" if c["type"] != "DISPLAY" else "TARGET_CPA",
                          "campaign_budget_amount_micros": c["budget_cents"] * 10_000})
        for g in c["ad_groups"]:
            groups.rows.append({"id": int(g["id"]), "campaign_id": int(c["id"]), "name": g["name"], "status": "ENABLED", "type": "SEARCH_STANDARD" if c["type"] == "SEARCH" else "DISPLAY_STANDARD"})
    t["google_ads_campaign"] = camp
    t["google_ads_ad_group"] = groups
    stats = Table([("customer_id", "int"), ("campaign_id", "int"), ("segments_date", "date"), ("segments_device", "str"), ("metrics_impressions", "int"),
                   ("metrics_clicks", "int"), ("metrics_cost_micros", "int"), ("metrics_conversions", "float"), ("metrics_conversions_value", "float")])
    for s in w.google_stats:
        shares = [r.uniform(0.45, 0.6), r.uniform(0.3, 0.45)]
        shares.append(max(0.02, 1 - sum(shares)))
        tot = sum(shares)
        rem = {"cost": s["cost_cents"], "clicks": s["clicks"], "imp": s["impressions"], "conv": s["conversions"]}
        for i, dev in enumerate(("MOBILE", "DESKTOP", "TABLET")):
            if i < 2:
                part = {k: int(v * shares[i] / tot) for k, v in (("cost", s["cost_cents"]), ("clicks", s["clicks"]), ("imp", s["impressions"]), ("conv", s["conversions"]))}
                for k in rem:
                    rem[k] -= part[k]
            else:
                part = rem
            stats.rows.append({"customer_id": cid, "campaign_id": int(s["campaign"]), "segments_date": s["date"], "segments_device": dev,
                               "metrics_impressions": part["imp"], "metrics_clicks": part["clicks"], "metrics_cost_micros": part["cost"] * 10_000,
                               "metrics_conversions": float(part["conv"]), "metrics_conversions_value": float(part["conv"] * 250)})
    t["google_ads_campaign_stats"] = stats


def render_meta(w: World, r: random.Random, t: dict) -> None:
    acct = "act_1029384756"
    camp = Table([("id", "str"), ("account_id", "str"), ("name", "str"), ("objective", "str"), ("status", "str"), ("created_time", "str"),
                  ("start_time", "str"), ("stop_time", "str"), ("daily_budget", "str")])
    sets = Table([("id", "str"), ("campaign_id", "str"), ("name", "str"), ("status", "str"), ("optimization_goal", "str"), ("billing_event", "str")])
    ads = Table([("id", "str"), ("adset_id", "str"), ("campaign_id", "str"), ("name", "str"), ("status", "str"), ("creative_id", "str")])
    budgets = {name: b for name, _, _, _, b in META_CAMPAIGNS}
    names = {}
    for c in w.meta_campaigns:
        names[c["id"]] = c["name"]
        camp.rows.append({"id": c["id"], "account_id": acct, "name": c["name"], "objective": c["objective"], "status": "ACTIVE" if c["end"] is None else "PAUSED",
                          "created_time": f"{(c['start'] - timedelta(days=3)).isoformat()}T15:04:11+0000", "start_time": f"{c['start'].isoformat()}T05:00:00+0000",
                          "stop_time": f"{c['end'].isoformat()}T04:59:00+0000" if c["end"] else None, "daily_budget": str(budgets[c["name"]] * 100)})
        for s in c["ad_sets"]:
            names[s["id"]] = s["name"]
            sets.rows.append({"id": s["id"], "campaign_id": c["id"], "name": s["name"], "status": "ACTIVE",
                              "optimization_goal": "LEAD_GENERATION" if c["objective"] == "OUTCOME_LEADS" else "REACH", "billing_event": "IMPRESSIONS"})
            for a in s["ads"]:
                names[a["id"]] = a["name"]
                ads.rows.append({"id": a["id"], "adset_id": s["id"], "campaign_id": c["id"], "name": a["name"], "status": "ACTIVE", "creative_id": str(r.randint(10 ** 14, 10 ** 15 - 1))})
    t["meta_ads_campaigns"] = camp
    t["meta_ads_ad_sets"] = sets
    t["meta_ads_ads"] = ads
    ins = Table([("date_start", "str"), ("date_stop", "str"), ("account_id", "str"), ("campaign_id", "str"), ("campaign_name", "str"), ("adset_id", "str"),
                 ("ad_id", "str"), ("ad_name", "str"), ("spend", "str"), ("impressions", "str"), ("clicks", "str"), ("cpm", "str"), ("actions", "str")])
    for m in w.meta_insights:
        actions = [{"action_type": "link_click", "value": str(m["clicks"])}]
        if m["platform_leads"]:
            actions.append({"action_type": "lead", "value": str(m["platform_leads"])})
            actions.append({"action_type": "onsite_conversion.lead_grouped", "value": str(m["platform_leads"])})
        imp = m["impressions"]
        ins.rows.append({"date_start": m["date"].isoformat(), "date_stop": m["date"].isoformat(), "account_id": acct, "campaign_id": m["campaign"],
                         "campaign_name": names[m["campaign"]], "adset_id": m["ad_set"], "ad_id": m["ad"], "ad_name": names[m["ad"]],
                         "spend": f"{m['spend_cents'] / 100:.2f}", "impressions": str(imp), "clicks": str(m["clicks"]),
                         "cpm": f"{(m['spend_cents'] / 100) / imp * 1000:.6f}" if imp else "0", "actions": json.dumps(actions)})
    t["meta_ads_insights"] = ins
