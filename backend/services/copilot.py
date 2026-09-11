"""The decision copilot.

Answers questions about the platform, the methodology behind a recommendation,
and the reference data behind it - grounded in the live database and the
decision engine rather than in prewritten strings that drift out of date.

There is deliberately no language-model call here. The questions this thing
answers are about landed cost, lane economics and procurement timing; sending
that to a third-party inference API would export exactly the material the rest
of the platform is built to keep in. Everything is computed locally from data
the signed-in user is already entitled to see.

Two boundaries protect the answers:

  ALLOW  an intent has to match before anything is composed, so the copilot
         only speaks about subjects it has a grounded answer for.
  SCRUB  every reply passes through `redact` on the way out, which removes
         anything shaped like a credential, a path or a connection string
         regardless of how it got there.
"""

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Security boundary
# ---------------------------------------------------------------------------

# Questions aimed at the machine rather than the cargo. Refused before any
# answer is composed - the copilot has no business discussing them, and saying
# so plainly is better than a vague non-answer.
PROBE_TERMS = {
    "secret", "secret_key", "api key", "apikey", "token", "password", "passwd",
    "credential", "env var", "environment variable", "os.environ", ".env",
    "private key", "signing key", "jwt secret", "database url", "connection string",
    "dump the", "drop table", "sql", "shell", "os.system", "subprocess",
    "source code", "show me the code", "file system", "directory listing",
    "config file", "vercel token", "aws", "hashed_password", "bcrypt hash",
}

# Anything credential-, path- or endpoint-shaped never leaves this module.
_SCRUB_PATTERNS = [
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*\.?[A-Za-z0-9_\-]*"), "[redacted token]"),
    (re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{20,}"), "[redacted hash]"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[redacted]"),
    (re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|sqlite)://\S+", re.I), "[redacted connection string]"),
    (re.compile(r"[A-Za-z]:\\\\[^\s\"'<>]+"), "[redacted path]"),
    (re.compile(r"(?<![\w/])/(?:home|root|tmp|var|etc|usr)/[^\s\"'<>]*"), "[redacted path]"),
    (re.compile(r"\bLOHA_[A-Z_]+\s*=\s*\S+"), "[redacted setting]"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9]{16,}\b"), "[redacted key]"),
]


def redact(text: str) -> str:
    """Last line of defence on the way out."""
    for pattern, replacement in _SCRUB_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _is_probe(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in PROBE_TERMS)


REFUSAL = (
    "I can explain how the platform reaches a recommendation and what the "
    "figures mean, but not how it is configured or credentialed - keys, "
    "connection details and source files are outside what I will discuss. "
    "Ask me about the cargo, the ports, the costing or the model instead."
)


# ---------------------------------------------------------------------------
# Intent model
# ---------------------------------------------------------------------------

@dataclass
class Intent:
    name: str
    terms: tuple           # any of these, weighted 1
    strong: tuple = ()     # a hit here settles it, weighted 3
    topic: str = "General"


