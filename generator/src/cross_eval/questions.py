"""Question templates. Each computes its gold answer from the simulated history (the truth) and carries a
reference SQL query over the rendered tables that must reproduce it. The SQL proves the question is
answerable from the data; it is never used to score an answer."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from .render import slug
from .world import AS_OF, CREW_ROLES, DEPTS, EVENT_TYPES, OFFICES, US_OFFICES, World, rate_on

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
CITY = {k: v["city"] for k, v in OFFICES.items()}

NS_DATE = "CAST(strptime({col}, '%m/%d/%Y') AS DATE)"
CW_DATE = "CAST(strptime({col}, '%m/%d/%Y') AS DATE)"
SHOW_REF = "COALESCE(NULLIF(replace({t}.custbody_show_number, '#', ''), ''), NULLIF(regexp_extract({t}.memo, '(\\d{{2}}-\\d{{4}})', 1), ''))"


def month_period(y: int, m: int) -> dict:
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return {"key": f"{y}-{m:02d}", "label": f"{MONTHS[m - 1]} {y}", "start": start, "end": end}


def quarter_period(y: int, q: int) -> dict:
    start = date(y, 3 * q - 2, 1)
    end = date(y + (q == 4), (3 * q) % 12 + 1, 1) - timedelta(days=1)
    return {"key": f"{y}Q{q}", "label": f"Q{q} {y}", "start": start, "end": end}


def span_period(key: str) -> dict:
    return {
        "2025": {"key": "2025", "label": "2025", "start": date(2025, 1, 1), "end": date(2025, 12, 31)},
        "2024H2": {"key": "2024H2", "label": "the second half of 2024", "start": date(2024, 7, 1), "end": date(2024, 12, 31)},
        "2025H1": {"key": "2025H1", "label": "the first half of 2025", "start": date(2025, 1, 1), "end": date(2025, 6, 30)},
        "2025H2": {"key": "2025H2", "label": "the second half of 2025", "start": date(2025, 7, 1), "end": date(2025, 12, 31)},
        "2026H1": {"key": "2026H1", "label": "the first half of 2026", "start": date(2026, 1, 1), "end": date(2026, 6, 30)},
    }[key]


MONTHS_IN_WINDOW = [month_period(y, m) for y, m in [(2024, m) for m in range(8, 13)] + [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 7)]]
QUARTERS = [quarter_period(y, q) for y, q in ((2024, 3), (2024, 4), (2025, 1), (2025, 2), (2025, 3), (2025, 4), (2026, 1), (2026, 2))]
SPANS = [span_period(k) for k in ("2024H2", "2025H1", "2025H2", "2025", "2026H1")]


def between(expr: str, p: dict) -> str:
    return f"{expr} BETWEEN DATE '{p['start'].isoformat()}' AND DATE '{p['end'].isoformat()}'"


def inside(d: date | None, p: dict) -> bool:
    return d is not None and p["start"] <= d <= p["end"]


def money_answer(v: float, currency: str = "USD", tol: float = 0.01) -> dict:
    return {"type": "money", "value": round(v, 2), "currency": currency, "tolerance": tol, "min_sig_figs": 2}


def count_answer(n: int) -> dict:
    return {"type": "count", "value": int(n)}


def number_answer(v: float, tol: float = 0.02, unit: str | None = None) -> dict:
    a = {"type": "number", "value": round(v, 2), "tolerance": tol, "min_sig_figs": 2}
    if unit:
        a["unit"] = unit
    return a


def entity_answer(name: str, aliases: list) -> dict:
    return {"type": "entity", "value": name, "aliases": sorted({a for a in aliases if a and a != name})}


def unique_top(scores: dict, min_gap: float = 0.005):
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] <= 0:
        return None
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] <= abs(ranked[0][1]) * min_gap:
        return None
    return ranked[0][0]


@dataclass
class Ctx:
    w: World
    core: dict

    def rows(self, system: str, table: str) -> list:
        """Rendered rows, for questions whose truth is a system's own record (tasks logged, rate tables)."""
        return self.core[system][table].rows

    def __post_init__(self):
        w = self.w
        self.shows = {s["sid"]: s for s in w.shows}
        self.show_by_no = {s["number"]: s for s in w.shows}
        self.opps = {o["id"]: o for o in w.opps}
        self.invoices = [t for t in w.transactions if t["type"] == "CustInvc" and not t["void"]]
        self.inv_by_show: dict[int, list] = {}
        for t in self.invoices:
            self.inv_by_show.setdefault(t["show"], []).append(t)
        self.bills_by_show: dict[int, list] = {}
        for t in w.transactions:
            if t["type"] == "VendBill" and t.get("show"):
                self.bills_by_show.setdefault(t["show"], []).append(t)
        self.calls_by_show: dict[int, list] = {}
        for c in w.crew_calls:
            self.calls_by_show.setdefault(c["show"], []).append(c)
        self.venue = {v["vid"]: v for v in w.venues}

    def usd(self, t: dict) -> float:
        return t["total"] * t["fx"] / 100

    def person_aliases(self, pid: int) -> tuple[str, list]:
        p = self.w.person(pid)
        legal = f"{p['first']} {p['last']}"
        return legal, [legal, f"{p['preferred']} {p['last']}" if p["preferred"] else None]

    def employee_labor(self, sid: int) -> float:
        total = 0.0
        for c in self.calls_by_show.get(sid, []):
            p = self.w.person(c["pid"])
            if p["kind"] == "hourly":
                total += c["hours"] * rate_on(p, c["date"]) / 100
        return total

    def show_aliases(self, sh: dict) -> list:
        return [sh["number"], sh["name"], f"{sh['number']} {sh['name']}", f"{sh['name']} ({sh['number']})"]


TEMPLATES = []


def template(name: str, systems: list, stratum: str, difficulty: str, test_only: bool = False):
    """test_only templates never appear in the query log, so their tables stay in the log's long tail."""
    def deco(fn):
        TEMPLATES.append((name, systems, stratum, difficulty, test_only, fn))
        return fn
    return deco


@template("crm_won_count_quarter", ["salesforce"], "single_table", "easy")
def crm_won_count_quarter(ctx: Ctx):
    for p in QUARTERS:
        n = sum(1 for o in ctx.w.opps if o["won"] and inside(o["close"], p))
        yield p["key"], f"How many deals did we win in {p['label']}?", count_answer(n), f"""
SELECT COUNT(*) FROM salesforce_opportunity
WHERE is_won AND NOT is_deleted AND {between('close_date', p)}"""


