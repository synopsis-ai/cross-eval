"""Simulates two years of Bloom Productions. This history is the truth: each system renders
its own copy of it, and gold answers are computed from it, not from the rendered tables."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .names import (
    COMPANY_HEADS,
    COMPANY_TAILS,
    FIRST_NAMES,
    INDUSTRY_WORDS,
    LAST_NAMES,
    LEGAL_SUFFIXES,
    OFFICE_CITIES,
    VENUE_PATTERNS,
    VENUE_WORDS,
)

COMPANY = "Bloom Productions"
START = date(2024, 7, 1)
AS_OF = date(2026, 6, 30)

OFFICES = {
    "CHI": {"city": "Chicago", "state": "IL", "country": "US", "std": -6, "dst": -5, "weight": 0.40},
    "NSH": {"city": "Nashville", "state": "TN", "country": "US", "std": -6, "dst": -5, "weight": 0.24},
    "DEN": {"city": "Denver", "state": "CO", "country": "US", "std": -7, "dst": -6, "weight": 0.21},
    "TOR": {"city": "Toronto", "state": "ON", "country": "CA", "std": -5, "dst": -4, "weight": 0.15},
}
US_OFFICES = ["CHI", "NSH", "DEN"]

EVENT_TYPES = {
    "CONF": {"label": "Conference", "base": 120_000, "days": (2, 4), "loadin": 2},
    "SKO": {"label": "Sales Kickoff", "base": 70_000, "days": (1, 3), "loadin": 1},
    "LNCH": {"label": "Product Launch", "base": 60_000, "days": (1, 1), "loadin": 1},
    "TSHW": {"label": "Trade Show", "base": 35_000, "days": (3, 4), "loadin": 2},
    "GALA": {"label": "Gala", "base": 55_000, "days": (1, 1), "loadin": 1},
    "TWNH": {"label": "Town Hall", "base": 20_000, "days": (1, 1), "loadin": 1},
    "HYBR": {"label": "Hybrid Event", "base": 45_000, "days": (1, 2), "loadin": 1},
}
SIZE_MULT = {"S": 0.5, "M": 1.0, "L": 1.8, "XL": 3.2}
EVENTS_PER_YEAR = {"S": 0.6, "M": 1.1, "L": 1.9, "XL": 3.2}

DEPTS = {"AUD": "Audio", "VID": "Video", "LTG": "Lighting", "STG": "Staging", "RIG": "Rigging", "LAB": "Labor", "FRT": "Freight"}
DEPT_SHARE = {"AUD": 0.20, "VID": 0.25, "LTG": 0.15, "STG": 0.10, "RIG": 0.05, "LAB": 0.20, "FRT": 0.05}
RENTAL_DEPTS = ["AUD", "VID", "LTG", "STG", "RIG"]

CREW_ROLES = {
    "A1": ("AUD", 48, 70, "Audio Engineer (A1)"),
    "A2": ("AUD", 32, 45, "Audio Assist (A2)"),
    "V1": ("VID", 50, 72, "Video Engineer (V1)"),
    "V2": ("VID", 34, 46, "Video Assist (V2)"),
    "CAM": ("VID", 36, 50, "Camera Operator"),
    "GFX": ("VID", 40, 58, "Graphics Operator"),
    "LD": ("LTG", 50, 75, "Lighting Designer"),
    "L2": ("LTG", 32, 44, "Lighting Tech (L2)"),
    "RIG": ("RIG", 45, 65, "Rigger"),
    "STG": ("STG", 26, 36, "Stagehand"),
}
ROLE_WEIGHTS = {"STG": 0.25, "A1": 0.08, "A2": 0.12, "V1": 0.08, "V2": 0.10, "CAM": 0.10, "GFX": 0.05, "LD": 0.06, "L2": 0.10, "RIG": 0.06}
ALL_DAYS_ROLES = {"A1", "V1", "LD", "GFX", "CAM"}

CHANNELS = {"Google Ads": 0.26, "Paid Social": 0.12, "Referral": 0.19, "Trade Show": 0.11, "Outbound": 0.19, "Website": 0.13}
WIN_PROB_NEW = {"Google Ads": 0.36, "Paid Social": 0.22, "Referral": 0.50, "Trade Show": 0.35, "Outbound": 0.25, "Website": 0.35}
WIN_PROB_REPEAT = 0.72
LOSS_REASONS = ["Price", "Timing", "Went with competitor", "In-house AV", "Event cancelled", "No decision"]

NICKNAMES = {
    "Christopher": "Chris", "Benjamin": "Ben", "Daniel": "Dan", "Jessica": "Jess", "Nathan": "Nate",
    "Samantha": "Sam", "Rebecca": "Becca", "Joseph": "Joe", "James": "Jim", "Alejandro": "Alex",
    "Nicole": "Nikki", "Elijah": "Eli", "Gabriel": "Gabe", "Jeremy": "Jer", "Zachary": "Zach",
    "Isabel": "Izzy", "Valeria": "Val", "Victor": "Vic", "Ricardo": "Rick", "Abigail": "Abby",
}

GOOGLE_CAMPAIGNS = [
    # name, channel type, office focus, start, end, daily budget $, avg cpc $, ctr
    ("Search | Corporate AV | Chicago", "SEARCH", "CHI", date(2024, 7, 1), None, 220, 9.5, 0.055),
    ("Search | Corporate AV | Nashville", "SEARCH", "NSH", date(2024, 7, 1), None, 120, 8.0, 0.05),
    ("Search | Corporate AV | Denver", "SEARCH", "DEN", date(2024, 7, 1), None, 110, 8.5, 0.05),
    ("Search | AV Rental | Toronto", "SEARCH", "TOR", date(2024, 9, 1), None, 90, 7.0, 0.045),
    ("Search | Conference Production | National", "SEARCH", None, date(2024, 7, 1), None, 300, 12.0, 0.04),
    ("Search | Brand", "SEARCH", None, date(2024, 7, 1), None, 40, 2.1, 0.12),
    ("Search | Hybrid & Virtual Events", "SEARCH", None, date(2024, 7, 1), date(2025, 9, 30), 80, 7.5, 0.035),
    ("Search | Trade Show Booth AV", "SEARCH", None, date(2024, 8, 15), None, 100, 6.8, 0.04),
    ("Display | Remarketing", "DISPLAY", None, date(2024, 7, 1), None, 60, 1.2, 0.004),
    ("PMax | Event Production", "PERFORMANCE_MAX", None, date(2025, 2, 1), None, 150, 4.5, 0.012),
    ("Search | Sales Kickoff Production", "SEARCH", None, date(2025, 8, 15), None, 140, 10.0, 0.045),
    ("YouTube | Showreel", "VIDEO", None, date(2025, 4, 1), date(2025, 12, 31), 50, 0.35, 0.009),
]
META_CAMPAIGNS = [
    # name, objective, start, end, daily budget $
    ("BLM | Lead Gen | Sales Kickoffs", "OUTCOME_LEADS", date(2024, 8, 1), None, 140),
    ("BLM | Lead Gen | Galas & Awards Nights", "OUTCOME_LEADS", date(2024, 7, 1), None, 90),
    ("BLM | Lead Gen | Conference Production", "OUTCOME_LEADS", date(2024, 7, 1), None, 160),
    ("BLM | Retargeting | Site Visitors", "OUTCOME_LEADS", date(2024, 7, 1), None, 45),
    ("BLM | Awareness | Showreel Video", "OUTCOME_AWARENESS", date(2024, 10, 1), date(2025, 6, 30), 60),
    ("BLM | Lead Gen | Toronto Corporate Events", "OUTCOME_LEADS", date(2025, 1, 15), None, 55),
    ("BLM | Lead Gen | Product Launches", "OUTCOME_LEADS", date(2025, 3, 1), None, 70),
    ("BLM | Traffic | Case Studies", "OUTCOME_TRAFFIC", date(2025, 9, 1), None, 35),
]
SEASON = {1: 1.10, 2: 0.95, 3: 1.0, 4: 0.95, 5: 0.90, 6: 0.85, 7: 0.85, 8: 1.05, 9: 1.15, 10: 1.15, 11: 1.05, 12: 0.80}

GEAR_ITEMS = {
    "AUD": ["Line array cabinet", "18in subwoofer", "48ch digital mixing console", "Wireless handheld mic kit",
            "Wireless lavalier kit", "Stage monitor wedge", "Audio DSP processor", "Intercom beltpack system",
            "32ch audio snake", "Playback computer"],
    "VID": ["LED wall panel 2.6mm", "20K lumen projector", "16x9 projection screen", "4K video switcher",
            "55in confidence monitor", "Broadcast camera kit", "PTZ camera", "Media server", "Graphics workstation",
            "Streaming encoder"],
    "LTG": ["Moving head spot", "Moving head wash", "LED par", "Ellipsoidal fixture", "Lighting console", "Hazer",
            "Truss lighting kit", "DMX node"],
    "STG": ["Stage deck 4x8", "Stair unit", "Pipe and drape 10ft", "Lectern", "Scenic flat", "Riser skirt"],
    "RIG": ["1-ton chain motor", "10ft box truss", "Rigging hardware kit", "Spanset kit"],
    "LAB": ["Audio crew labor", "Video crew labor", "Lighting crew labor", "Stagehand labor", "Rigging crew labor",
            "Show caller"],
    "FRT": ["Box truck freight", "26ft truck freight", "53ft trailer freight"],
}


def season(d: date) -> float:
    return SEASON[d.month]


def tz_offset(office: str, d: date) -> int:
    o = OFFICES[office]
    return o["dst"] if 4 <= d.month <= 10 else o["std"]


def rand_date(r: random.Random, a: date, b: date) -> date:
    if b <= a:
        return a
    return a + timedelta(days=r.randint(0, (b - a).days))


def days(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def quarter(d: date) -> tuple[int, int]:
    return d.year, (d.month - 1) // 3 + 1


def poisson(r: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 40:
        return max(0, round(r.gauss(lam, math.sqrt(lam))))
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= r.random()
        if p <= limit:
            return k
        k += 1


def utc_ts(d: date, r: random.Random) -> datetime:
    """A business-hours timestamp whose UTC date matches the local date in every office."""
    return datetime(d.year, d.month, d.day, r.randint(13, 22), r.randint(0, 59), r.randint(0, 59))


B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def sf18(id15: str) -> str:
    suffix = ""
    for i in range(3):
        chunk = id15[i * 5:(i + 1) * 5]
        bits = sum(1 << j for j, c in enumerate(chunk) if "A" <= c <= "Z")
        suffix += "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"[bits]
    return id15 + suffix


@dataclass
class Ids:
    r: random.Random
    used: set = field(default_factory=set)
    counters: dict = field(default_factory=dict)

    def sf(self, prefix: str) -> str:
        while True:
            body = "".join(self.r.choice(B62) for _ in range(9))
            id15 = f"{prefix}8c0{body}"
            if id15 not in self.used:
                self.used.add(id15)
                return sf18(id15)

    def seq(self, name: str, start: int = 1) -> int:
        n = self.counters.get(name, start)
        self.counters[name] = n + 1
        return n

    def digits(self, n: int) -> str:
        while True:
            v = str(self.r.randint(10 ** (n - 1), 10 ** n - 1))
            if v not in self.used:
                self.used.add(v)
                return v


@dataclass
class World:
    seed: int
    people: list = field(default_factory=list)
    venues: list = field(default_factory=list)
    gear_items: list = field(default_factory=list)
    gear_assets: list = field(default_factory=list)
    clients: list = field(default_factory=list)
    accounts: list = field(default_factory=list)
    contacts: list = field(default_factory=list)
    google_campaigns: list = field(default_factory=list)
    google_stats: list = field(default_factory=list)
    meta_campaigns: list = field(default_factory=list)
    meta_insights: list = field(default_factory=list)
    sf_campaigns: list = field(default_factory=list)
    leads: list = field(default_factory=list)
    opps: list = field(default_factory=list)
    shows: list = field(default_factory=list)
    crew_calls: list = field(default_factory=list)
    repairs: list = field(default_factory=list)
    fx: dict = field(default_factory=dict)
    customers: dict = field(default_factory=dict)
    vendors: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    pay_statements: list = field(default_factory=list)

    def person(self, pid: int) -> dict:
        return self.people[pid - 1]

    def client(self, cid: int) -> dict:
        return self.clients[cid - 1]


def rate_on(p: dict, d: date) -> int:
    """Hourly rate in cents, or annual salary in dollars, in effect on d."""
    current = p["rates"][0][1]
    for eff, rate in p["rates"]:
        if eff <= d:
            current = rate
    return current


def employed_on(p: dict, d: date) -> bool:
    return p["hire"] <= d and (p["term"] is None or d <= p["term"])


def make_people(w: World, r: random.Random) -> None:
    used = set()

    def name():
        while True:
            first, last = r.choice(FIRST_NAMES), r.choice(LAST_NAMES)
            if (first, last) not in used:
                used.add((first, last))
                return first, last

    def add(office, kind, dept, title, role=None, hire=None, term=None, salary=None):
        first, last = name()
        if hire is None:
            hire = rand_date(r, date(2016, 1, 4), date(2024, 6, 28)) if r.random() < 0.72 else rand_date(r, START, AS_OF - timedelta(days=90))
        if term is None and kind in ("hourly", "freelance") and r.random() < 0.12:
            lo = max(hire + timedelta(days=120), START)
            if lo < AS_OF - timedelta(days=30):
                term = rand_date(r, lo, AS_OF - timedelta(days=30))
        p = {
            "pid": len(w.people) + 1, "first": first, "last": last,
            "preferred": NICKNAMES.get(first) if r.random() < 0.6 else None,
            "office": office, "kind": kind, "dept": dept, "title": title, "role": role,
            "hire": hire, "term": term,
        }
        if kind in ("hourly", "freelance"):
            lo, hi = (CREW_ROLES[role][1], CREW_ROLES[role][2]) if role else (22, 30)
            base = round(r.uniform(lo, hi) * 4) / 4
            if kind == "freelance":
                base = round(base * 1.25 * 4) / 4
            rates = [(min(hire, START), int(round(base * 100)))]
            if kind == "hourly":
                for jan in (date(2025, 1, 1), date(2026, 1, 1)):
                    if employed_on(p, jan) and hire < jan - timedelta(days=60) and r.random() < 0.65:
                        base = round(base * r.uniform(1.03, 1.06) * 4) / 4
                        rates.append((jan, int(round(base * 100))))
            p["rates"] = rates
        else:
            sal = salary or r.randint(60, 120) * 1000
            rates = [(min(hire, START), sal)]
            for jan in (date(2025, 1, 1), date(2026, 1, 1)):
                if employed_on(p, jan) and hire < jan - timedelta(days=60):
                    sal = int(round(sal * r.uniform(1.02, 1.05), -2))
                    rates.append((jan, sal))
            p["rates"] = rates
        w.people.append(p)
        return p

    for office, n in (("CHI", 4), ("NSH", 2), ("DEN", 2)):
        for i in range(n):
            if office == "CHI" and i == 0:
                add(office, "salaried", "Sales", "Account Executive", hire=date(2019, 5, 6), term=date(2025, 2, 14), salary=78000)
                add(office, "salaried", "Sales", "Account Executive", hire=date(2025, 3, 3), salary=82000)
            else:
                add(office, "salaried", "Sales", "Account Executive", hire=rand_date(r, date(2017, 1, 2), date(2024, 1, 8)), salary=r.randint(70, 95) * 1000)
    add("TOR", "contractor", "Sales", "Account Executive", hire=date(2022, 4, 1))
    for office, n in (("CHI", 5), ("NSH", 3), ("DEN", 2)):
        for _ in range(n):
            add(office, "salaried", "Production", "Producer", hire=rand_date(r, date(2016, 3, 1), date(2024, 3, 1)), salary=r.randint(72, 110) * 1000)
    for _ in range(2):
        add("TOR", "contractor", "Production", "Producer", hire=rand_date(r, date(2020, 1, 6), date(2023, 6, 5)))
    for title, sal in (("CEO", 240000), ("CFO", 205000), ("Controller", 128000), ("Staff Accountant", 68000),
                       ("AR Specialist", 58000), ("Marketing Manager", 96000), ("Operations Director", 140000),
                       ("Office Manager", 61000)):
        add("CHI", "salaried", "G&A", title, hire=rand_date(r, date(2014, 1, 6), date(2023, 9, 4)), salary=sal)
    add("NSH", "salaried", "G&A", "Office Manager", hire=rand_date(r, date(2018, 1, 8), date(2023, 1, 9)), salary=57000)
    add("DEN", "salaried", "G&A", "Office Manager", hire=rand_date(r, date(2018, 1, 8), date(2023, 1, 9)), salary=56000)

    roles, weights = zip(*ROLE_WEIGHTS.items())
    for office, n_emp, n_free, n_wh in (("CHI", 55, 20, 4), ("NSH", 30, 12, 2), ("DEN", 25, 10, 2), ("TOR", 0, 25, 0)):
        for _ in range(n_wh):
            add(office, "hourly", "Warehouse", "Warehouse Technician")
        for _ in range(n_emp):
            role = r.choices(roles, weights)[0]
            add(office, "hourly", "Crew", CREW_ROLES[role][3], role=role)
        for _ in range(n_free):
            role = r.choices(roles, weights)[0]
            add(office, "freelance", "Crew", CREW_ROLES[role][3], role=role)


def make_venues(w: World, r: random.Random) -> None:
    used = set()
    counts = {"CHI": 32, "NSH": 24, "DEN": 22, "TOR": 18}
    for office, n in counts.items():
        for _ in range(n):
            while True:
                nm = r.choice(VENUE_PATTERNS).format(a=r.choice(VENUE_WORDS))
                city, region = r.choice(OFFICE_CITIES[office])
                key = (nm, city)
                if key not in used:
                    used.add(key)
                    break
            w.venues.append({
                "vid": len(w.venues) + 1, "name": nm, "city": city, "region": region,
                "country": OFFICES[office]["country"], "office": office,
                "type": "Convention Center" if "Convention" in nm or "Exposition" in nm else ("Hotel" if "Hotel" in nm or "Resort" in nm else "Event Venue"),
                "union": r.random() < 0.35, "dock": r.choice(["A", "B", "C", "D"]) + str(r.randint(1, 6)),
                "power_amps": r.choice([200, 400, 400, 600, 800]), "rig_points": r.randint(0, 60),
            })


def make_gear(w: World, r: random.Random, ids: Ids) -> None:
    for dept, items in GEAR_ITEMS.items():
        for i, desc in enumerate(items, start=1):
            if dept == "LAB":
                rate, repl = r.randint(55, 95) * 10, 0
            elif dept == "FRT":
                rate, repl = r.randint(90, 260) * 10, 0
            else:
                rate = r.randint(4, 120) * 5
                repl = rate * r.randint(18, 35)
            w.gear_items.append({"code": f"{dept}-{i:03d}", "dept": dept, "desc": desc, "rate": rate, "repl": repl})
    for item in w.gear_items:
        if item["dept"] not in RENTAL_DEPTS:
            continue
        for _ in range(r.randint(4, 36)):
            bought = rand_date(r, date(2017, 1, 1), date(2024, 6, 1)) if r.random() < 0.9 else rand_date(r, START, AS_OF - timedelta(days=20))
            w.gear_assets.append({
                "tag": f"BLM-{ids.seq('asset', 1001):05d}", "code": item["code"], "serial": ids.digits(9),
                "bought": bought, "office": r.choices(US_OFFICES + ["TOR"], [0.45, 0.22, 0.2, 0.13])[0],
                "retired": rand_date(r, START, AS_OF) if r.random() < 0.04 else None,
            })


def make_clients(w: World, r: random.Random) -> None:
    used = set()
    offices, ow = zip(*((k, v["weight"]) for k, v in OFFICES.items()))
    channels, cw = zip(*CHANNELS.items())
    for _ in range(430):
        while True:
            stem = r.choice(COMPANY_HEADS) + r.choice(COMPANY_TAILS)
            industry = r.choice(list(INDUSTRY_WORDS))
            base = f"{stem} {r.choice(INDUSTRY_WORDS[industry])}"
            if base not in used and stem not in used:
                used.add(base)
                used.add(stem)
                break
        suffix = r.choice(LEGAL_SUFFIXES)
        legal = f"{base}, {suffix}" if suffix in ("Inc.", "LLC") and r.random() < 0.6 else f"{base} {suffix}"
        roll = r.random()
        if roll < 0.3:
            erp_name = "".join(ch for ch in legal.upper() if ch.isalnum() or ch == " ")
        elif roll < 0.8:
            erp_name = legal.replace(",", "")
        else:
            erp_name = base
        cw_name = stem if r.random() < 0.25 else base
        office = r.choices(offices, ow)[0]
        pre = r.random() < 0.35
        first_touch = rand_date(r, date(2021, 1, 4), date(2024, 5, 31)) if pre else rand_date(r, START, AS_OF - timedelta(days=20))
        size = r.choices(["S", "M", "L", "XL"], [0.35, 0.35, 0.22, 0.08])[0]
        types = list(EVENT_TYPES)
        prefs = r.sample(types, r.choice([1, 1, 2]))
        city, region = r.choice(OFFICE_CITIES[office])
        w.clients.append({
            "cid": len(w.clients) + 1, "stem": stem, "base": base, "legal": legal, "erp_name": erp_name,
            "cw_name": cw_name, "industry": industry, "office": office, "city": city, "region": region,
            "country": OFFICES[office]["country"], "size": size, "preexisting": pre, "first_touch": first_touch,
            "channel": r.choices(channels, cw)[0], "prefs": prefs,
            "pay_days": r.randint(70, 95) if r.random() < 0.1 else r.randint(18, 55),
            "aliases": sorted({base, legal, erp_name, cw_name}),
            "crm_dup": False,
        })


def make_ads(w: World, r: random.Random, ids: Ids) -> None:
    for name, ctype, office, start, end, budget, cpc, ctr in GOOGLE_CAMPAIGNS:
        c = {"id": ids.digits(11), "name": name, "type": ctype, "office": office, "start": start, "end": end,
             "budget_cents": budget * 100, "ad_groups": []}
        for g in range(r.randint(2, 5)):
            c["ad_groups"].append({"id": ids.digits(11), "name": f"{name.split('|')[-1].strip()} - AG{g + 1}"})
        pauses = []
        for _ in range(r.choice([0, 1, 1, 2])):
            p0 = rand_date(r, start, (end or AS_OF) - timedelta(days=25))
            pauses.append((p0, p0 + timedelta(days=r.randint(5, 20))))
        c["pauses"] = pauses
        w.google_campaigns.append(c)
        for d in days(start, min(end or AS_OF, AS_OF)):
            if any(a <= d <= b for a, b in pauses):
                continue
            cost = int(round(budget * 100 * 0.55 * r.uniform(0.72, 1.0) * season(d)))
            this_cpc = cpc * 100 * r.uniform(0.85, 1.15)
            clicks = max(1, round(cost / this_cpc))
            w.google_stats.append({
                "campaign": c["id"], "date": d, "cost_cents": cost, "clicks": clicks,
                "impressions": max(clicks, round(clicks / ctr * r.uniform(0.8, 1.2))),
                "crm_leads": [], "junk": poisson(r, clicks * 0.03),
            })
    for name, objective, start, end, budget in META_CAMPAIGNS:
        c = {"id": "1202" + ids.digits(14), "name": name, "objective": objective, "start": start, "end": end, "ad_sets": []}
        for s in range(2):
            ad_set = {"id": "1202" + ids.digits(14), "name": f"{name.split('|')[-1].strip()} - {['Broad', 'Lookalike 1%'][s]}", "ads": []}
            for a in range(2):
                ad_set["ads"].append({"id": "1202" + ids.digits(14), "name": f"{['Video', 'Carousel'][a]} v{r.randint(1, 4)}"})
            c["ad_sets"].append(ad_set)
        w.meta_campaigns.append(c)
        ads = [(s, a) for s in c["ad_sets"] for a in s["ads"]]
        for d in days(start, min(end or AS_OF, AS_OF)):
            spend = int(round(budget * 100 * r.uniform(0.8, 1.0) * season(d)))
            shares = [r.uniform(0.5, 1.5) for _ in ads]
            tot = sum(shares)
            allocated = 0
            for i, (s, a) in enumerate(ads):
                part = spend - allocated if i == len(ads) - 1 else int(spend * shares[i] / tot)
                allocated += part
                impressions = round(part / 100 / r.uniform(18, 32) * 1000)
                is_leads = objective == "OUTCOME_LEADS"
                platform = poisson(r, part / 100 / 115) if is_leads else 0
                w.meta_insights.append({
                    "campaign": c["id"], "ad_set": s["id"], "ad": a["id"], "date": d, "spend_cents": part,
                    "impressions": impressions, "clicks": round(impressions * r.uniform(0.006, 0.014)),
                    "platform_leads": platform, "crm_leads": [],
                    "junk": sum(1 for _ in range(platform) if r.random() < 0.85),
                })


def pick_campaign_day(r: random.Random, rows: list, d: date, key_cost: str) -> dict | None:
    window = [x for x in rows if abs((x["date"] - d).days) <= 3]
    if not window:
        return None
    return r.choices(window, [max(1, x[key_cost]) for x in window])[0]


def make_crm(w: World, r: random.Random, ids: Ids) -> None:
    reps = [p for p in w.people if p["title"] == "Account Executive"]
    stats_by_date: dict[date, list] = {}
    for s in w.google_stats:
        stats_by_date.setdefault(s["date"], []).append(s)
    meta_by_date: dict[date, list] = {}
    for m in w.meta_insights:
        if m["platform_leads"] > 0:
            meta_by_date.setdefault(m["date"], []).append(m)

    def rep_for(office: str, d: date) -> dict:
        pool = [p for p in reps if p["office"] == office and employed_on(p, d)]
        if not pool:
            pool = [p for p in reps if employed_on(p, d) and p["office"] in US_OFFICES]
        return r.choice(pool)

    def contact_for(c: dict, d: date) -> dict:
        first, last = r.choice(FIRST_NAMES), r.choice(LAST_NAMES)
        ct = {"id": ids.sf("003"), "client": c["cid"], "first": first, "last": last,
              "email": f"{first.lower()}.{last.lower()}@{c['stem'].lower()}.example",
              "title": r.choice(["Event Manager", "Director of Events", "Marketing Director", "VP Marketing",
                                 "Executive Assistant", "Chief of Staff", "Meetings & Events Lead", "HR Director"]),
              "created": utc_ts(d, r)}
        w.contacts.append(ct)
        return ct

    for c in w.clients:
        acct_created = c["first_touch"]
        owner = rep_for(c["office"], max(acct_created, START) if acct_created >= START else START)
        acct = {"id": ids.sf("001"), "client": c["cid"], "name": c["legal"], "owner": owner["pid"],
                "created": utc_ts(acct_created, r), "source": c["channel"], "dup": False}
        w.accounts.append(acct)
        c["account"] = acct["id"]
        c["accounts"] = [acct["id"]]
        for _ in range(r.randint(1, 3)):
            contact_for(c, acct_created)

        if not c["preexisting"]:
            lead = None
            if c["channel"] in ("Google Ads", "Paid Social", "Website") or r.random() < 0.7:
                lead_day = c["first_touch"]
                lead = {"id": ids.sf("00Q"), "client": c["cid"], "created": utc_ts(lead_day, r),
                        "source": c["channel"], "company": c["base"], "first": r.choice(FIRST_NAMES),
                        "last": r.choice(LAST_NAMES), "google": None, "meta": None, "junk": False}
                if c["channel"] == "Google Ads":
                    s = pick_campaign_day(r, stats_by_date.get(lead_day, []), lead_day, "cost_cents") if stats_by_date.get(lead_day) else None
                    if s:
                        lead["google"] = s["campaign"]
                        s["crm_leads"].append(lead["id"])
                    else:
                        lead["source"] = "Website"
                elif c["channel"] == "Paid Social":
                    cands = meta_by_date.get(lead_day, [])
                    if cands:
                        m = r.choice(cands)
                        lead["meta"] = m["campaign"]
                        m["crm_leads"].append(lead["id"])
                        m["platform_leads"] = max(m["platform_leads"], len(m["crm_leads"]))
                    else:
                        lead["source"] = "Website"
                w.leads.append(lead)
            c["source_lead"] = lead
        c["events"] = []

    for c in w.clients:
        opps = []
        lead = c.get("source_lead")
        if not c["preexisting"]:
            created = c["first_touch"] + timedelta(days=r.randint(0, 25))
            if created <= AS_OF:
                event = created + timedelta(days=r.randint(60, 220))
                opps.append({"created": created, "event": event, "new": True})
        t = date(2024, 3, 1) if c["preexisting"] else None
        rate = EVENTS_PER_YEAR[c["size"]] / 365
        while t is not None:
            t = t + timedelta(days=max(20, int(r.expovariate(rate)))) if rate > 0 else None
            if t is None or t > AS_OF + timedelta(days=240):
                break
            created = t - timedelta(days=r.randint(70, 200))
            if created <= AS_OF and created >= date(2024, 3, 1):
                opps.append({"created": created, "event": t, "new": False})
            if r.random() < 0.15 * (rate * 365) / 4:
                break
        c["_pending"] = opps

    for c in w.clients:
        queue = sorted(c.pop("_pending"), key=lambda o: o["created"])
        won_any = c["preexisting"]
        i = 0
        while i < len(queue):
            spec = queue[i]
            i += 1
            o = make_opp(w, r, ids, c, spec, rep_for)
            if o is None:
                continue
            if spec["new"] and o["won"] and not won_any:
                won_any = True
                t = o["event"]
                rate = EVENTS_PER_YEAR[c["size"]] / 365
                while True:
                    t = t + timedelta(days=max(30, int(r.expovariate(rate))))
                    if t > AS_OF + timedelta(days=240) or r.random() < 0.18:
                        break
                    created = t - timedelta(days=r.randint(70, 200))
                    if created <= AS_OF and created > o["created"]:
                        queue.append({"created": created, "event": t, "new": False})
                queue[i:] = sorted(queue[i:], key=lambda x: x["created"])

    dup_candidates = [c for c in w.clients if sum(1 for o in w.opps if o["client"] == c["cid"]) >= 2]
    for c in r.sample(dup_candidates, max(1, len(dup_candidates) // 25)):
        c["crm_dup"] = True
        later = [o for o in w.opps if o["client"] == c["cid"]][1:]
        made = min(o["created"] for o in later) - timedelta(days=r.randint(1, 20))
        dup = {"id": ids.sf("001"), "client": c["cid"], "name": c["base"], "owner": rep_for(c["office"], max(made, START))["pid"],
               "created": utc_ts(max(made, START), r), "source": "Outbound", "dup": True}
        w.accounts.append(dup)
        c["accounts"].append(dup["id"])
        for o in later:
            if r.random() < 0.5:
                o["account"] = dup["id"]

    for c in w.clients:
        lead = c.get("source_lead")
        first = next((o for o in w.opps if o["client"] == c["cid"] and o["new"]), None)
        if lead and first:
            lead["converted"] = first["created"]
            lead["converted_opp"] = first["id"]
            lead["converted_account"] = c["account"]
            lead["converted_contact"] = next(ct["id"] for ct in w.contacts if ct["client"] == c["cid"])
            first["lead"] = lead["id"]
            first["google"] = lead["google"]
            first["meta"] = lead["meta"]

    junk_companies = [r.choice(COMPANY_HEADS) + r.choice(COMPANY_TAILS) + " " + r.choice(["Events", "Studio", "Group", "Consulting", "Productions", "Photography"]) for _ in range(300)]

    def junk_lead(d: date, source: str, google=None, meta=None):
        w.leads.append({"id": ids.sf("00Q"), "client": None, "created": utc_ts(d, r), "source": source,
                        "company": r.choice(junk_companies + ["Self", "Student", "N/A"]),
                        "first": r.choice(FIRST_NAMES), "last": r.choice(LAST_NAMES),
                        "google": google, "meta": meta, "junk": True})
        return w.leads[-1]

    for s in w.google_stats:
        for _ in range(s["junk"]):
            s["crm_leads"].append(junk_lead(s["date"], "Google Ads", google=s["campaign"])["id"])
        s["conversions"] = len(s["crm_leads"]) + poisson(r, len(s["crm_leads"]) * 0.2)
    for m in w.meta_insights:
        for _ in range(m["junk"]):
            m["crm_leads"].append(junk_lead(m["date"], "Paid Social", meta=m["campaign"])["id"])
        m["platform_leads"] = max(m["platform_leads"], len(m["crm_leads"]))
    for d in days(START, AS_OF):
        for _ in range(poisson(r, 1.4)):
            junk_lead(d, "Website")
        if r.random() < 0.08:
            for _ in range(r.randint(3, 25)):
                junk_lead(d, "Trade Show")
        for _ in range(poisson(r, 0.5)):
            junk_lead(d, r.choice(["Referral", "Outbound"]))
    w.leads.sort(key=lambda x: x["created"])

    for c in w.google_campaigns:
        w.sf_campaigns.append({"id": ids.sf("701"), "name": c["name"], "platform": "Google Ads", "platform_id": c["id"],
                               "start": c["start"], "end": c["end"], "type": "Paid Search" if "Search" in c["name"] else "Advertisement"})
    for c in w.meta_campaigns:
        w.sf_campaigns.append({"id": ids.sf("701"), "name": c["name"], "platform": "Meta", "platform_id": c["id"],
                               "start": c["start"], "end": c["end"], "type": "Paid Social"})
    for nm, d0 in (("Trade Show Booth - Fall 2024", date(2024, 10, 8)), ("Webinar - Hybrid Event Playbook", date(2025, 2, 20)),
                   ("Trade Show Booth - Spring 2025", date(2025, 4, 15)), ("Customer Appreciation Night 2025", date(2025, 6, 12)),
                   ("Trade Show Booth - Fall 2025", date(2025, 10, 7)), ("Trade Show Booth - Spring 2026", date(2026, 4, 14))):
        w.sf_campaigns.append({"id": ids.sf("701"), "name": nm, "platform": None, "platform_id": None,
                               "start": d0, "end": d0 + timedelta(days=2), "type": "Trade Show" if "Trade" in nm else "Event"})


def make_opp(w: World, r: random.Random, ids: Ids, c: dict, spec: dict, rep_for) -> dict | None:
    created = spec["created"]
    event = spec["event"]
    if created > AS_OF:
        return None
    close = created + timedelta(days=r.randint(15, 80))
    if close > event - timedelta(days=14):
        close = max(created + timedelta(days=5), event - timedelta(days=14))
    etype = r.choice(c["prefs"])
    amount = EVENT_TYPES[etype]["base"] * SIZE_MULT[c["size"]] * math.exp(r.gauss(0, 0.35))
    amount = int(max(5000, round(amount / 500) * 500))
    p_win = WIN_PROB_NEW[c["channel"]] if spec["new"] else WIN_PROB_REPEAT
    won = r.random() < p_win
    owner = rep_for(c["office"], max(created, START))
    o = {
        "id": ids.sf("006"), "client": c["cid"], "account": c["account"], "owner": owner["pid"], "created": created,
        "created_ts": utc_ts(created, r), "close": close, "event": event, "etype": etype, "amount": amount,
        "new": spec["new"], "lead_source": c["channel"] if spec["new"] else "Repeat Client",
        "won": won, "closed": close <= AS_OF, "loss_reason": None if won else r.choice(LOSS_REASONS),
        "lead": None, "google": None, "meta": None, "show": None,
    }
    if close > AS_OF:
        o["won"] = False
        frac = (AS_OF - created).days / max(1, (close - created).days)
        o["stage"] = "Prospecting" if frac < 0.25 else "Qualification" if frac < 0.5 else "Proposal" if frac < 0.8 else "Negotiation"
    else:
        o["stage"] = "Closed Won" if won else "Closed Lost"
    if not o["won"]:
        o["loss_reason"] = o["loss_reason"] if o["closed"] else None
    w.opps.append(o)
    return o


def make_shows(w: World, r: random.Random, ids: Ids) -> None:
    producers = [p for p in w.people if p["title"] == "Producer"]
    venues_by_office: dict[str, list] = {}
    for v in w.venues:
        venues_by_office.setdefault(v["office"], []).append(v)
    specs = []
    for o in w.opps:
        if o["won"]:
            specs.append({"opp": o, "client": o["client"], "booked": o["close"], "start": o["event"], "etype": o["etype"], "amount": o["amount"]})
    for c in w.clients:
        if c["preexisting"] and r.random() < 0.18:
            start = rand_date(r, START + timedelta(days=30), AS_OF + timedelta(days=90))
            booked = start - timedelta(days=r.randint(30, 120))
            if booked <= AS_OF:
                etype = r.choice(c["prefs"])
                amount = int(round(EVENT_TYPES[etype]["base"] * SIZE_MULT[c["size"]] * 0.6 * math.exp(r.gauss(0, 0.3)) / 500) * 500)
                specs.append({"opp": None, "client": c["cid"], "booked": booked, "start": start, "etype": etype, "amount": amount})
    specs.sort(key=lambda s: (s["booked"], s["start"]))
    seq_by_year: dict[int, int] = {}
    for s in specs:
        c = w.client(s["client"])
        office = c["office"]
        et = EVENT_TYPES[s["etype"]]
        n_days = r.randint(*et["days"])
        start = s["start"]
        end = start + timedelta(days=n_days - 1)
        load_in = start - timedelta(days=et["loadin"])
        if load_in < START:
            continue
        yr = s["booked"].year % 100
        seq_by_year[yr] = seq_by_year.get(yr, 0) + 1
        strike = end if r.random() < 0.7 else end + timedelta(days=1)
        pool = [p for p in producers if p["office"] == office and employed_on(p, s["booked"])] or producers
        venue = r.choice(venues_by_office[office])
        currency = "CAD" if office == "TOR" else "USD"
        cancel = None
        if r.random() < 0.045 and start > s["booked"] + timedelta(days=12):
            cd = rand_date(r, s["booked"] + timedelta(days=7), start - timedelta(days=3))
            if cd <= AS_OF:
                cancel = cd
        sh = {
            "sid": len(w.shows) + 1, "number": f"{yr:02d}-{seq_by_year[yr]:04d}", "client": c["cid"], "opp": s["opp"]["id"] if s["opp"] else None,
            "office": office, "venue": venue["vid"], "producer": r.choice(pool)["pid"], "etype": s["etype"],
            "name": f"{c['cw_name']} {et['label']} {start.year}", "booked": s["booked"], "load_in": load_in,
            "start": start, "end": end, "strike": strike, "currency": currency, "cancel": cancel,
            "po": f"PO-{r.randint(100000, 999999)}" if r.random() < 0.55 else None, "rush": (start - s["booked"]).days < 30,
        }
        if s["opp"]:
            s["opp"]["show"] = sh["sid"]
        local_amount = s["amount"] * (1.36 if currency == "CAD" else 1.0)
        target = int(local_amount * r.uniform(0.95, 1.12) * 100)
        build_quote(w, r, sh, target)
        w.shows.append(sh)
    for sh in w.shows:
        sh["status"] = show_status(sh)


def build_quote(w: World, r: random.Random, sh: dict, target_cents: int) -> None:
    disc = r.choice([0, 0, 0, 5, 5, 7.5, 10])
    gross_target = target_cents / (1 - disc / 100)
    items_by_dept: dict[str, list] = {}
    for it in w.gear_items:
        items_by_dept.setdefault(it["dept"], []).append(it)
    n_show_days = (sh["end"] - sh["start"]).days + 1
    lines = []
    for dept, share in DEPT_SHARE.items():
        alloc = gross_target * share * r.uniform(0.8, 1.2)
        chosen = r.sample(items_by_dept[dept], min(len(items_by_dept[dept]), r.randint(1, 3)))
        parts = [r.uniform(0.5, 1.5) for _ in chosen]
        tot = sum(parts)
        for it, part in zip(chosen, parts):
            amt = alloc * part / tot
            qty = 1 if dept == "FRT" else r.randint(1, 16)
            d = 1 if dept == "FRT" else n_show_days
            unit = max(100, int(round(amt / (qty * d))))
            lines.append({"code": it["code"], "dept": dept, "desc": it["desc"], "qty": qty, "days": d, "unit_cents": unit, "ext_cents": unit * qty * d})
    gross = sum(l["ext_cents"] for l in lines)
    discount = int(round(gross * disc / 100))
    sh["quote"] = {"lines": lines, "disc": disc, "gross": gross, "discount": discount, "net": gross - discount}
    versions = []
    for v in range(r.choice([0, 0, 1, 1, 2])):
        scale = r.uniform(0.85, 1.1)
        versions.append([{**l, "unit_cents": int(l["unit_cents"] * scale), "ext_cents": int(l["unit_cents"] * scale) * l["qty"] * l["days"]} for l in lines])
    sh["quote_drafts"] = versions
    cos = []
    if sh["cancel"] is None:
        for _ in range(r.choices([0, 1, 2, 3], [0.55, 0.25, 0.13, 0.07])[0]):
            approved = rand_date(r, sh["booked"] + timedelta(days=3), sh["strike"])
            if approved > AS_OF:
                continue
            if r.random() < 0.8:
                amt = int(round(sh["quote"]["net"] * r.uniform(0.02, 0.15) / 2500)) * 2500
                desc = r.choice(["Add second confidence monitor", "Upgrade LED wall size", "Add breakout room AV", "Additional camera and operator",
                                 "Extend show day", "Add livestream package", "Additional wireless mics", "Add uplighting package"])
            else:
                amt = -int(round(sh["quote"]["net"] * r.uniform(0.01, 0.06) / 2500)) * 2500
                desc = r.choice(["Remove breakout room", "Client supplied lectern", "Reduce LED wall", "Drop second camera"])
            cos.append({"amount_cents": amt, "desc": desc, "approved": approved, "void": r.random() < 0.06})
    sh["change_orders"] = sorted(cos, key=lambda x: x["approved"])
    sh["contract_cents"] = sh["quote"]["net"] + sum(c["amount_cents"] for c in cos if not c["void"])


def show_status(sh: dict) -> str:
    if sh["cancel"]:
        return "CANC"
    if sh["start"] > AS_OF and sh["load_in"] > AS_OF:
        return "TENT" if (sh["start"] - AS_OF).days > 150 else "CONF"
    if sh["load_in"] <= AS_OF <= sh["strike"]:
        return "LIVE"
    return "WRAP"


def make_crew(w: World, r: random.Random) -> None:
    crew = [p for p in w.people if p["kind"] in ("hourly", "freelance") and p["dept"] == "Crew"]
    by_office: dict[str, list] = {}
    for p in crew:
        by_office.setdefault(p["office"], []).append(p)
    busy: set = set()
    call_id = 0
    for sh in sorted(w.shows, key=lambda s: (s["load_in"], s["sid"])):
        if sh["cancel"] or sh["load_in"] > AS_OF:
            continue
        usd = sh["contract_cents"] / 100 / (1.36 if sh["currency"] == "CAD" else 1)
        n = max(4, min(36, round(usd / 9000)))
        work_days = list(days(sh["load_in"], sh["strike"]))
        pool = [p for p in by_office[sh["office"]] if employed_on(p, sh["load_in"])]
        if sh["office"] in US_OFFICES and n > 14:
            pool += [p for o in US_OFFICES if o != sh["office"] for p in by_office[o] if employed_on(p, sh["load_in"]) and r.random() < 0.15]
        r.shuffle(pool)
        team = []
        for p in pool:
            if len(team) >= n:
                break
            if all((p["pid"], d) not in busy for d in work_days):
                team.append(p)
        for p in team:
            for d in work_days:
                is_load = d < sh["start"]
                is_strike = d > sh["end"] or (d == sh["end"] and sh["strike"] == sh["end"] and r.random() < 0.0)
                if p["role"] not in ALL_DAYS_ROLES and not is_load and not is_strike and d != sh["end"] and r.random() < 0.5:
                    continue
                if d > AS_OF or not employed_on(p, d):
                    continue
                if is_load:
                    hours, start_h = round(r.uniform(9, 13.5) * 4) / 4, r.choice([6, 6.5, 7, 7.5, 8])
                elif is_strike:
                    hours, start_h = round(r.uniform(5, 9) * 4) / 4, r.choice([13, 14, 15, 16])
                else:
                    hours, start_h = round(r.uniform(7, 12) * 4) / 4, r.choice([6.5, 7, 7.5, 8, 8.5, 9])
                meal = 0.5 if hours > 6 else 0
                busy.add((p["pid"], d))
                call_id += 1
                off = tz_offset(sh["office"], d)
                call_dt = datetime(d.year, d.month, d.day) + timedelta(hours=start_h)
                wrap_dt = call_dt + timedelta(hours=hours + meal)
                w.crew_calls.append({
                    "id": call_id, "show": sh["sid"], "pid": p["pid"], "role": p["role"], "date": d,
                    "hours": hours, "call": call_dt, "wrap": wrap_dt, "offset": off, "travel": p["office"] != sh["office"],
                })


def make_repairs(w: World, r: random.Random) -> None:
    assets_by_code: dict[str, list] = {}
    for a in w.gear_assets:
        assets_by_code.setdefault(a["code"], []).append(a)
    tid = 0
    for sh in w.shows:
        if sh["cancel"] or sh["strike"] > AS_OF - timedelta(days=2) or r.random() > 0.2:
            continue
        rental = [l for l in sh["quote"]["lines"] if l["dept"] in RENTAL_DEPTS]
        for _ in range(r.randint(1, 2)):
            line = r.choice(rental)
            asset = r.choice(assets_by_code[line["code"]])
            opened = sh["strike"] + timedelta(days=r.randint(1, 5))
            closed = opened + timedelta(days=r.randint(3, 40)) if r.random() < 0.85 else None
            if closed and closed > AS_OF:
                closed = None
            tid += 1
            outcome = "CLOSED" if closed else r.choice(["OPEN", "IN_REPAIR", "IN_REPAIR"])
            if closed and r.random() < 0.08:
                outcome = "SCRAPPED"
            w.repairs.append({"id": tid, "tag": asset["tag"], "show": sh["sid"], "opened": opened, "closed": closed,
                              "status": outcome, "cost_cents": r.randint(40, 1800) * 100 if closed else None,
                              "issue": r.choice(["Dead pixel cluster", "No power", "Cracked housing", "Intermittent signal",
                                                 "Fan failure", "Bent truss chord", "RF dropouts", "Firmware fault", "Damaged connector"])})


def make_fx(w: World, r: random.Random) -> None:
    rate = 0.735
    m = date(2023, 7, 1)
    while m <= AS_OF:
        rate = min(0.76, max(0.70, rate + r.gauss(0, 0.006)))
        w.fx[(m.year, m.month)] = round(rate, 6)
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)


def fx_on(w: World, currency: str, d: date) -> float:
    return 1.0 if currency == "USD" else w.fx[(d.year, d.month)]


def make_finance(w: World, r: random.Random, ids: Ids) -> None:
    """NetSuite: deposits, invoices, deposit applications, payments, vendor bills and payroll journals."""
    tx = w.transactions

    def customer(c: dict, d: date) -> dict:
        if c["cid"] not in w.customers:
            w.customers[c["cid"]] = {"id": 1000 + len(w.customers) + 1, "client": c["cid"], "created": d,
                                     "sf_link": r.random() < 0.7, "sf_15": r.random() < 0.3,
                                     "currency": "CAD" if c["office"] == "TOR" else "USD"}
        return w.customers[c["cid"]]

    def add(t: dict) -> dict:
        t.setdefault("lines", [])
        t.setdefault("void", False)
        t.setdefault("links", [])
        tx.append(t)
        return t

    for sh in w.shows:
        c = w.client(sh["client"])
        if sh["cancel"]:
            fee = int(round(sh["quote"]["net"] * 0.25))
            d = sh["cancel"] + timedelta(days=3)
            if d <= AS_OF:
                cust = customer(c, d)
                inv = add({"type": "CustInvc", "date": d, "cust": cust["id"], "client": c["cid"], "show": sh["sid"], "currency": sh["currency"],
                           "total": fee, "lines": [{"kind": "cancel", "dept": None, "amount": fee}], "memo": None})
                pay_invoice(w, r, inv, c, deposit=None, add=add)
            continue
        dep = None
        dep_date = sh["booked"] + timedelta(days=r.randint(3, 10))
        if dep_date <= AS_OF and dep_date < sh["start"]:
            cust = customer(c, dep_date)
            dep = add({"type": "CustDep", "date": dep_date, "cust": cust["id"], "client": c["cid"], "show": sh["sid"],
                       "currency": sh["currency"], "total": int(round(sh["quote"]["net"] * 0.5)), "memo": None})
        inv_date = sh["strike"] + timedelta(days=r.randint(2, 10))
        if inv_date > AS_OF:
            continue
        cust = customer(c, inv_date)
        lines = []
        dept_gross: dict[str, int] = {}
        for l in sh["quote"]["lines"]:
            dept_gross[l["dept"]] = dept_gross.get(l["dept"], 0) + l["ext_cents"]
        remaining = sh["quote"]["net"]
        depts = list(dept_gross)
        for i, dept in enumerate(depts):
            amt = remaining if i == len(depts) - 1 else int(round(dept_gross[dept] * (1 - sh["quote"]["disc"] / 100)))
            remaining -= amt
            lines.append({"kind": "dept", "dept": dept, "amount": amt})
        for co in sh["change_orders"]:
            if not co["void"]:
                lines.append({"kind": "co", "dept": None, "amount": co["amount_cents"], "desc": co["desc"]})
        inv = add({"type": "CustInvc", "date": inv_date, "cust": cust["id"], "client": c["cid"], "show": sh["sid"],
                   "currency": sh["currency"], "total": sum(l["amount"] for l in lines), "lines": lines, "memo": None})
        assert inv["total"] == sh["contract_cents"]
        if r.random() < 0.012:
            add({"type": "CustInvc", "date": inv_date, "cust": cust["id"], "client": c["cid"], "show": sh["sid"],
                 "currency": sh["currency"], "total": inv["total"], "lines": [dict(l) for l in lines], "memo": "Duplicate - voided", "void": True,
                 "paid_in_full": False, "remaining": inv["total"]})
        pay_invoice(w, r, inv, c, deposit=dep, add=add)
    for sh in w.shows:
        inv = next((t for t in tx if t["type"] == "CustInvc" and t["show"] == sh["sid"] and not t["void"]), None)
        if sh["status"] == "WRAP" and inv is not None:
            sh["status"] = "CLSD" if inv["date"] <= AS_OF - timedelta(days=5) else "WRAP"

    make_bills(w, r, ids, add)
    tx.sort(key=lambda t: (t["date"], {"CustDep": 0, "CustInvc": 1, "DepAppl": 2, "CustPymt": 3, "VendBill": 4, "Journal": 5}[t["type"]]))
    seqs = {}
    prefixes = {"CustInvc": ("INV", 10001), "CustDep": ("DEP", 5001), "DepAppl": ("DA", 3001), "CustPymt": ("PYMT", 20001), "Journal": ("JE", 701)}
    for i, t in enumerate(tx, start=1):
        t["id"] = 100000 + i * 3 + r.randint(0, 2)
        if t["type"] in prefixes:
            p, s0 = prefixes[t["type"]]
            seqs[t["type"]] = seqs.get(t["type"], s0 - 1) + 1
            t["tranid"] = f"{p}{seqs[t['type']]}"
        t["fx"] = fx_on(w, t["currency"], t["date"])


def pay_invoice(w: World, r: random.Random, inv: dict, c: dict, deposit: dict | None, add) -> None:
    applied = 0
    if deposit is not None:
        applied = min(deposit["total"], inv["total"])
        add({"type": "DepAppl", "date": inv["date"], "cust": inv["cust"], "client": inv["client"], "show": inv["show"], "currency": inv["currency"],
             "total": applied, "memo": None, "applies": [(deposit, applied), (inv, applied)]})
    due = inv["total"] - applied
    paid = []
    if due > 0:
        days_to_pay = max(3, int(r.gauss(c["pay_days"], 9)))
        final = inv["date"] + timedelta(days=days_to_pay)
        if r.random() < 0.07 and due > 200000:
            part = int(due * r.uniform(0.3, 0.6))
            mid = inv["date"] + timedelta(days=max(2, days_to_pay // 2))
            paid.append((mid, part))
            paid.append((final, due - part))
        else:
            paid.append((final, due))
    remaining = due
    last_pay = None
    for d, amt in paid:
        if d > AS_OF:
            continue
        p = add({"type": "CustPymt", "date": d, "cust": inv["cust"], "client": inv["client"], "show": inv["show"], "currency": inv["currency"],
                 "total": amt, "memo": None, "applies": [(inv, amt)]})
        remaining -= amt
        last_pay = d
    inv["remaining"] = remaining
    inv["paid_in_full"] = remaining == 0
    inv["paid_date"] = last_pay if remaining == 0 else None


def make_bills(w: World, r: random.Random, ids: Ids, add) -> None:
    def vendor(kind: str, name: str, pid: int | None = None, currency: str = "USD") -> dict:
        v = {"id": 5000 + len(w.vendors) + 1, "kind": kind, "name": name, "pid": pid, "currency": currency}
        w.vendors.append(v)
        return v

    by_pid = {}
    for p in w.people:
        if p["kind"] in ("freelance", "contractor"):
            style = r.random()
            nm = f"{p['first']} {p['last']}" if style < 0.6 else (f"{p['last']}, {p['first']}" if style < 0.85 else f"{p['first']} {p['last']} Productions LLC")
            by_pid[p["pid"]] = vendor("freelance" if p["kind"] == "freelance" else "contractor", nm, p["pid"], "CAD" if p["office"] == "TOR" else "USD")
    carriers = [vendor("freight", n) for n in ("Redline Freight Lines", "Copperhead Logistics", "Northstar Expedited", "Bluegate Carriers", "Maple Route Transport")]
    subrent = [vendor("subrental", n) for n in ("Stagecraft Rentals Midwest", "Pixelyard Video Supply", "Rivermark Audio Rental", "Tallgrass Lighting Co.")]
    makers = [vendor("equipment", n) for n in ("Voltaire Pro Audio", "Lumenra Display Systems", "Gridline Rigging Supply", "Starfield Lighting Mfg")]
    misc = [vendor("other", n) for n in ("Citywide Parking Services", "Brightway Office Supply", "Harbor Insurance Brokers", "Keystone Facilities")]

    calls_by_show: dict[int, list] = {}
    for cc in w.crew_calls:
        calls_by_show.setdefault(cc["show"], []).append(cc)
    for sh in w.shows:
        if sh["cancel"] or sh["load_in"] > AS_OF:
            continue
        hours_by_pid: dict[int, float] = {}
        for cc in calls_by_show.get(sh["sid"], []):
            p = w.person(cc["pid"])
            if p["kind"] == "freelance":
                hours_by_pid[cc["pid"]] = hours_by_pid.get(cc["pid"], 0) + cc["hours"]
        for pid, hrs in sorted(hours_by_pid.items()):
            d = sh["strike"] + timedelta(days=r.randint(5, 25))
            if d > AS_OF:
                continue
            p = w.person(pid)
            amt = int(round(hrs * rate_on(p, sh["start"])))
            v = by_pid[pid]
            add({"type": "VendBill", "date": d, "vendor": v["id"], "show": sh["sid"], "currency": v["currency"], "total": amt,
                 "category": "freelance", "tranid": f"{p['last'][:3].upper()}-{d:%y%m}-{r.randint(10, 99)}",
                 "memo": None, "lines": [{"kind": "expense", "acct": "5100", "dept": "LAB", "amount": amt}]})
        frt = sum(l["ext_cents"] for l in sh["quote"]["lines"] if l["dept"] == "FRT")
        if frt:
            d = sh["load_in"] - timedelta(days=r.randint(0, 3))
            if d <= AS_OF:
                amt = int(frt * r.uniform(0.4, 0.7))
                v = r.choice(carriers)
                add({"type": "VendBill", "date": d, "vendor": v["id"], "show": sh["sid"], "currency": sh["currency"], "total": amt,
                     "category": "freight", "tranid": f"PRO{r.randint(1000000, 9999999)}", "memo": None,
                     "lines": [{"kind": "expense", "acct": "5200", "dept": "FRT", "amount": amt}]})
        if r.random() < 0.3:
            d = sh["load_in"] - timedelta(days=r.randint(0, 5))
            if d <= AS_OF:
                amt = int(sh["contract_cents"] * r.uniform(0.03, 0.10))
                v = r.choice(subrent)
                dept = r.choice(RENTAL_DEPTS)
                add({"type": "VendBill", "date": d, "vendor": v["id"], "show": sh["sid"], "currency": sh["currency"], "total": amt,
                     "category": "subrental", "tranid": f"SR-{r.randint(10000, 99999)}", "memo": None,
                     "lines": [{"kind": "expense", "acct": "5300", "dept": dept, "amount": amt}]})
    purchases: dict[tuple, list] = {}
    for a in w.gear_assets:
        if a["bought"] >= START:
            purchases.setdefault((a["code"], a["bought"]), []).append(a)
    items = {it["code"]: it for it in w.gear_items}
    for (code, d), assets in sorted(purchases.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        amt = items[code]["repl"] * 100 * len(assets)
        add({"type": "VendBill", "date": d, "vendor": r.choice(makers)["id"], "show": None, "currency": "USD", "total": amt,
             "category": "capex", "tranid": f"EQ-{r.randint(100000, 999999)}", "memo": f"{len(assets)} x {items[code]['desc']}",
             "lines": [{"kind": "expense", "acct": "1500", "dept": items[code]["dept"], "amount": amt}]})
    for p in w.people:
        if p["kind"] != "contractor":
            continue
        m = START
        while m <= AS_OF:
            if employed_on(p, m):
                amt = (850000 if p["title"] == "Producer" else 780000) + r.randint(-20, 20) * 100
                v = by_pid[p["pid"]]
                add({"type": "VendBill", "date": m, "vendor": v["id"], "show": None, "currency": "CAD", "total": amt,
                     "category": "contractor", "tranid": f"{p['last'][:3].upper()}{m:%y%m}", "memo": f"Retainer {m:%b %Y}",
                     "lines": [{"kind": "expense", "acct": "6100", "dept": None, "amount": amt}]})
            m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for m_start in (date(y, mo, 1) for y in (2024, 2025, 2026) for mo in range(1, 13)):
        if START <= m_start <= AS_OF:
            for v in misc:
                if r.random() < 0.7:
                    amt = r.randint(150, 4000) * 100
                    add({"type": "VendBill", "date": m_start + timedelta(days=r.randint(0, 25)), "vendor": v["id"], "show": None, "currency": "USD",
                         "total": amt, "category": "overhead", "tranid": f"{r.randint(100000, 999999)}", "memo": None,
                         "lines": [{"kind": "expense", "acct": "6200", "dept": None, "amount": amt}]})


def make_payroll(w: World, r: random.Random, ids: Ids) -> None:
    """ADP: weekly pay for hourly US employees, biweekly for salaried. Covers US employees only;
    Toronto people are contractors and freelancers paid through NetSuite."""
    hours: dict[tuple[int, date], float] = {}
    for cc in w.crew_calls:
        p = w.person(cc["pid"])
        if p["kind"] == "hourly":
            wk_end = cc["date"] + timedelta(days=(5 - cc["date"].weekday()) % 7)
            hours[(p["pid"], wk_end)] = hours.get((p["pid"], wk_end), 0) + cc["hours"]
    first_sat = START + timedelta(days=(5 - START.weekday()) % 7)
    stmt = 0
    for p in w.people:
        if p["kind"] == "hourly":
            sat = first_sat
            while True:
                pay_date = sat + timedelta(days=6)
                if pay_date > AS_OF:
                    break
                wk_start = sat - timedelta(days=6)
                if employed_on(p, sat) or employed_on(p, wk_start):
                    show_h = hours.get((p["pid"], sat), 0)
                    shop = 40 * r.uniform(0.9, 1.0) if p["dept"] == "Warehouse" else (r.uniform(0, 10) if r.random() < 0.6 else 0)
                    shop = round(shop * 4) / 4
                    total = show_h + shop
                    if total > 0:
                        rate = rate_on(p, sat)
                        reg = min(40.0, total)
                        ot = max(0.0, total - 40.0)
                        earnings = [{"code": "REG", "hours": reg, "rate_cents": rate, "amount": int(round(reg * rate))}]
                        if ot:
                            earnings.append({"code": "OT", "hours": ot, "rate_cents": int(round(rate * 1.5)), "amount": int(round(ot * rate * 1.5))})
                        stmt += 1
                        w.pay_statements.append({"id": stmt, "pid": p["pid"], "pay_date": pay_date, "start": wk_start, "end": sat,
                                                 "earnings": earnings, "show_hours": show_h, "shop_hours": shop})
                sat += timedelta(days=7)
        elif p["kind"] == "salaried":
            pay_date = START + timedelta(days=(4 - START.weekday()) % 7)
            paid_quarters = set()
            while pay_date <= AS_OF:
                end = pay_date - timedelta(days=6)
                start = end - timedelta(days=13)
                if employed_on(p, end):
                    sal = rate_on(p, end)
                    earnings = [{"code": "SAL", "hours": 80.0, "rate_cents": None, "amount": int(round(sal * 100 / 26))}]
                    if p["title"] == "Account Executive" and pay_date.month in (1, 4, 7, 10) and (pay_date.year, pay_date.month) not in paid_quarters:
                        paid_quarters.add((pay_date.year, pay_date.month))
                        q_end = date(pay_date.year, pay_date.month, 1) - timedelta(days=1)
                        q_start = date(q_end.year, q_end.month - 2, 1)
                        won = sum(o["amount"] for o in w.opps if o["owner"] == p["pid"] and o["won"] and q_start <= o["close"] <= q_end)
                        if won:
                            earnings.append({"code": "COM", "hours": 0.0, "rate_cents": None, "amount": int(round(won * 100 * 0.015))})
                    stmt += 1
                    w.pay_statements.append({"id": stmt, "pid": p["pid"], "pay_date": pay_date, "start": start, "end": end,
                                             "earnings": earnings, "show_hours": 0, "shop_hours": 0})
                pay_date += timedelta(days=14)
    for s in w.pay_statements:
        s["gross"] = sum(e["amount"] for e in s["earnings"])
        s["net"] = int(round(s["gross"] * r.uniform(0.68, 0.78)))
    by_date: dict[date, int] = {}
    for s in w.pay_statements:
        by_date[s["pay_date"]] = by_date.get(s["pay_date"], 0) + s["gross"]
    for d, gross in sorted(by_date.items()):
        w.transactions.append({"type": "Journal", "date": d, "currency": "USD", "total": gross, "memo": f"ADP payroll {d.isoformat()}",
                               "show": None, "void": False, "links": [], "fx": 1.0,
                               "lines": [{"kind": "debit", "acct": "6000", "dept": None, "amount": gross},
                                         {"kind": "credit", "acct": "1000", "dept": None, "amount": -gross}]})


def simulate(seed: int) -> World:
    r = random.Random(seed)
    w = World(seed=seed)
    ids = Ids(random.Random(seed + 1))
    make_people(w, r)
    make_venues(w, r)
    make_gear(w, r, ids)
    make_clients(w, r)
    make_ads(w, r, ids)
    make_crm(w, r, ids)
    make_shows(w, r, ids)
    make_crew(w, r)
    make_repairs(w, r)
    make_fx(w, r)
    make_payroll(w, r, ids)
    make_finance(w, r, ids)
    return w