INTENTS = [
    Intent("vessel_choice", ("vessel", "ship", "class", "size", "tonnage", "dwt",
                             "capesize", "panamax", "supramax", "handysize"),
           ("why this vessel", "which vessel", "vessel class"), "Fleet"),
    Intent("port_choice", ("port", "berth", "discharge", "terminal", "why not"),
           ("why this port", "which port", "why not", "discharge port"), "Ports"),
    Intent("port_profile", ("draft", "loa", "berths", "handling rate", "mechanised",
                            "evacuation", "wharfage"),
           ("port profile", "port dna"), "Ports"),
    Intent("cost_breakdown", ("cost", "landed", "breakdown", "waterfall", "component",
                              "fob", "price", "expensive", "cheaper"),
           ("landed cost", "cost breakdown", "what makes up"), "Costing"),
    Intent("deadfreight", ("deadfreight", "dead freight", "unused space", "utilisation",
                           "utilization", "part loaded"),
           ("deadfreight",), "Costing"),
    Intent("demurrage", ("demurrage", "laytime", "waiting", "queue", "despatch"),
           ("demurrage", "laytime"), "Costing"),
    Intent("lightering", ("lighter", "lightering", "transhipment", "barge", "shallow"),
           ("lightering",), "Costing"),
    Intent("risk", ("risk", "exposure", "volatility", "congestion", "monsoon",
                    "cyclone", "weather"),
           ("risk index", "how is risk"), "Risk"),
    Intent("continuity", ("continuity", "supply", "buffer", "plant delivery",
                          "schedule headroom", "laycan"),
           ("supply continuity",), "Risk"),
    Intent("saving", ("saving", "savings", "benefit", "optimisation saving",
                      "optimization saving", "versus median"),
           ("optimisation saving", "how much are we saving"), "Costing"),
    Intent("ranking", ("rank", "ranked", "decide", "decided", "chosen", "selection",
                       "methodology", "regret", "minimax", "risk-adjusted"),
           ("how was this decided", "how do you rank", "how are options ranked"), "Method"),
    Intent("model", ("model", "forecast", "predict", "accuracy", "r2", "mae", "rmse",
                     "mape", "training", "trained", "algorithm", "gradient"),
           ("ml model", "how accurate", "forecast"), "Model"),
    Intent("scenarios", ("scenario", "what if", "what-if", "disruption", "simulate",
                         "spike", "blocked", "closure", "bunker", "unavailable",
                         "hits", "strikes", "goes wrong", "happens if"),
           ("what if", "what happens if", "scenario", "simulator"), "Scenarios"),
    Intent("data_sources", ("data", "source", "synthetic", "real", "provenance",
                            "governance", "where does", "benchmark", "reliable"),
           ("data source", "is this real", "synthetic"), "Governance"),
    Intent("security", ("security", "secure", "confidential", "who can see",
                        "access", "permission", "role", "audit", "sign in", "login"),
           ("is it secure", "who can see"), "Governance"),
    Intent("plants", ("plant", "rourkela", "bhilai", "bokaro", "durgapur", "burnpur",
                      "steel plant", "rail"),
           ("which plant",), "Network"),
    Intent("origins", ("origin", "lane", "australia", "indonesia", "south africa",
                       "usa", "distance", "voyage", "corridor"),
           ("which origin", "origin lane"), "Network"),
    Intent("waterways", ("waterway", "canal", "strait", "suez", "panama", "malacca",
                         "hormuz", "chokepoint", "route"),
           ("waterway", "chokepoint"), "Network"),
    Intent("navigation", ("how do i", "where is", "find", "navigate", "button",
                          "page", "screen", "panel", "export", "report", "print"),
           ("how do i", "where do i"), "Using the platform"),
    Intent("glossary", ("what is", "what does", "meaning", "define", "definition",
                        "laycan", "charter party", "coa", "ukc", "under keel",
                        "voyage charter", "spot"),
           ("what does", "what is a"), "Glossary"),
]


def classify(question: str):
    """Score every intent; the best non-zero score wins."""
    lowered = " " + re.sub(r"[^a-z0-9%\- ]+", " ", question.lower()) + " "
    scored = []
    for intent in INTENTS:
        score = sum(3 for phrase in intent.strong if phrase in lowered)
        score += sum(1 for term in intent.terms if f" {term} " in lowered or term in lowered)
        if score:
            scored.append((score, intent))
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]


# ---------------------------------------------------------------------------
# Reference knowledge
# ---------------------------------------------------------------------------

GLOSSARY = {
    "laycan": "The agreed window between the earliest date a vessel may present "
              "for loading and the date after which the charterer may cancel.",
    "deadfreight": "Freight payable on booked space that is not filled. Charter "
                   "the space, and you pay for it whether cargo occupies it or not.",
    "demurrage": "Compensation to the owner when the vessel is detained beyond the "
                 "agreed laytime, charged per day at the rate in the charter party.",
    "laytime": "The time allowed, free of charge, to load or discharge. Beyond it, "
               "demurrage begins to run.",
    "ukc": "Under-keel clearance: the water between the vessel's keel and the "
           "seabed. The platform requires 0.6 m before a berth is considered usable.",
    "draft": "The depth of the vessel below the waterline. It rises as cargo is "
             "loaded, which is why a berth's usable draft governs how much can be lifted.",
    "loa": "Length overall - the total length of the vessel, and a hard limit at "
           "berths with restricted turning circles.",
    "dwt": "Deadweight tonnage: the total mass a vessel can carry including cargo, "
           "bunkers and stores.",
    "fob": "Free On Board - the cargo price at the load port, before any freight, "
           "port or inland cost is added.",
    "coa": "Contract of Affreightment: an agreement to move a stated quantity over "
           "several voyages, trading spot flexibility for rate certainty.",
    "voyage charter": "Hiring a vessel for one defined voyage at a rate per tonne, "
                      "with the owner bearing the operating cost.",
    "spot": "A single fixture at the prevailing market rate, with no forward "
            "commitment and full exposure to rate movement.",
    "lightering": "Transferring part of a cargo to barges offshore so the mother "
                  "vessel floats high enough to enter a draft-restricted berth.",
    "bunker": "Fuel for the vessel. Its price is one of the model's four market "
              "inputs because it moves freight rates directly.",
    "capesize": "The largest dry-bulk class here, around 180,000 DWT - too big for "
                "the Suez and Panama canals, hence the name.",
    "panamax": "Around 80,000 DWT, sized to the original Panama Canal locks.",
    "supramax": "Around 60,000 DWT, usually geared so it can work at berths without "
                "shore cranes.",
    "handysize": "Around 40,000 DWT - the most berth-flexible class, and the one "
                 "that fits draft-restricted ports.",
}