@template("crm_leads_source_month", ["salesforce"], "single_table", "easy")
def crm_leads_source_month(ctx: Ctx):
    labels = {"Google Ads": "Google Ads", "Paid Social": "paid social", "Website": "website", "Trade Show": "trade show"}
    for i, p in enumerate(MONTHS_IN_WINDOW):
        src = list(labels)[i % 4]
        n = sum(1 for l in ctx.w.leads if l["source"] == src and inside(l["created"].date(), p))
        yield f"{src}:{p['key']}", f"How many {labels[src]} leads came in during {p['label']}?", count_answer(n), f"""
SELECT COUNT(*) FROM salesforce_lead
WHERE NOT is_deleted AND lead_source = '{src}' AND {between('CAST(substr(created_date, 1, 10) AS DATE)', p)}"""


@template("crm_won_amount_type", ["salesforce"], "single_table", "easy")
def crm_won_amount_type(ctx: Ctx):
    for et, spec in EVENT_TYPES.items():
        for key in ("2025", "2026H1"):
            p = span_period(key)
            v = sum(o["amount"] for o in ctx.w.opps if o["won"] and o["etype"] == et and inside(o["close"], p))
            if v == 0:
                continue
            yield f"{et}:{key}", f"What was the total value of {spec['label'].lower()} deals we closed-won in {p['label']}?", money_answer(v), f"""
SELECT SUM(amount) FROM salesforce_opportunity
WHERE is_won AND NOT is_deleted AND event_type_c = '{spec['label']}' AND {between('close_date', p)}"""


@template("erp_invoiced_month", ["netsuite"], "single_table", "medium")
def erp_invoiced_month(ctx: Ctx):
    for p in MONTHS_IN_WINDOW:
        v = sum(ctx.usd(t) for t in ctx.invoices if inside(t["date"], p))
        yield p["key"], f"How much did we invoice in {p['label']}, in US dollars?", money_answer(v), f"""
SELECT SUM(foreigntotal * exchangerate) FROM netsuite_transaction
WHERE type = 'CustInvc' AND voided = 'F' AND {between(NS_DATE.format(col='trandate'), p)}"""


@template("erp_open_ar_aging", ["netsuite"], "single_table", "medium")
def erp_open_ar_aging(ctx: Ctx):
    for days in (0, 30, 60, 90):
        cutoff = AS_OF - timedelta(days=days)
        v = sum(t["remaining"] * t["fx"] / 100 for t in ctx.invoices if t["remaining"] > 0 and (days == 0 or t["date"] < cutoff))
        q = ("How much do customers owe us on open invoices as of June 30, 2026, in US dollars?" if days == 0 else
             f"As of June 30, 2026, how much is still unpaid on invoices issued more than {days} days earlier, in US dollars?")
        cond = "" if days == 0 else f" AND {NS_DATE.format(col='trandate')} < DATE '{cutoff.isoformat()}'"
        yield str(days), q, money_answer(v), f"""
SELECT SUM(foreignamountremaining * exchangerate) FROM netsuite_transaction
WHERE type = 'CustInvc' AND voided = 'F' AND foreignamountremaining > 0{cond}"""


@template("erp_top_ar_customer", ["netsuite"], "single_system_join", "medium")
def erp_top_ar_customer(ctx: Ctx):
    for key in ("all", "2025", "2026H1"):
        p = None if key == "all" else span_period(key)
        scores: dict[int, float] = {}
        for t in ctx.invoices:
            if t["remaining"] > 0 and (p is None or inside(t["date"], p)):
                scores[t["client"]] = scores.get(t["client"], 0) + t["remaining"] * t["fx"] / 100
        top = unique_top(scores)
        if top is None:
            continue
        c = ctx.w.client(top)
        q = ("Which customer has the largest unpaid invoice balance as of June 30, 2026?" if p is None else
             f"Which customer has the largest unpaid balance on invoices we issued in {p['label']}?")
        cond = "" if p is None else f" AND {between(NS_DATE.format(col='t.trandate'), p)}"
        yield key, q, entity_answer(c["base"], c["aliases"]), f"""
SELECT c.companyname FROM netsuite_transaction t JOIN netsuite_customer c ON c.id = t.entity
WHERE t.type = 'CustInvc' AND t.voided = 'F' AND t.foreignamountremaining > 0{cond}
GROUP BY c.companyname ORDER BY SUM(t.foreignamountremaining * t.exchangerate) DESC LIMIT 1"""


@template("erp_dept_revenue", ["netsuite"], "single_system_join", "hard")
def erp_dept_revenue(ctx: Ctx):
    for i, (code, dept) in enumerate(DEPTS.items()):
        for key in ("2025", "2026H1"):
            p = span_period(key)
            v = sum(l["amount"] * t["fx"] / 100 for t in ctx.invoices if inside(t["date"], p) for l in t["lines"] if l["kind"] == "dept" and l["dept"] == code)
            yield f"{code}:{key}", f"How much {dept.lower()} revenue did we invoice in {p['label']}, in US dollars?", money_answer(v), f"""
SELECT SUM(-l.foreignamount * t.exchangerate)
FROM netsuite_transaction_line l
JOIN netsuite_transaction t ON t.id = l."transaction"
JOIN netsuite_department d ON d.id = l.department
WHERE t.type = 'CustInvc' AND t.voided = 'F' AND l.mainline = 'F' AND d.name = '{dept}'
  AND {between(NS_DATE.format(col='t.trandate'), p)}"""


@template("erp_days_to_pay", ["netsuite"], "single_system_join", "hard")
def erp_days_to_pay(ctx: Ctx):
    for key in ("2024H2", "2025H1", "2025H2", "2025"):
        p = span_period(key)
        ds = [(t["paid_date"] - t["date"]).days for t in ctx.invoices if t["paid_in_full"] and inside(t["date"], p)]
        v = sum(ds) / len(ds)
        yield key, (f"On average, how many days did customers take to pay the invoices we issued in {p['label']}? "
                    "Only count invoices that are paid in full."), number_answer(v, unit="days"), f"""
WITH inv AS (
  SELECT id, {NS_DATE.format(col='trandate')} AS d FROM netsuite_transaction
  WHERE type = 'CustInvc' AND voided = 'F' AND status = 'Paid In Full'),
pay AS (
  SELECT k.previousdoc AS inv_id, MAX({NS_DATE.format(col='p.trandate')}) AS paid
  FROM netsuite_next_transaction_line_link k JOIN netsuite_transaction p ON p.id = k.nextdoc
  WHERE p.type = 'CustPymt' GROUP BY 1)
SELECT AVG(date_diff('day', inv.d, pay.paid)) FROM inv JOIN pay ON pay.inv_id = inv.id
WHERE {between('inv.d', p)}"""


