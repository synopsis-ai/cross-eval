"""Widens the core schema to each tier's size the way real accounts are wide: sparse custom fields on
core objects, plus many rarely-queried tables. Lower tiers are strict prefixes of higher ones, and every
padding column's values depend only on the seed and its own name, never on the tier."""

from __future__ import annotations

import random
from datetime import date, timedelta

from .render import Table

TIER_TARGETS = {1: 1_500, 2: 3_000, 3: 10_000, 4: 35_000}

# Neutral vocabulary: nothing here overlaps the subjects questions ask about (shows, revenue, invoices,
# hours, pay, campaigns, spend, leads, opportunities, venues), so padding never competes with the answer.
WORDS = """
preferred contact method region segment tier notes flag code status legacy migration source external reference
partner territory language timezone rating score priority category subcategory channel approval review compliance
risk parent group level type detail sync batch import export owner manager team unit division project phase
milestone survey nps feedback renewal health onboarding integration portal access consent optout marketing
newsletter linkedin website domain duns naics sic ticker fiscal headcount office site parking badge security
insurance certificate coi w9 exempt vat required terms localization accessibility sustainability diversity
procurement vendor portal sso mfa audit retention archive hold escalation sla routing queue macro template
signature brand logo color theme font locale dialect qualification persona interest hobby referral nickname
pronoun salutation suffix assistant birthday anniversary alma mater committee board advisory steering
""".split()

PADDED = {
    "salesforce_account": ("{a}_{b}_c", 1.0), "salesforce_opportunity": ("{a}_{b}_c", 1.0), "salesforce_contact": ("{a}_{b}_c", 0.6),
    "salesforce_lead": ("{a}_{b}_c", 0.8), "netsuite_customer": ("custentity_{a}_{b}", 0.5), "netsuite_transaction": ("custbody_{a}_{b}", 0.6),
    "netsuite_vendor": ("custentity_{a}_{b}", 0.3), "adp_workers": ("custom_{a}_{b}", 0.4), "cuewright_shows": ("usr_fld_{n:03d}", 0.4),
    "cuewright_clients": ("usr_fld_{n:03d}", 0.2),
}

FILLER_NOUNS = {
    "salesforce": """case case_comment solution knowledge_article knowledge_article_version idea vote document folder email_template dashboard
        report list_view permission_set permission_set_assignment profile user_role group_member queue_sobject topic topic_assignment
        content_version content_document content_document_link feed_item feed_comment collaboration_group macro quick_text
        social_persona duplicate_record_set duplicate_record_item individual contact_point_email contact_point_phone
        login_history setup_audit_trail user_login process_instance process_instance_step flow_interview approval
        site_visit_c competitor_c partner_referral_c nps_response_c survey_c survey_question_c survey_invitation_c
        territory_c territory_member_c holiday business_hours entitlement asset asset_relationship knowledge_c
        badge_c certification_c training_module_c onboarding_checklist_c account_plan_c account_team_member
        data_use_purpose consent_record_c brand_guideline_c""".split(),
    "netsuite": """bin classification nexus tax_item tax_group term price_level payment_method saved_search script_deployment role
        custom_list entity_group support_case phone_call note message file folder accounting_book budget_category
        location_type billing_schedule revenue_element unit_type ship_item employee_type job_type sales_role
        customrecord_insurance_cert customrecord_w9 customrecord_audit_note customrecord_approval_rule
        customrecord_dock_schedule customrecord_vendor_scorecard customrecord_sla customrecord_portal_user
        customrecord_retention customrecord_brand""".split(),
    "adp": """benefit_plans benefit_enrollments tax_withholdings direct_deposits time_off_requests time_off_balances org_units
        job_codes cost_numbers certifications emergency_contacts onboarding_tasks i9_status w4_elections garnishments
        dependents beneficiaries licenses skills education performance_reviews goals training_records equipment_assignments
        position_history manager_history locations_master business_units""".split(),
    "google_ads": """label asset asset_group conversion_action bidding_strategy shared_set shared_criterion campaign_criterion
        ad_group_criterion customer_client user_list audience extension_feed_item geo_target_constant
        recommendation change_status experiment keyword_plan""".split(),
    "meta_ads": """ad_creatives ad_images ad_videos custom_audiences saved_audiences pixels ad_labels ad_rules lead_forms
        business_users page_posts catalog product_sets offline_event_sets""".split(),
    "cuewright": """xusrp xcfgs xrpts xaudt xlblp xtrkp xcase xdock xpwrd xseat xcolr xfont xlang xperm xrole xntfy xmacr
        xtmpl xsign xarch xhold xescl xqueu xrout xbadg xcert xinsu xsftp xsync xbatch xexpt ximpt xlogo xbrnd""".split(),
}
FILLER_SUFFIXES = {
    "salesforce": ["", "_share", "_feed", "_tag"],
    "netsuite": ["", "_map", "_log"],
    "adp": ["", "_history", "_audit"],
    "google_ads": ["", "_view", "_link"],
    "meta_ads": ["", "_history", "_link"],
    "cuewright": ["", "h", "x", "a", "b"],
}


def _rng(seed: int, *parts: str) -> random.Random:
    return random.Random(f"{seed}:" + ":".join(parts))