def _fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


@dataclass
class Answer:
    text: str
    topic: str = "General"
    sources: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "answer": redact(self.text),
            "topic": self.topic,
            "sources": self.sources,
            "suggestions": self.suggestions,
        }


# ---------------------------------------------------------------------------
# Answer builders
#
# Each takes the live reference data and, where available, the recommendation
# currently on the user's screen, so the copilot and the dashboard cannot
# disagree about a number.
# ---------------------------------------------------------------------------

def _best(context: dict) -> dict:
    return (context or {}).get("recommended") or {}


def _plant_label(context) -> str:
    return (_best(context).get("plant") or "the plant").split("(")[0].strip()


def _rail_for(port, context) -> float:
    """Rail distance from this berth to the plant on screen - not the berth's
    generic figure, which is the same whichever plant is chosen."""
    from services import network

    return network.rail_km(port, _best(context).get("plant") or "")


def _answer_vessel(ports, vessels, context, question):
    best = _best(context)
    fleet = ", ".join(
        f"{v.class_type} ({v.capacity_mt:,.0f} MT, {v.draft_m:.1f} m draft)"
        for v in sorted(vessels, key=lambda v: v.capacity_mt)
    )
    if best:
        text = (
            f"<b>{best.get('vessel_class')}</b> was selected for this parcel. It lifts "
            f"{best.get('parcel_mt', 0):,.0f} MT in {best.get('shipments')} shipment(s) at "
            f"{best.get('utilisation_pct', 0):.0f}% utilisation, and its laden draft clears "
            f"{best.get('port_name')}.<br><br>"
            "Class selection is not a preference - it falls out of three constraints: the "
            "berth's usable draft against the vessel's laden draft, the length-overall limit, "
            "and deadfreight. A larger ship moves a tonne more cheaply, but only if it is "
            "actually full; book 180,000 MT of space for an 80,000 MT parcel and you pay for "
            "the empty half."
        )
        if best.get("deadfreight_usd", 0) > 0:
            text += (
                f"<br><br>This option still carries {_fmt_usd(best['deadfreight_usd'])} of "
                "deadfreight, which the ranking has already priced in."
            )
    else:
        text = (
            "Vessel class is chosen by testing every class against every berth: laden draft "
            "against usable draft, length overall against the berth limit, and deadfreight on "
            "space booked but not filled. Run a strategy and I can explain the specific choice."
        )
    return Answer(text + f"<br><br><i>Fleet available: {fleet}.</i>", "Fleet",
                  ["/api/vessels", "decision engine"],
                  ["Why this port?", "What is deadfreight?", "How is the cost built up?"])


def _answer_port(ports, vessels, context, question):
    lowered = question.lower()
    named = [p for p in ports if p.name.lower().split("/")[0] in lowered]
    best = _best(context)

    if named:
        p = named[0]
        text = (
            f"<b>{p.name} ({p.code})</b><br>"
            f"Usable draft {p.draft_m:.1f} m &middot; LOA limit {p.max_loa:.0f} m &middot; "
            f"{p.berths} berth(s)<br>"
            f"Mechanised handling {p.mech_rate_mt_d:,.0f} MT/day &middot; "
            f"average pre-berthing wait {p.avg_wait_days:.1f} days<br>"
            f"Demurrage {_fmt_usd(p.demurrage_usd_day)}/day &middot; "
            f"rail to {_plant_label(context)} {_rail_for(p, context):.0f} km<br>"
            f"Monsoon/cyclone months: {p.monsoon_months or '-'}"
        )
        if p.draft_m < 12:
            text += (
                f"<br><br>{p.name} is draft-restricted. Anything drawing more than "
                f"{p.draft_m - 0.6:.1f} m laden needs lightering before it can berth, which "
                "adds cost and a transhipment that can stall - so it rarely wins on a large "
                "parcel however short the rail leg looks."
            )
        if best and best.get("port_name") != p.name:
            text += (
                f"<br><br>It was not selected this time: <b>{best.get('port_name')}</b> came "
                f"out ahead on risk-adjusted landed cost "
                f"({_fmt_usd(best.get('landed_cost_usd_mt', 0))}/MT at risk "
                f"{best.get('risk_index', 0):.0f}/100)."
            )
        return Answer(text, "Ports", ["/api/ports"],
                      ["Why was this port chosen?", "How is demurrage calculated?"])

    if best:
        parcel = max(best.get("parcel_mt", 1), 1)
        text = (
            f"<b>{best.get('port_name')}</b> was selected. Port choice balances four things "
            "that pull against each other: berth draft (can the laden ship enter at all), "
            "handling rate (how fast it discharges), pre-berthing queue (demurrage exposure), "
            "and rail distance to the plant.<br><br>"
            f"On this parcel it discharges in {best.get('discharge_days', 0):.1f} days after "
            f"{best.get('wait_days', 0):.1f} days of expected waiting, and the inland leg costs "
            f"{_fmt_usd(best.get('inland_rail_usd', 0) / parcel)}/MT.<br><br>"
            "A nearer port with a shallow berth often loses to a deeper one further inland, "
            "because lightering and demurrage cost more than the extra rail."
        )
    else:
        text = (
            "Port choice balances berth draft, handling rate, pre-berthing queue and rail "
            "distance to the plant. Run a strategy and I will explain the specific selection."
        )
    return Answer(text, "Ports", ["/api/ports", "decision engine"],
                  ["Why is Haldia draft restricted?", "How is demurrage calculated?"])