@template("adp_gross_month", ["adp"], "single_table", "easy")
def adp_gross_month(ctx: Ctx):
    for p in MONTHS_IN_WINDOW:
        v = sum(s["gross"] for s in ctx.w.pay_statements if inside(s["pay_date"], p)) / 100
        yield p["key"], f"What was our total gross payroll for paychecks dated in {p['label']}?", money_answer(v), f"""
SELECT SUM(gross_pay_amount) FROM adp_pay_statements WHERE {between('pay_date', p)}"""


@template("adp_ot_hours_quarter", ["adp"], "single_system_join", "medium")
def adp_ot_hours_quarter(ctx: Ctx):
    for p in QUARTERS:
        v = sum(e["hours"] for s in ctx.w.pay_statements if inside(s["pay_date"], p) for e in s["earnings"] if e["code"] == "OT")
        yield p["key"], f"How many overtime hours did we pay for on paychecks dated in {p['label']}?", number_answer(v, tol=0.01, unit="hours"), f"""
SELECT SUM(e.hours) FROM adp_pay_statement_earnings e JOIN adp_pay_statements s ON s.pay_statement_id = e.pay_statement_id
WHERE e.earning_code = 'OT' AND {between('s.pay_date', p)}"""


@template("adp_office_gross", ["adp"], "single_system_join", "medium")
def adp_office_gross(ctx: Ctx):
    for office in US_OFFICES:
        for key in ("2025", "2026H1", "2024H2"):
            p = span_period(key)
            v = sum(s["gross"] for s in ctx.w.pay_statements if ctx.w.person(s["pid"])["office"] == office and inside(s["pay_date"], p)) / 100
            yield f"{office}:{key}", f"What was total gross payroll for the {CITY[office]} office in {p['label']}?", money_answer(v), f"""
SELECT SUM(s.gross_pay_amount) FROM adp_pay_statements s JOIN adp_workers w ON w.associate_oid = s.associate_oid
WHERE w.home_work_location_name = '{CITY[office]}' AND {between('s.pay_date', p)}"""


@template("adp_active_hourly", ["adp"], "single_table", "easy")
def adp_active_hourly(ctx: Ctx):
    hourly = [p for p in ctx.w.people if p["kind"] == "hourly"]
    boundaries = {p["hire"] for p in hourly} | {p["term"] for p in hourly if p["term"]}
    for p_ in MONTHS_IN_WINDOW[::2]:
        d = p_["start"] + timedelta(days=14)
        while d in boundaries:
            d += timedelta(days=1)
        n = sum(1 for p in hourly if p["hire"] <= d and (p["term"] is None or d <= p["term"]))
        label = f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
        yield d.isoformat(), f"How many hourly employees did we have on {label}?", count_answer(n), f"""
SELECT COUNT(*) FROM adp_workers
WHERE pay_type = 'Hourly' AND CAST(hire_date AS DATE) <= DATE '{d.isoformat()}'
  AND (termination_date IS NULL OR CAST(termination_date AS DATE) >= DATE '{d.isoformat()}')"""


@template("gads_spend_month", ["google_ads"], "single_table", "easy")
def gads_spend_month(ctx: Ctx):
    for p in MONTHS_IN_WINDOW:
        v = sum(s["cost_cents"] for s in ctx.w.google_stats if inside(s["date"], p)) / 100
        yield p["key"], f"How much did we spend on Google Ads in {p['label']}?", money_answer(v), f"""
SELECT SUM(metrics_cost_micros) / 1e6 FROM google_ads_campaign_stats WHERE {between('segments_date', p)}"""


@template("meta_spend_quarter", ["meta_ads"], "single_table", "easy")
def meta_spend_quarter(ctx: Ctx):
    for p in QUARTERS:
        v = sum(m["spend_cents"] for m in ctx.w.meta_insights if inside(m["date"], p)) / 100
        yield p["key"], f"How much did we spend on Meta ads in {p['label']}?", money_answer(v), f"""
SELECT SUM(CAST(spend AS DOUBLE)) FROM meta_ads_insights WHERE {between('CAST(date_start AS DATE)', p)}"""


@template("gads_top_campaign_clicks", ["google_ads"], "single_system_join", "medium")
def gads_top_campaign_clicks(ctx: Ctx):
    names = {c["id"]: c["name"] for c in ctx.w.google_campaigns}
    for p in SPANS + QUARTERS[::2]:
        scores: dict[str, float] = {}
        for s in ctx.w.google_stats:
            if inside(s["date"], p):
                scores[s["campaign"]] = scores.get(s["campaign"], 0) + s["clicks"]
        top = unique_top(scores)
        if top is None:
            continue
        yield p["key"], f"Which Google Ads campaign got the most clicks in {p['label']}?", entity_answer(names[top], []), f"""
SELECT c.name FROM google_ads_campaign_stats s JOIN google_ads_campaign c ON c.id = s.campaign_id
WHERE {between('s.segments_date', p)} GROUP BY c.name ORDER BY SUM(s.metrics_clicks) DESC LIMIT 1"""


META_LEADS_SQL = """(
  SELECT CAST(date_start AS DATE) AS d, CAST(a.value AS INTEGER) AS n
  FROM (SELECT date_start, UNNEST(from_json(actions, '[{"action_type":"VARCHAR","value":"VARCHAR"}]')) AS a FROM meta_ads_insights)
  WHERE a.action_type = 'lead')"""


@template("meta_leads_month", ["meta_ads"], "single_table", "hard")
def meta_leads_month(ctx: Ctx):
    for p in MONTHS_IN_WINDOW:
        v = sum(m["platform_leads"] for m in ctx.w.meta_insights if inside(m["date"], p))
        yield p["key"], f"How many leads did Meta report for {p['label']}?", count_answer(v), f"""
SELECT SUM(n) FROM {META_LEADS_SQL} WHERE {between('d', p)}"""