def _value(rr: random.Random, kind: str):
    if kind == "str":
        return rr.choice(WORDS).title() if rr.random() < 0.7 else f"{rr.choice(WORDS)}-{rr.randint(1, 999)}"
    if kind == "int":
        return rr.randint(0, 5000)
    if kind == "float":
        return round(rr.uniform(0, 100), 2)
    if kind == "bool":
        return rr.random() < 0.5
    return date(2020, 1, 1) + timedelta(days=rr.randint(0, 2400))


def _column_names(seed: int, table: str, pattern: str, n: int, taken: set) -> list:
    rr = _rng(seed, "cols", table)
    names, i = [], 0
    while len(names) < n:
        i += 1
        a, b = rr.choice(WORDS), rr.choice(WORDS)
        nm = pattern.format(a=a, b=b, n=i)
        if nm not in taken and a != b:
            taken.add(nm)
            names.append(nm)
    return names


def _filler_plan(seed: int) -> list:
    """Every possible filler table, in a fixed order; a tier takes a prefix."""
    plan = []
    for system, nouns in FILLER_NOUNS.items():
        for suffix in FILLER_SUFFIXES[system]:
            for noun in nouns:
                name = f"{system}_{noun}{suffix}"
                plan.append((system, name))
    rr = _rng(seed, "filler-order")
    rr.shuffle(plan)
    return plan


def _filler_table(seed: int, system: str, name: str) -> Table:
    rr = _rng(seed, "filler", name)
    base = {
        "salesforce": [("id", "str"), ("is_deleted", "bool"), ("name", "str"), ("owner_id", "str"), ("created_date", "str"), ("last_modified_date", "str"), ("system_modstamp", "str")],
        "netsuite": [("id", "int"), ("name", "str"), ("isinactive", "str"), ("created", "str"), ("lastmodified", "str")],
        "adp": [("associate_oid", "str"), ("item_id", "str"), ("effective_date", "date"), ("code_value", "str"), ("short_name", "str")],
        "google_ads": [("customer_id", "int"), ("resource_name", "str"), ("id", "int"), ("name", "str"), ("status", "str")],
        "meta_ads": [("id", "str"), ("account_id", "str"), ("name", "str"), ("status", "str"), ("created_time", "str")],
        "cuewright": [(f"{name.split('_', 1)[1][:4]}_id", "int"), (f"{name.split('_', 1)[1][:4]}_cd", "str"), (f"{name.split('_', 1)[1][:4]}_desc", "str"), ("upd_ts", "str"), ("upd_usr", "int")],
    }[system]
    n_extra = rr.randint(10, 80)
    style = {"salesforce": "{a}_{b}_c", "netsuite": "custrecord_{a}_{b}", "adp": "{a}_{b}", "google_ads": "{a}_{b}", "meta_ads": "{a}_{b}",
             "cuewright": name.split("_", 1)[1][:4] + "_{a}{n}"}[system]
    taken = {c for c, _ in base}
    extra = [(c, rr.choice(["str", "str", "str", "int", "float", "bool", "date"])) for c in _column_names(seed, name, style, n_extra, taken)]
    cols = base + extra
    t = Table(cols)
    for i in range(rr.randint(0, 120)):
        row = {}
        for c, kind in cols:
            if c in ("id", "item_id") or c.endswith("_id") and kind == "int":
                row[c] = i + 1 if kind == "int" else f"{name[:6]}{i + 1:06d}"
            elif rr.random() < 0.5:
                row[c] = _value(rr, kind)
        t.rows.append(row)
    return t


def widen(core: dict, seed: int, tier: int) -> dict:
    """Returns a new {system: {table: Table}} at the tier's width. The core tables are not mutated."""
    out = {s: {name: Table(list(t.cols), t.rows) for name, t in tabs.items()} for s, tabs in core.items()}
    core_cols = sum(len(t.cols) for tabs in core.values() for t in tabs.values())
    target = TIER_TARGETS[tier]
    pad_scale = {1: 0.8, 2: 1.6, 3: 3.2, 4: 6.4}[tier]
    pad_total = 0
    for table, (pattern, weight) in PADDED.items():
        system = next(s for s, tabs in core.items() if table in tabs)
        t = out[system][table]
        n = int(round(40 * weight * pad_scale))
        all_names = _column_names(seed, f"pad:{table}", pattern, int(round(40 * weight * 6.4)), {c for c, _ in t.cols})
        names = all_names[:n]
        kinds = [_rng(seed, "padkind", table, nm).choice(["str", "str", "str", "int", "float", "bool", "date"]) for nm in names]
        new_rows = [dict(row) for row in t.rows]
        for nm, kind in zip(names, kinds):
            rr = _rng(seed, "pad", table, nm)
            for row in new_rows:
                if rr.random() < 0.12:
                    row[nm] = _value(rr, kind)
        t.cols = t.cols + list(zip(names, kinds))
        t.rows = new_rows
        pad_total += n
    have = core_cols + pad_total
    for system, name in _filler_plan(seed):
        if have >= target:
            break
        ft = _filler_table(seed, system, name)
        out[system][name] = ft
        have += len(ft.cols)
    if have < target:
        raise ValueError(f"tier {tier}: only {have} columns available, target {target}")
    return out