def _answer_cost(ports, vessels, context, question):
    best = _best(context)
    if not best:
        return Answer(
            "Landed cost is assembled from ocean freight (predicted per tonne by the model), "
            "deadfreight on unfilled booked space, vessel hire across sea and port days, port "
            "dues, demurrage beyond free laytime, lightering where a berth is draft-limited, "
            "and inland rail to the plant. The cargo's FOB price, which differs by origin, sits "
            "on top and is what decides between origins. Run a strategy and I will break down "
            "the actual figures.",
            "Costing", ["decision engine"],
            ["Run a strategy", "What is deadfreight?"])

    parcel = max(best.get("parcel_mt", 1), 1)
    rows = [
        ("Ocean freight", best.get("ocean_freight_usd", 0)),
        ("Deadfreight", best.get("deadfreight_usd", 0)),
        ("Vessel hire", best.get("vessel_hire_usd", 0)),
        ("Port dues", best.get("port_dues_usd", 0)),
        ("Demurrage", best.get("demurrage_usd", 0)),
        ("Lightering", best.get("lightering_usd", 0)),
        ("Inland rail", best.get("inland_rail_usd", 0)),
    ]
    lines = "".join(
        f"<br>&bull; {label}: {_fmt_usd(value)} ({_fmt_usd(value / parcel)}/MT)"
        for label, value in rows if value > 0
    )
    text = (
        f"Logistics cost for {parcel:,.0f} MT via <b>{best.get('vessel_class')}</b> into "
        f"<b>{best.get('port_name')}</b> totals {_fmt_usd(best.get('landed_cost_usd', 0))} "
        f"({_fmt_usd(best.get('landed_cost_usd_mt', 0))}/MT):{lines}"
        + (f"<br><br>Cargo price from {best.get('origin')}: {_fmt_usd(best['fob_usd_mt'])}/MT FOB "
           f"(indicative, quality-adjusted), so {_fmt_usd(best.get('delivered_cost_usd_mt', 0))}/MT "
           "delivered. That price is what decides between origins."
           if best.get("fob_usd_mt") else "")
        + "<br><br>The dashboard adds origin-side charges, marine insurance and working-capital "
        "financing to reach the figure on the card. Every line here comes from the same "
        "calculation that produced the recommendation."
    )
    return Answer(text, "Costing", ["/api/decision/optimize"],
                  ["What is deadfreight?", "How is demurrage calculated?",
                   "How much is the optimisation saving?"])


def _answer_deadfreight(ports, vessels, context, question):
    best = _best(context)
    text = (
        "<b>Deadfreight</b> is freight payable on booked space you do not fill. A voyage "
        "charter buys the ship's capacity, not the tonnes you happen to load.<br><br>"
        "The engine charges it on space left empty beyond a 10% tolerance, at 35% of the "
        "freight rate. That is what stops it recommending a half-empty Capesize: without it the "
        "per-tonne rate looks attractive right until you pay for the empty half."
    )
    if best:
        dead = best.get("deadfreight_usd", 0)
        text += (
            f"<br><br>On the current recommendation utilisation is "
            f"{best.get('utilisation_pct', 0):.0f}% and deadfreight is "
            f"{'nil' if dead <= 0 else _fmt_usd(dead)}."
        )
    return Answer(text, "Costing", ["decision engine"],
                  ["Why this vessel class?", "How is the cost built up?"])