@template("cw_cancelled", ["cuewright"], "single_table", "easy")
def cw_cancelled(ctx: Ctx):
    for p in SPANS:
        n = sum(1 for s in ctx.w.shows if s["cancel"] and inside(s["start"], p))
        yield p["key"], f"How many shows scheduled to start in {p['label']} were cancelled?", count_answer(n), f"""
SELECT COUNT(*) FROM cuewright_shows WHERE status_cd = 'CANC' AND {between(CW_DATE.format(col='show_start_dt'), p)}"""


@template("cw_office_shows_month", ["cuewright"], "single_table", "easy")
def cw_office_shows_month(ctx: Ctx):
    offices = list(OFFICES)
    for i, p in enumerate(MONTHS_IN_WINDOW):
        office = offices[i % 4]
        n = sum(1 for s in ctx.w.shows if s["office"] == office and not s["cancel"] and inside(s["start"], p))
        yield f"{office}:{p['key']}", f"How many shows did our {CITY[office]} office start in {p['label']}, not counting cancelled ones?", count_answer(n), f"""
SELECT COUNT(*) FROM cuewright_shows
WHERE office_cd = '{office}' AND status_cd <> 'CANC' AND {between(CW_DATE.format(col='show_start_dt'), p)}"""


@template("cw_top_venue", ["cuewright"], "single_system_join", "medium")
def cw_top_venue(ctx: Ctx):
    name_counts: dict[str, int] = {}
    for v in ctx.w.venues:
        name_counts[v["name"]] = name_counts.get(v["name"], 0) + 1
    for p in SPANS + QUARTERS:
        scores: dict[int, float] = {}
        for s in ctx.w.shows:
            if not s["cancel"] and inside(s["start"], p):
                scores[s["venue"]] = scores.get(s["venue"], 0) + 1
        top = unique_top(scores)
        if top is None or name_counts[ctx.venue[top]["name"]] > 1:
            continue
        v = ctx.venue[top]
        yield p["key"], f"Which venue hosted the most of our shows in {p['label']}, excluding cancelled shows?", entity_answer(v["name"], [f"{v['name']}, {v['city']}"]), f"""
SELECT v.venue_nm FROM cuewright_shows s JOIN cuewright_venues v ON v.venue_id = s.venue_id
WHERE s.status_cd <> 'CANC' AND {between(CW_DATE.format(col='s.show_start_dt'), p)}
GROUP BY v.venue_id, v.venue_nm ORDER BY COUNT(*) DESC LIMIT 1"""


@template("cw_show_crew_hours", ["cuewright"], "single_system_join", "medium")
def cw_show_crew_hours(ctx: Ctx):
    r = random.Random(ctx.w.seed + 11)
    cands = sorted(s["number"] for s in ctx.w.shows if ctx.calls_by_show.get(s["sid"]) and s["strike"] < AS_OF)
    for no in r.sample(cands, 16):
        s = ctx.show_by_no[no]
        v = sum(c["hours"] for c in ctx.calls_by_show[s["sid"]])
        yield no, f"How many total crew hours were logged on show {no}?", number_answer(v, tol=0.0, unit="hours"), f"""
SELECT SUM(c.hrs_worked) FROM cuewright_crew_calls c JOIN cuewright_shows s ON s.show_id = c.show_id WHERE s.show_no = '{no}'"""


CONTRACT_CTE = """WITH fq AS (
  SELECT q.show_id, q.disc_pct, SUM(l.ext_price) AS gross
  FROM cuewright_quotes q JOIN cuewright_quote_lines l ON l.quote_id = q.quote_id
  WHERE q.is_final = 'Y' GROUP BY 1, 2),
co AS (
  SELECT show_id, SUM(CAST(replace(replace(co_amt, '$', ''), ',', '') AS DOUBLE)) AS amt
  FROM cuewright_change_orders WHERE void_flg = 'N' GROUP BY 1),
cv AS (
  SELECT fq.show_id, ROUND(fq.gross * (1 - fq.disc_pct / 100), 2) + COALESCE(co.amt, 0) AS contract
  FROM fq LEFT JOIN co ON co.show_id = fq.show_id)"""


@template("cw_contract_value_quarter", ["cuewright"], "single_system_join", "hard")
def cw_contract_value_quarter(ctx: Ctx):
    for office in US_OFFICES:
        for p in QUARTERS[:6]:
            shows = [s for s in ctx.w.shows if s["office"] == office and inside(s["start"], p)]
            v = sum(s["contract_cents"] for s in shows if not s["cancel"]) / 100
            ans = money_answer(v)
            cancelled = sum(s["quote"]["net"] for s in shows if s["cancel"]) / 100
            if cancelled:
                ans["accepted"] = [{"value": round(v + cancelled, 2), "reading": "includes the quoted value of cancelled shows"}]
            yield f"{office}:{p['key']}", f"What was the total contract value of {CITY[office]} shows that started in {p['label']}, including change orders?", ans, f"""
{CONTRACT_CTE}
SELECT SUM(cv.contract) FROM cuewright_shows s JOIN cv ON cv.show_id = s.show_id
WHERE s.office_cd = '{office}' AND s.status_cd <> 'CANC' AND {between(CW_DATE.format(col='s.show_start_dt'), p)}"""


@template("cw_top_crew_hours_month", ["cuewright"], "single_system_join", "medium")
def cw_top_crew_hours_month(ctx: Ctx):
    for p in MONTHS_IN_WINDOW[::2]:
        scores: dict[int, float] = {}
        for c in ctx.w.crew_calls:
            if inside(c["date"], p):
                scores[c["pid"]] = scores.get(c["pid"], 0) + c["hours"]
        top = unique_top(scores, min_gap=0.0)
        if top is None:
            continue
        legal, aliases = ctx.person_aliases(top)
        pp = ctx.w.person(top)
        shown = f"{pp['preferred'] or pp['first']} {pp['last']}"
        yield p["key"], f"Which crew member worked the most hours in {p['label']}?", entity_answer(shown, aliases), f"""
SELECT cr.first_nm || ' ' || cr.last_nm FROM cuewright_crew_calls c JOIN cuewright_crew cr ON cr.crew_id = c.crew_id
WHERE {between('CAST(c.work_dt AS DATE)', p)}
GROUP BY cr.crew_id, cr.first_nm, cr.last_nm ORDER BY SUM(c.hrs_worked) DESC LIMIT 1"""