def _answer_demurrage(ports, vessels, context, question):
    best = _best(context)
    text = (
        "<b>Demurrage</b> is what the charterer owes the owner once the vessel is held beyond "
        "agreed laytime. The engine allows 3 free days per shipment, then charges the excess at "
        "that berth's own daily rate - it is not the same money as vessel hire, and both are "
        "counted.<br><br>Berth queues are why a nearer port can lose: waiting days convert "
        "directly into cost."
    )
    if best:
        text += (
            f"<br><br>Here, {best.get('port_name')} carries {best.get('wait_days', 0):.1f} days "
            f"of expected waiting, giving {_fmt_usd(best.get('demurrage_usd', 0))} of exposure."
        )
    queues = ", ".join(
        f"{p.name} {p.avg_wait_days:.1f}d at {_fmt_usd(p.demurrage_usd_day)}/day"
        for p in sorted(ports, key=lambda p: p.avg_wait_days)[:4]
    )
    return Answer(text + f"<br><br><i>Shortest queues: {queues}.</i>", "Costing",
                  ["/api/ports"], ["Why this port?", "What is laytime?"])


def _answer_lightering(ports, vessels, context, question):
    shallow = [p for p in ports if p.draft_m < 13]
    names = ", ".join(f"{p.name} ({p.draft_m:.1f} m)" for p in shallow) or "none in this network"
    return Answer(
        "<b>Lightering</b> transfers part of a cargo to barges offshore so the mother vessel "
        "floats high enough to enter a draft-restricted berth. The engine prices it at $2.20/MT "
        "on the tonnage that must come off, and treats a berth as unusable once laden draft "
        "exceeds usable draft by more than 4 m.<br><br>It also carries schedule risk: an extra "
        "transhipment is another thing that can stall, which the continuity score penalises."
        f"<br><br><i>Draft-restricted here: {names}.</i>",
        "Costing", ["/api/ports", "decision engine"],
        ["Why is Haldia draft restricted?", "How is supply continuity scored?"])


def _answer_risk(ports, vessels, context, question):
    best = _best(context)
    text = (
        "The <b>Risk Index</b> is 0-100, weighted across four components:<br>"
        "&bull; Berth congestion (30%) - expected waiting, plus a penalty for single-berth ports<br>"
        "&bull; Seasonal exposure (25%) - monsoon and Bay of Bengal cyclone season, raised "
        "further when the berth itself lists that month<br>"
        "&bull; Freight-market volatility (25%) - the market pressure index<br>"
        "&bull; Under-keel margin (20%) - how much water is left beneath the keel<br><br>"
        "Options are ranked on cost per tonne x (1 + 0.35 x risk/100), so a marginally cheaper "
        "berth does not win when it carries materially more exposure."
    )
    if best:
        text += (
            f"<br><br>Current: <b>{best.get('risk_index', 0):.0f}/100</b> "
            f"(congestion {best.get('congestion_score', 0):.0f}, seasonal "
            f"{best.get('monsoon_risk_score', 0):.0f}, volatility "
            f"{best.get('freight_volatility_score', 0):.0f}, draft "
            f"{best.get('draft_risk_score', 0):.0f})."
        )
    return Answer(text, "Risk", ["decision engine"],
                  ["How is supply continuity scored?", "What if a cyclone hits?"])


def _answer_continuity(ports, vessels, context, question):
    best = _best(context)
    text = (
        "<b>Supply Continuity</b> estimates confidence that the parcel reaches the plant inside "
        "the laycan window. Three factors compound rather than add:<br>"
        "&bull; <i>Schedule headroom</i> - how much of the window the voyage cycle consumes. "
        "Comfortable below half, precarious past 80%, near zero once it overruns<br>"
        "&bull; <i>Disruption risk</i> - up to 45% of confidence lost to congestion, weather "
        "and volatility<br>"
        "&bull; <i>Execution</i> - each extra shipment is another chance to slip, and lightering "
        "adds a transhipment that can stall<br><br>"
        "They multiply, so a roomy schedule cannot rescue a high-risk lane. Capped at 97: "
        "certainty is not something a charter offers."
    )
    if best:
        text += (
            f"<br><br>Current: <b>{best.get('supply_continuity', 0):.0f}/100</b> - schedule "
            f"headroom {best.get('schedule_headroom_pct', 0):.0f}%, risk factor "
            f"{best.get('continuity_risk_factor_pct', 0):.0f}%, execution "
            f"{best.get('execution_factor_pct', 0):.0f}%. The lowest of those is what holds the "
            "score down."
        )
    return Answer(text, "Risk", ["decision engine"],
                  ["How is the risk index calculated?", "What happens in monsoon?"])


def _answer_saving(ports, vessels, context, question):
    options = (context or {}).get("options") or []
    text = (
        "The <b>Optimisation Saving</b> compares the recommended strategy against the "
        "<i>median</i> of the feasible shortlist - what the parcel would plausibly cost if "
        "placed without the engine.<br><br>"
        "It deliberately does not compare against the runner-up. The second-ranked option is "
        "almost always a near-twin of the winner - same lane, same class, an adjacent berth "
        "whose rail and waiting costs cancel - so that comparison collapses to a rounding error "
        "and understates the work. Nor does it use the worst option, which would flatter it."
    )
    if options:
        totals = sorted(o.get("landed_cost_usd_mt", 0) for o in options)
        if totals:
            median = totals[len(totals) // 2]
            text += (
                f"<br><br>Across {len(totals)} feasible options here: best "
                f"{_fmt_usd(totals[0])}/MT, median {_fmt_usd(median)}/MT, worst "
                f"{_fmt_usd(totals[-1])}/MT - a saving of {_fmt_usd(median - totals[0])}/MT "
                f"against the median, {_fmt_usd(totals[-1] - totals[0])}/MT against the worst."
            )
    return Answer(text, "Costing", ["/api/decision/optimize"],
                  ["How is the cost built up?", "How are options ranked?"])


def _answer_ranking(ports, vessels, context, question):
    evaluated = ((context or {}).get("context") or {}).get("candidates_evaluated")
    text = (
        "Every feasible combination of vessel class and discharge berth is scored, then ranked "
        "on <b>risk-adjusted landed cost</b>: cost per tonne x (1 + 0.35 x risk/100).<br><br>"
        "Feasibility is a real filter, not a preference. A pairing is dropped when laden draft "
        "exceeds the berth's usable draft by more than the lighterable margin, or when the "
        "length-overall limit cannot take the class. Part-loaded ships float higher, so laden "
        "draft is scaled by utilisation rather than assumed at scantling.<br><br>"
        "The scenario regret table below the recommendation is a cross-check, not the selection "
        "rule: it re-prices the shortlist under four market scenarios and shows how much each "
        "option would lose against the best available choice if that scenario turned bad."
    )
    if evaluated:
        text += f"<br><br>{evaluated} feasible pairings were scored for this parcel."
    return Answer(text, "Method", ["decision engine"],
                  ["How is the risk index calculated?", "How much are we saving?"])


def _answer_model(ports, vessels, context, question):
    from services import model_registry

    meta = dict(model_registry.get_payload().get("metadata") or {})
    text = (
        "Ocean freight is predicted by a <b>gradient-boosted regressor</b> over four inputs - "
        "voyage distance, calendar month, bunker price and a market pressure index - plus a "
        "one-hot origin lane.<br><br>"
        f"Held-out accuracy: <b>R&sup2; {meta.get('r2_score', 'n/a')}</b>, MAE "
        f"${meta.get('mae_usd', 'n/a')}/MT, RMSE ${meta.get('rmse_usd', 'n/a')}/MT, MAPE "
        f"{meta.get('mape_pct', 'n/a')}%, trained on {meta.get('records_count', 'n/a')} records."
        "<br><br>Month is the only time feature, so a naive daily forecast would be flat within "
        "a month and jump at the boundary. The rate horizon blends the model's response for the "
        "two months bracketing each date to get a smooth daily curve, and anchors day one to the "
        "last historical value so the two legs meet cleanly at the TODAY divider.<br><br>"
        "The training data is <b>synthetic, calibrated against dry-bulk benchmarks</b> - every "
        "response carrying a prediction says so in a data_source field."
    )
    return Answer(text, "Model", ["/api/ml/info"],
                  ["Where does the data come from?", "How is the forecast anchored?"])


def _answer_scenarios(ports, vessels, context, question):
    return Answer(
        "The <b>What-If Simulator</b> re-prices the whole shortlist under a disruption and "
        "reports the delta against baseline with a mitigation. Six scenarios:<br>"
        "&bull; <b>Cyclone</b> - peak Bay of Bengal month, +4 days berth wait, market pressure +35%<br>"
        "&bull; <b>Monsoon</b> - south-west season, +1.8 days berth wait<br>"
        "&bull; <b>Port closure</b> - a named berth removed from the feasible set<br>"
        "&bull; <b>Freight spike</b> - market pressure +50%<br>"
        "&bull; <b>Bunker spike</b> - fuel +40%, which flows through the model into the rate<br>"
        "&bull; <b>Tonnage unavailable</b> - a vessel class withdrawn<br><br>"
        "Ports and vessels are perturbed in memory only; nothing is written back to the "
        "reference data. The useful output is not the new cost but the delta - it tells you how "
        "exposed the plan is, and which mitigation actually recovers the position.",
        "Scenarios", ["/api/decision/simulate"],
        ["What happens if the port is blocked?", "How is the risk index calculated?"])


def _answer_data_sources(ports, vessels, context, question):
    return Answer(
        "Every figure carries a classification, and nothing here is live operational data.<br><br>"
        "&bull; <b>Public / regulatory</b> - port draft, LOA limits, mechanised handling rates "
        "and statutory tariff structures follow figures published by the Ministry of Ports, "
        "Shipping and Waterways and the Indian Ports Association<br>"
        "&bull; <b>Calibrated baseline</b> - bunker corridors, rail tariffs, demurrage rates and "
        "laytime conventions, held as configurable constants in the service<br>"
        "&bull; <b>Synthetic</b> - the model's training set: 1,500 calibrated voyage records "
        "across four lanes<br><br>"
        "It does not connect to SAIL procurement systems, receive live AIS positions, or quote "
        "real charter rates. The historical leg of the freight chart is the model's own response "
        "for past dates, not observed market data. Where the service cannot be reached the "
        "dashboard falls back to a local approximation and marks itself <b>Offline Estimate</b>, "
        "so an estimate is never presented as a model output.<br><br>"
        "The full register is on the About &amp; Data Governance page.",
        "Governance", ["About & Data Governance"],
        ["How accurate is the model?", "Who can see this data?"])


def _answer_security(ports, vessels, context, question):
    return Answer(
        "Access is controlled and recorded.<br><br>"
        "&bull; Sessions are httpOnly, SameSite=strict cookies - the page cannot read the token, "
        "so injected script cannot lift it<br>"
        "&bull; Everything disclosing commercial figures needs a session: the decision engine, "
        "port tariffs, charter rates, freight predictions and procurement history<br>"
        "&bull; Cargo listings are scoped to you; reading across users is an Admin privilege<br>"
        "&bull; Self-registration is closed unless your domain is on the allow-list<br>"
        "&bull; Failed sign-ins are throttled, and both failures and reads of priced "
        "recommendations are written to the audit log<br><br>"
        "Known gaps, documented rather than hidden: tokens cannot be revoked before they expire, "
        "there is no MFA, and the database is not encrypted at rest. Real procurement data would "
        "also need to sit on government infrastructure rather than public cloud.<br><br>"
        "I will not discuss configuration, credentials or source files.",
        "Governance", ["About & Data Governance"],
        ["Where does the data come from?", "What data is stored?"])


def _answer_plants(ports, vessels, context, question):
    best = _best(context)
    text = (
        "The network serves five integrated steel plants - Rourkela, Bhilai, Durgapur, Bokaro "
        "and IISCO Burnpur. The plant matters because it fixes the inland leg: rail distance "
        "from the discharge berth is a real cost line, priced at roughly $0.019 per tonne-km, "
        "and it is often what decides between two otherwise similar ports.<br><br>"
        "Rail evacuation distances from each berth: "
        + ", ".join(f"{p.name} {_rail_for(p, context):.0f} km"
                    for p in sorted(ports, key=lambda p: _rail_for(p, context)))
        + "."
    )
    if best:
        parcel = max(best.get("parcel_mt", 1), 1)
        text += (
            f"<br><br>For the current parcel the inland leg costs "
            f"{_fmt_usd(best.get('inland_rail_usd', 0))} "
            f"({_fmt_usd(best.get('inland_rail_usd', 0) / parcel)}/MT)."
        )
    return Answer(text, "Network", ["/api/ports"],
                  ["Why this port?", "How is the cost built up?"])


def _answer_origins(ports, vessels, context, question):
    from services import model_registry

    lanes = ", ".join(
        f"{origin} {distance:,.0f} nm"
        for origin, distance in sorted(model_registry.ORIGIN_DISTANCE_NM.items())
    )
    return Answer(
        "Four origin lanes are modelled, and the distance is what drives both the voyage time "
        f"and the freight rate: {lanes}.<br><br>"
        "Choosing 'Any Origin' scores every lane the model knows and compares them on "
        "risk-adjusted landed cost, so a longer voyage can still win if the rate, berth and "
        "rail combination is better. Adding a lane the model was not trained on would fall back "
        "to a default distance, which is why the selector is restricted to these four.",
        "Network", ["/api/ml/info"],
        ["Why this origin?", "How accurate is the model?"])


def _answer_waterways(ports, vessels, context, question):
    return Answer(
        "The International Waterways panel maps the canals, straits and shipping routes that "
        "constrain global dry-bulk movement - Suez, Panama, Malacca, Hormuz, Bab-el-Mandeb, "
        "Gibraltar and the Cape route among them - with the ports each connects and indicative "
        "vessel positions.<br><br>"
        "It is context rather than an input: the lanes modelled here reach the Indian east coast "
        "without transiting Suez or Panama, so a closure there affects the market rate the model "
        "sees rather than the route itself. Vessel positions shown are synthetic.",
        "Network", ["/api/waterways"],
        ["Which origin lanes are modelled?", "Where does the data come from?"])


def _answer_navigation(ports, vessels, context, question):
    return Answer(
        "Getting around:<br>"
        "&bull; <b>Command Centre</b> - the recommendation, cost waterfall and regret matrix<br>"
        "&bull; <b>Freight Intelligence</b> - the rate horizon chart and market pressure gauge<br>"
        "&bull; <b>What-If Simulator</b> - disruption scenarios<br>"
        "&bull; <b>Port Profiles</b> and <b>Vessel Fit</b> - the reference data behind the engine<br>"
        "&bull; <b>ML Model &amp; Training</b> - model metrics and live retraining<br>"
        "&bull; <b>System Verification</b> - the in-process test battery<br>"
        "&bull; <b>About &amp; Data Governance</b> - methodology and the data register<br><br>"
        "Change the parcel with <b>Edit Cargo</b> in the bar at the top, then <b>Find Best "
        "Strategy</b> to re-run. <b>Report</b> produces a printable summary. The badge beside "
        "the masthead reads LIVE MODEL when figures came from the service, or OFFLINE ESTIMATE "
        "if it fell back to a local approximation.",
        "Using the platform", [],
        ["How are options ranked?", "What do the scenarios do?"])


def _answer_glossary(ports, vessels, context, question):
    lowered = question.lower()
    hits = [(term, meaning) for term, meaning in GLOSSARY.items() if term in lowered]
    if not hits:
        return None
    if len(hits) == 1:
        term, meaning = hits[0]
        return Answer(f"<b>{term.upper() if len(term) <= 4 else term.title()}</b> - {meaning}",
                      "Glossary", [], ["How is the cost built up?", "How are options ranked?"])
    body = "".join(
        f"<br>&bull; <b>{t.upper() if len(t) <= 4 else t.title()}</b> - {m}" for t, m in hits
    )
    return Answer("Terms in your question:" + body, "Glossary", [],
                  ["How is the cost built up?"])


HANDLERS = {
    "vessel_choice": _answer_vessel,
    "port_choice": _answer_port,
    "port_profile": _answer_port,
    "cost_breakdown": _answer_cost,
    "deadfreight": _answer_deadfreight,
    "demurrage": _answer_demurrage,
    "lightering": _answer_lightering,
    "risk": _answer_risk,
    "continuity": _answer_continuity,
    "saving": _answer_saving,
    "ranking": _answer_ranking,
    "model": _answer_model,
    "scenarios": _answer_scenarios,
    "data_sources": _answer_data_sources,
    "security": _answer_security,
    "plants": _answer_plants,
    "origins": _answer_origins,
    "waterways": _answer_waterways,
    "navigation": _answer_navigation,
    "glossary": _answer_glossary,
}

FALLBACK_SUGGESTIONS = [
    "Why was this vessel class selected?",
    "How is the landed cost built up?",
    "How is the risk index calculated?",
    "What happens if a cyclone hits?",
    "Where does the data come from?",
]


def ask(question: str, *, ports, vessels, context=None) -> dict:
    """Answer a question about the platform, grounded in live data."""
    question = (question or "").strip()
    if not question:
        return Answer("Ask me about the recommendation, the ports and vessels behind it, the "
                      "costing, the risk scores, the model, or how to use the platform.",
                      "General", [], FALLBACK_SUGGESTIONS).as_dict()

    if len(question) > 500:
        question = question[:500]

    if _is_probe(question):
        return Answer(REFUSAL, "Refused", [], FALLBACK_SUGGESTIONS).as_dict()

    # Glossary first: a definition question is usually more specific than the
    # broader intent its wording would otherwise match.
    if any(term in question.lower() for term in ("what is", "what does", "meaning", "define")):
        glossary = _answer_glossary(ports, vessels, context, question)
        if glossary:
            return glossary.as_dict()

    lowered = question.lower()

    # Naming a berth or a vessel class settles the topic - these come from the
    # database, so they cannot be listed in the static intent table.
    if any(p.name.lower().split("/")[0] in lowered for p in ports):
        return _answer_port(ports, vessels, context, question).as_dict()
    if any(v.class_type.lower() in lowered for v in vessels):
        return _answer_vessel(ports, vessels, context, question).as_dict()

    intent = classify(question)
    if intent is None:
        return Answer(
            "I do not have a grounded answer for that one. I can cover the recommendation and "
            "why it was chosen, port and vessel characteristics, how each cost line is built, "
            "the risk and continuity scores, the forecasting model, the disruption scenarios, "
            "data provenance, and how to use the platform.",
            "General", [], FALLBACK_SUGGESTIONS).as_dict()

    handler = HANDLERS.get(intent.name)
    answer = handler(ports, vessels, context, question) if handler else None
    if answer is None:
        answer = Answer(
            "I recognised the topic but could not ground an answer in the current data. Try "
            "running a strategy first, or ask a more specific question.",
            intent.topic, [], FALLBACK_SUGGESTIONS)
    return answer.as_dict()