@template("cw_open_repairs", ["cuewright"], "single_table", "easy")
def cw_open_repairs(ctx: Ctx):
    for p in SPANS:
        n = sum(1 for x in ctx.w.repairs if x["status"] in ("OPEN", "IN_REPAIR") and inside(x["opened"], p))
        yield p["key"], f"How many gear repair tickets opened in {p['label']} are still unresolved?", count_answer(n), f"""
SELECT COUNT(*) FROM cuewright_repair_tickets
WHERE tkt_status IN ('OPEN', 'IN_REPAIR') AND {between(CW_DATE.format(col='opened_dt'), p)}"""


def invoiced_show_sql(show_no: str) -> str:
    return f"""SELECT SUM(foreigntotal * exchangerate) FROM netsuite_transaction t
  WHERE t.type = 'CustInvc' AND t.voided = 'F' AND {SHOW_REF.format(t='t')} = '{show_no}'"""


@template("x_invoice_vs_crm", ["cuewright", "netsuite", "salesforce"], "cross_system", "hard")
def x_invoice_vs_crm(ctx: Ctx):
    r = random.Random(ctx.w.seed + 12)
    cands = sorted(s["number"] for s in ctx.w.shows if s["opp"] and s["currency"] == "USD" and ctx.inv_by_show.get(s["sid"]))
    for no in r.sample(cands, 14):
        s = ctx.show_by_no[no]
        diff = sum(ctx.usd(t) for t in ctx.inv_by_show[s["sid"]]) - ctx.opps[s["opp"]]["amount"]
        yield no, (f"For show {no} ({s['name']}), how much higher or lower was the final invoice than the amount on the CRM deal? "
                   "Give a positive number if the invoice was higher."), money_answer(diff), f"""
WITH s AS (SELECT crm_opp_ref FROM cuewright_shows WHERE show_no = '{no}'),
inv AS ({invoiced_show_sql(no)}),
o AS (SELECT o.amount FROM salesforce_opportunity o, s WHERE NOT o.is_deleted AND left(o.id, 15) = left(s.crm_opp_ref, 15))
SELECT (SELECT * FROM inv) - (SELECT amount FROM o)"""


@template("x_campaign_won_count", ["google_ads", "salesforce"], "cross_system", "hard")
def x_campaign_won_count(ctx: Ctx):
    names = {c["id"]: c["name"] for c in ctx.w.google_campaigns}
    for key in ("2025", "2025H1", "2025H2", "2026H1"):
        p = span_period(key)
        counts: dict[str, int] = {}
        for o in ctx.w.opps:
            if o["won"] and o["google"] and inside(o["close"], p):
                counts[o["google"]] = counts.get(o["google"], 0) + 1
        for cid, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]:
            yield f"{cid}:{key}", f"How many deals did we win in {p['label']} that trace back to leads from the Google Ads campaign \"{names[cid]}\"?", count_answer(n), f"""
SELECT COUNT(*) FROM salesforce_lead l
JOIN salesforce_opportunity o ON o.id = l.converted_opportunity_id
JOIN google_ads_campaign c ON l.utm_campaign_c = trim(regexp_replace(lower(c.name), '[^a-z0-9]+', '-', 'g'), '-')
WHERE NOT l.is_deleted AND NOT o.is_deleted AND o.is_won AND c.name = '{names[cid]}' AND {between('o.close_date', p)}"""


@template("x_google_cost_per_won", ["google_ads", "salesforce"], "cross_system", "medium")
def x_google_cost_per_won(ctx: Ctx):
    for p in SPANS + QUARTERS[2:6]:
        spend = sum(s["cost_cents"] for s in ctx.w.google_stats if inside(s["date"], p)) / 100
        won = sum(1 for o in ctx.w.opps if o["won"] and o["lead_source"] == "Google Ads" and inside(o["close"], p))
        if not won:
            continue
        yield p["key"], (f"What was our Google Ads cost per won deal in {p['label']}? Divide Google Ads spend by the number of deals "
                         "closed-won in that period whose lead source is Google Ads."), money_answer(spend / won), f"""
SELECT (SELECT SUM(metrics_cost_micros) / 1e6 FROM google_ads_campaign_stats WHERE {between('segments_date', p)})
     / (SELECT COUNT(*) FROM salesforce_opportunity WHERE is_won AND NOT is_deleted AND lead_source = 'Google Ads' AND {between('close_date', p)})"""


@template("x_meta_vs_crm_leads", ["meta_ads", "salesforce"], "cross_system", "hard")
def x_meta_vs_crm_leads(ctx: Ctx):
    for p in MONTHS_IN_WINDOW[1::2]:
        meta = sum(m["platform_leads"] for m in ctx.w.meta_insights if inside(m["date"], p))
        crm = sum(1 for l in ctx.w.leads if l["source"] == "Paid Social" and inside(l["created"].date(), p))
        yield p["key"], f"In {p['label']}, how many more leads did Meta report than Salesforce recorded from paid social?", number_answer(meta - crm, tol=0.0, unit="leads"), f"""
SELECT (SELECT SUM(n) FROM {META_LEADS_SQL} WHERE {between('d', p)})
     - (SELECT COUNT(*) FROM salesforce_lead WHERE NOT is_deleted AND lead_source = 'Paid Social'
        AND {between('CAST(substr(created_date, 1, 10) AS DATE)', p)})"""


LABOR_SQL = """SELECT SUM(c.hrs_worked * a.hourly_rate_amount)
FROM cuewright_crew_calls c
JOIN cuewright_shows s ON s.show_id = c.show_id
JOIN cuewright_crew cr ON cr.crew_id = c.crew_id
JOIN adp_workers w ON CAST(w.worker_id AS INTEGER) = CAST(replace(cr.emp_no, 'E-', '') AS INTEGER)
JOIN adp_work_assignments a ON a.associate_oid = w.associate_oid
WHERE s.show_no = '{no}' AND cr.crew_type = 'EMP'
  AND a.effective_date = (SELECT MAX(a2.effective_date) FROM adp_work_assignments a2
                          WHERE a2.associate_oid = a.associate_oid AND a2.effective_date <= CAST(c.work_dt AS DATE))"""


@template("x_show_labor_cost", ["cuewright", "adp"], "cross_system", "hard")
def x_show_labor_cost(ctx: Ctx):
    r = random.Random(ctx.w.seed + 13)
    cands = sorted(s["number"] for s in ctx.w.shows if s["office"] in US_OFFICES and ctx.employee_labor(s["sid"]) > 0 and s["strike"] < AS_OF)
    for no in r.sample(cands, 14):
        v = ctx.employee_labor(ctx.show_by_no[no]["sid"])
        yield no, (f"What was the employee crew labor cost on show {no}, using each employee's base hourly rate in effect on the day they worked? "
                   "Leave out freelancers."), money_answer(v), "\n" + LABOR_SQL.format(no=no)


@template("x_office_invoiced_quarter", ["cuewright", "netsuite"], "cross_system", "medium")
def x_office_invoiced_quarter(ctx: Ctx):
    for i, p in enumerate(QUARTERS[:7]):
        for office in (list(OFFICES)[i % 4], list(OFFICES)[(i + 2) % 4]):
            v = sum(ctx.usd(t) for s in ctx.w.shows if s["office"] == office and not s["cancel"] and inside(s["end"], p) for t in ctx.inv_by_show.get(s["sid"], []))
            yield f"{office}:{p['key']}", f"How much have we invoiced, in US dollars, for {CITY[office]} shows that ended in {p['label']}?", money_answer(v), f"""
SELECT SUM(t.foreigntotal * t.exchangerate)
FROM netsuite_transaction t JOIN cuewright_shows s ON s.show_no = {SHOW_REF.format(t='t')}
WHERE t.type = 'CustInvc' AND t.voided = 'F' AND s.office_cd = '{office}' AND s.status_cd <> 'CANC'
  AND {between(CW_DATE.format(col='s.show_end_dt'), p)}"""


@template("x_top_freelance_show", ["netsuite", "cuewright"], "cross_system", "hard")
def x_top_freelance_show(ctx: Ctx):
    for p in SPANS + QUARTERS:
        scores: dict[int, float] = {}
        for t in ctx.w.transactions:
            if t["type"] == "VendBill" and t.get("category") == "freelance" and inside(t["date"], p):
                scores[t["show"]] = scores.get(t["show"], 0) + ctx.usd(t)
        top = unique_top(scores)
        if top is None or sum(1 for x in ctx.w.shows if x["name"] == ctx.shows[top]["name"]) > 1:
            continue
        s = ctx.shows[top]
        yield p["key"], f"Which show had the highest freelance crew cost billed to us in {p['label']}? Give the show's name.", entity_answer(s["name"], ctx.show_aliases(s)), f"""
SELECT s.show_nm FROM netsuite_transaction t
JOIN netsuite_vendor v ON v.id = t.entity
JOIN cuewright_shows s ON s.show_no = {SHOW_REF.format(t='t')}
WHERE t.type = 'VendBill' AND v.category = 'Freelance Crew' AND {between(NS_DATE.format(col='t.trandate'), p)}
GROUP BY s.show_no, s.show_nm ORDER BY SUM(t.foreigntotal * t.exchangerate) DESC LIMIT 1"""


@template("x_show_margin", ["cuewright", "netsuite", "adp"], "cross_system", "very_hard")
def x_show_margin(ctx: Ctx):
    r = random.Random(ctx.w.seed + 14)
    cands = sorted(s["number"] for s in ctx.w.shows if s["office"] in US_OFFICES and ctx.inv_by_show.get(s["sid"]) and s["strike"] < AS_OF - timedelta(days=40))
    for no in r.sample(cands, 10):
        s = ctx.show_by_no[no]
        revenue = sum(ctx.usd(t) for t in ctx.inv_by_show[s["sid"]])
        bills = sum(ctx.usd(t) for t in ctx.bills_by_show.get(s["sid"], []) if t["category"] in ("freelance", "freight", "subrental"))
        v = revenue - ctx.employee_labor(s["sid"]) - bills
        yield no, (f"What was the gross margin in US dollars on show {no}? Take what we invoiced for it and subtract employee crew labor "
                   "at base hourly rates, freelance crew bills, freight bills and subrental bills."), money_answer(v), f"""
SELECT ({invoiced_show_sql(no)})
     - COALESCE(({LABOR_SQL.format(no=no)}), 0)
     - COALESCE((SELECT SUM(t.foreigntotal * t.exchangerate) FROM netsuite_transaction t JOIN netsuite_vendor v ON v.id = t.entity
                 WHERE t.type = 'VendBill' AND v.category IN ('Freelance Crew', 'Freight', 'Subrental') AND {SHOW_REF.format(t='t')} = '{no}'), 0)"""


@template("x_rep_contract_value", ["salesforce", "cuewright"], "cross_system", "hard")
def x_rep_contract_value(ctx: Ctx):
    for p in SPANS:
        scores: dict[int, float] = {}
        for s in ctx.w.shows:
            if s["opp"] and s["office"] in US_OFFICES and not s["cancel"] and inside(s["start"], p):
                o = ctx.opps[s["opp"]]
                scores[o["owner"]] = scores.get(o["owner"], 0) + s["contract_cents"] / 100
        top = unique_top(scores)
        if top is None:
            continue
        legal, aliases = ctx.person_aliases(top)
        yield p["key"], (f"Which sales rep's won deals produced the most contract value on US shows that started in {p['label']}? "
                         "Count contract value as the final quote after discount plus approved change orders, and skip cancelled shows."), entity_answer(legal, aliases), f"""
{CONTRACT_CTE}
SELECT u.name FROM cuewright_shows s
JOIN cv ON cv.show_id = s.show_id
JOIN salesforce_opportunity o ON left(o.id, 15) = left(s.crm_opp_ref, 15) AND NOT o.is_deleted
JOIN salesforce_user u ON u.id = o.owner_id
WHERE s.office_cd IN ('CHI', 'NSH', 'DEN') AND s.status_cd <> 'CANC' AND {between(CW_DATE.format(col='s.show_start_dt'), p)}
GROUP BY u.name ORDER BY SUM(cv.contract) DESC LIMIT 1"""


@template("x_days_close_to_start", ["salesforce", "cuewright"], "cross_system", "medium")
def x_days_close_to_start(ctx: Ctx):
    for p in SPANS + QUARTERS[2:]:
        ds = [(s["start"] - ctx.opps[s["opp"]]["close"]).days for s in ctx.w.shows if s["opp"] and not s["cancel"] and inside(s["start"], p)]
        if not ds:
            continue
        yield p["key"], (f"For non-cancelled shows that started in {p['label']}, how many days passed on average between the CRM deal closing "
                         "and the show starting?"), number_answer(sum(ds) / len(ds), unit="days"), f"""
SELECT AVG(date_diff('day', o.close_date, {CW_DATE.format(col='s.show_start_dt')}))
FROM cuewright_shows s JOIN salesforce_opportunity o ON left(o.id, 15) = left(s.crm_opp_ref, 15) AND NOT o.is_deleted
WHERE s.status_cd <> 'CANC' AND {between(CW_DATE.format(col='s.show_start_dt'), p)}"""


@template("x_google_sourced_invoiced", ["salesforce", "cuewright", "netsuite"], "cross_system", "very_hard")
def x_google_sourced_invoiced(ctx: Ctx):
    for p in SPANS + QUARTERS[1:7]:
        v = sum(ctx.usd(t) for s in ctx.w.shows if s["opp"] and ctx.opps[s["opp"]]["lead_source"] == "Google Ads" and inside(s["start"], p)
                for t in ctx.inv_by_show.get(s["sid"], []))
        if v == 0:
            continue
        yield p["key"], (f"How much have we invoiced, in US dollars, for shows that started in {p['label']} whose CRM deal came from "
                         "a Google Ads lead?"), money_answer(v), f"""
SELECT SUM(t.foreigntotal * t.exchangerate)
FROM netsuite_transaction t
JOIN cuewright_shows s ON s.show_no = {SHOW_REF.format(t='t')}
JOIN salesforce_opportunity o ON left(o.id, 15) = left(s.crm_opp_ref, 15) AND NOT o.is_deleted
WHERE t.type = 'CustInvc' AND t.voided = 'F' AND o.lead_source = 'Google Ads' AND {between(CW_DATE.format(col='s.show_start_dt'), p)}"""


@template("crm_contacts_added_quarter", ["salesforce"], "single_table", "easy", test_only=True)
def crm_contacts_added_quarter(ctx: Ctx):
    for p in QUARTERS:
        n = sum(1 for ct in ctx.w.contacts if inside(ct["created"].date(), p))
        yield p["key"], f"How many contacts did we add to the CRM in {p['label']}?", count_answer(n), f"""
SELECT COUNT(*) FROM salesforce_contact WHERE NOT is_deleted AND {between('CAST(substr(created_date, 1, 10) AS DATE)', p)}"""


@template("crm_calls_logged_month", ["salesforce"], "single_table", "easy", test_only=True)
def crm_calls_logged_month(ctx: Ctx):
    tasks = ctx.rows("salesforce", "salesforce_task")
    for p in MONTHS_IN_WINDOW[1::3]:
        n = sum(1 for t in tasks if t["type"] == "Call" and inside(t["activity_date"], p))
        yield p["key"], f"How many calls did our sales team log in the CRM in {p['label']}?", count_answer(n), f"""
SELECT COUNT(*) FROM salesforce_task WHERE type = 'Call' AND {between('activity_date', p)}"""


@template("crm_campaign_members", ["salesforce"], "single_system_join", "medium", test_only=True)
def crm_campaign_members(ctx: Ctx):
    names = {c["id"]: c["name"] for c in ctx.rows("salesforce", "salesforce_campaign")}
    counts: dict[str, int] = {}
    for m in ctx.rows("salesforce", "salesforce_campaign_member"):
        if m["lead_id"]:
            counts[m["campaign_id"]] = counts.get(m["campaign_id"], 0) + 1
    r = random.Random(ctx.w.seed + 15)
    for cid in r.sample(sorted(counts), 8):
        yield cid, f"How many leads are members of the CRM campaign \"{names[cid]}\"?", count_answer(counts[cid]), f"""
SELECT COUNT(*) FROM salesforce_campaign_member m JOIN salesforce_campaign c ON c.id = m.campaign_id
WHERE c.name = '{names[cid]}' AND m.lead_id IS NOT NULL"""


@template("cw_assets_owned", ["cuewright"], "single_system_join", "easy", test_only=True)
def cw_assets_owned(ctx: Ctx):
    items = {i["code"]: i for i in ctx.w.gear_items}
    r = random.Random(ctx.w.seed + 16)
    for code in r.sample(sorted({a["code"] for a in ctx.w.gear_assets}), 8):
        n = sum(1 for a in ctx.w.gear_assets if a["code"] == code and a["retired"] is None)
        desc = items[code]["desc"]
        yield code, f"How many {desc} units do we own, not counting retired ones?", count_answer(n), f"""
SELECT COUNT(*) FROM cuewright_gear_assets a JOIN cuewright_gear_items i ON i.item_cd = a.item_cd
WHERE i.item_desc = '{desc}' AND a.asset_status <> 'RETIRED'"""


@template("cw_union_venues_city", ["cuewright"], "single_table", "hard", test_only=True)
def cw_union_venues_city(ctx: Ctx):
    cities: dict[str, list] = {}
    for v in ctx.w.venues:
        cities.setdefault(v["city"], []).append(v)
    for city in sorted(c for c, vs in cities.items() if len(vs) >= 3):
        n = sum(1 for v in cities[city] if v["union"])
        yield city, f"How many of the venues we've worked with in {city} are union houses?", count_answer(n), f"""
SELECT COUNT(*) FROM cuewright_venues WHERE city = '{city}' AND CAST(json_extract(details, '$.union_house') AS BOOLEAN)"""


@template("cw_top_producer", ["cuewright"], "single_system_join", "medium", test_only=True)
def cw_top_producer(ctx: Ctx):
    for p in SPANS + QUARTERS:
        scores: dict[int, float] = {}
        for s in ctx.w.shows:
            if not s["cancel"] and inside(s["start"], p):
                scores[s["producer"]] = scores.get(s["producer"], 0) + 1
        top = unique_top(scores)
        if top is None:
            continue
        legal, aliases = ctx.person_aliases(top)
        yield p["key"], f"Which producer ran the most shows that started in {p['label']}, not counting cancelled ones?", entity_answer(legal, aliases), f"""
SELECT u.full_nm FROM cuewright_shows s JOIN cuewright_users u ON u.user_id = s.producer_id
WHERE s.status_cd <> 'CANC' AND {between(CW_DATE.format(col='s.show_start_dt'), p)}
GROUP BY u.user_id, u.full_nm ORDER BY COUNT(*) DESC LIMIT 1"""


@template("cw_bill_rate", ["cuewright"], "single_table", "medium", test_only=True)
def cw_bill_rate(ctx: Ctx):
    rates = {(x["rt_cd"], x["eff_dt"]): x["rt_amt"] for x in ctx.rows("cuewright", "cuewright_xrtcd")}
    for code, (_, _, _, title) in CREW_ROLES.items():
        for year in (2025, 2026):
            v = rates[(f"L{code}", f"01/01/{year}")]
            yield f"{code}:{year}", f"What was our standard hourly bill rate for a {title} in {year}?", money_answer(v, tol=0.0), f"""
SELECT rt_amt FROM cuewright_xrtcd WHERE rt_cd = 'L{code}' AND eff_dt = '01/01/{year}'"""


@template("erp_account_total", ["netsuite"], "single_system_join", "hard", test_only=True)
def erp_account_total(ctx: Ctx):
    accounts = {"5100": "Freelance Labor", "5200": "Freight Expense", "5300": "Subrental Expense", "6100": "Contractor Fees", "6200": "General Overhead"}
    for acct, name in accounts.items():
        for key in ("2025", "2026H1"):
            p = span_period(key)
            v = sum(l["amount"] * t["fx"] / 100 for t in ctx.w.transactions if t["type"] == "VendBill" and inside(t["date"], p)
                    for l in t["lines"] if l.get("acct") == acct)
            yield f"{acct}:{key}", f"How much did we book to {name} in {p['label']}, in US dollars?", money_answer(v), f"""
SELECT SUM(l.foreignamount * t.exchangerate)
FROM netsuite_transaction_line l
JOIN netsuite_transaction t ON t.id = l."transaction"
JOIN netsuite_account a ON a.id = l.account
WHERE a.fullname = '{name}' AND l.mainline = 'F' AND t.voided = 'F' AND {between(NS_DATE.format(col='t.trandate'), p)}"""


@template("erp_new_customers", ["netsuite"], "single_table", "medium", test_only=True)
def erp_new_customers(ctx: Ctx):
    for p in SPANS + QUARTERS[2:6]:
        n = sum(1 for cu in ctx.w.customers.values() if inside(cu["created"], p))
        yield p["key"], f"How many new customers did we set up in the ERP in {p['label']}?", count_answer(n), f"""
SELECT COUNT(*) FROM netsuite_customer
WHERE {between("CAST(strptime(split_part(datecreated, ' ', 1), '%m/%d/%Y') AS DATE)", p)}"""


@template("meta_top_adset", ["meta_ads"], "single_system_join", "medium", test_only=True)
def meta_top_adset(ctx: Ctx):
    names = {s["id"]: s["name"] for c in ctx.w.meta_campaigns for s in c["ad_sets"]}
    for p in QUARTERS:
        scores: dict[str, float] = {}
        for m in ctx.w.meta_insights:
            if inside(m["date"], p):
                scores[m["ad_set"]] = scores.get(m["ad_set"], 0) + m["spend_cents"]
        top = unique_top(scores)
        if top is None:
            continue
        yield p["key"], f"Which Meta ad set spent the most in {p['label']}?", entity_answer(names[top], []), f"""
SELECT a.name FROM meta_ads_insights i JOIN meta_ads_ad_sets a ON a.id = i.adset_id
WHERE {between('CAST(i.date_start AS DATE)', p)} GROUP BY a.id, a.name ORDER BY SUM(CAST(i.spend AS DOUBLE)) DESC LIMIT 1"""


@template("adp_commission_quarter", ["adp"], "single_system_join", "medium", test_only=True)
def adp_commission_quarter(ctx: Ctx):
    for p in QUARTERS:
        v = sum(e["amount"] for s in ctx.w.pay_statements if inside(s["pay_date"], p) for e in s["earnings"] if e["code"] == "COM") / 100
        yield p["key"], f"How much sales commission did we pay on paychecks dated in {p['label']}?", money_answer(v), f"""
SELECT SUM(e.amount) FROM adp_pay_statement_earnings e JOIN adp_pay_statements s ON s.pay_statement_id = e.pay_statement_id
WHERE e.earning_code = 'COM' AND {between('s.pay_date', p)}"""


@template("cw_pull_units_show", ["cuewright"], "single_system_join", "easy", test_only=True)
def cw_pull_units_show(ctx: Ctx):
    units: dict[int, int] = {}
    for row in ctx.rows("cuewright", "cuewright_pull_lines"):
        units[row["show_id"]] = units.get(row["show_id"], 0) + row["qty"]
    r = random.Random(ctx.w.seed + 17)
    for sid in r.sample(sorted(units), 8):
        no = ctx.shows[sid - 30000]["number"]
        yield no, f"How many pieces of gear were on the pull list for show {no}?", count_answer(units[sid]), f"""
SELECT SUM(p.qty) FROM cuewright_pull_lines p JOIN cuewright_shows s ON s.show_id = p.show_id WHERE s.show_no = '{no}'"""


def generate(w: World, core: dict, generator_version: str) -> list[dict]:
    ctx = Ctx(w, core)
    r = random.Random(w.seed + 10)
    out = []
    for name, systems, stratum, difficulty, test_only, fn in TEMPLATES:
        instances = [x for x in fn(ctx) if not (x[2]["type"] == "money" and x[2]["value"] == 0)]
        r.shuffle(instances)
        for i, (param, question, answer, sql) in enumerate(instances):
            out.append({
                "template": name, "param": param, "split": "test" if test_only or i % 2 == 0 else "log", "question": question, "answer": answer,
                "systems": systems, "cross_system": stratum == "cross_system", "stratum": stratum, "difficulty": difficulty,
                "reference_sql": sql.strip(), "reference_sql_dialect": "duckdb", "generator_version": generator_version,
            })
    for i, q in enumerate(out, start=1):
        q["id"] = f"cross-{i:04d}"
    return out
