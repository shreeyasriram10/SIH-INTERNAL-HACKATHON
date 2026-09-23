"""Cargo physics and the rail network behind the decision engine.

Two inputs used to be accepted by the engine and then ignored.

Cargo type only ever reached the explanation text, so coking coal and iron ore
produced identical routes, vessels and freight. But the two load very
differently: a bulk carrier's holds are sized by volume while its deadweight is
a weight limit, and which one binds depends on how dense the cargo is. Iron ore
is dense enough that the ship reaches its deadweight long before the holds are
full; coal is light enough that the holds fill first and the ship cannot lift
its rated deadweight at all. That changes how many tonnes a class can carry,
how many shipments a parcel needs, how deep the ship sits, and therefore which
berths it can reach.

Plant only ever reached the explanation too. The rail leg was stored per port,
as if every plant sat at the same distance from a given berth, so choosing
Bhilai over Durgapur changed nothing. Rail distance is now looked up per
port-and-plant pair.

The figures are representative planning values, not measured survey data, in
keeping with the rest of the platform's synthetic dataset.
"""

# Grain cubic capacity per deadweight tonne for a typical dry-bulk carrier.
VESSEL_CUBIC_M3_PER_DWT = 1.25

# stowage_m3_t  hold volume one tonne occupies
# handling      discharge-rate multiplier against the berth's coal-rated figure
CARGO_PROFILES = {
    "coking_coal":    {"label": "Coking Coal",    "stowage_m3_t": 1.30, "handling": 1.00},
    "thermal_coal":   {"label": "Thermal Coal",   "stowage_m3_t": 1.35, "handling": 1.00},
    "iron_ore_fines": {"label": "Iron Ore Fines", "stowage_m3_t": 0.45, "handling": 1.25},
    "iron_ore_lumps": {"label": "Iron Ore Lumps", "stowage_m3_t": 0.50, "handling": 1.20},
}
DEFAULT_CARGO = "coking_coal"


def cargo_key(cargo_type: str) -> str:
    """Accept either the key ("iron_ore_fines") or the label ("Iron Ore Fines")."""
    text = (cargo_type or "").strip().lower().replace("-", " ").replace("_", " ")
    for key, profile in CARGO_PROFILES.items():
        if text == key.replace("_", " ") or text == profile["label"].lower():
            return key
    if "ore" in text:
        return "iron_ore_lumps" if "lump" in text or "pellet" in text else "iron_ore_fines"
    if "thermal" in text or "steam" in text:
        return "thermal_coal"
    return DEFAULT_CARGO


def cargo_profile(cargo_type: str) -> dict:
    key = cargo_key(cargo_type)
    return {"key": key, **CARGO_PROFILES[key]}


def effective_capacity(capacity_dwt: float, profile: dict) -> float:
    """Tonnes a vessel can actually lift of this cargo: the lower of its
    deadweight and what its holds can take by volume."""
    capacity_dwt = max(float(capacity_dwt), 1.0)
    by_volume = capacity_dwt * VESSEL_CUBIC_M3_PER_DWT / profile["stowage_m3_t"]
    return min(capacity_dwt, by_volume)


def binding_limit(capacity_dwt: float, profile: dict) -> str:
    return "volume" if effective_capacity(capacity_dwt, profile) < capacity_dwt else "weight"


# Rail kilometres from each discharge berth to each integrated steel plant.
PLANT_RAIL_KM = {
    "INPRT": {"rourkela": 440, "bhilai": 720, "durgapur": 560, "bokaro": 540, "burnpur": 530},
    "INDHM": {"rourkela": 400, "bhilai": 760, "durgapur": 450, "bokaro": 470, "burnpur": 430},
    "INGGV": {"rourkela": 710, "bhilai": 580, "durgapur": 1020, "bokaro": 970, "burnpur": 1000},
    "INVTZ": {"rourkela": 690, "bhilai": 560, "durgapur": 1000, "bokaro": 950, "burnpur": 980},
    "INGOP": {"rourkela": 560, "bhilai": 620, "durgapur": 780, "bokaro": 760, "burnpur": 750},
    "INHAL": {"rourkela": 480, "bhilai": 890, "durgapur": 220, "bokaro": 330, "burnpur": 260},
    "INSAG": {"rourkela": 520, "bhilai": 930, "durgapur": 260, "bokaro": 370, "burnpur": 300},
}
PLANTS = ("rourkela", "bhilai", "durgapur", "bokaro", "burnpur")


def plant_key(plant: str) -> str | None:
    """Accept "rourkela", "Rourkela Steel Plant (RSP)", "IISCO Steel Plant (ISP)"."""
    text = (plant or "").lower()
    if "iisco" in text or "burnpur" in text:
        return "burnpur"
    for key in PLANTS:
        if key in text:
            return key
    return None


def rail_km(port, plant: str) -> float:
    """Distance for this berth-and-plant pair, falling back to the berth's
    generic figure only when the pair is not in the table."""
    key = plant_key(plant)
    by_plant = PLANT_RAIL_KM.get(getattr(port, "code", ""), {})
    if key and key in by_plant:
        return float(by_plant[key])
    return float(getattr(port, "rail_evac_km", 0.0) or 0.0)


# Cargo price at the load port (FOB, USD per tonne), per cargo and origin.
#
# Without this the engine compared origins on logistics alone. The cargo was
# priced the same wherever it came from, so the shortest haul always won:
# every coking-coal parcel went to Richards Bay, although South Africa ships
# little coking coal and its semi-soft grades take more tonnes to make the same
# coke. The cargo price differs between origins by more than the freight does,
# so an origin can only be chosen on delivered cost.
#
# Figures are indicative of recent index levels and quality-adjusted to one
# reference specification per cargo (a tonne of a weaker grade costs more per
# tonne of equivalent quality). They are synthetic planning values like the
# rest of the dataset - replace them with contract prices in production.
COMMODITY_FOB_USD_MT = {
    "coking_coal":    {"Australia": 232.0, "USA": 214.0, "South Africa": 241.0, "Indonesia": 250.0},
    "thermal_coal":   {"Indonesia": 84.0, "South Africa": 98.0, "Australia": 121.0, "USA": 104.0},
    "iron_ore_fines": {"Australia": 104.0, "South Africa": 109.0, "USA": 112.0, "Indonesia": 112.0},
    "iron_ore_lumps": {"Australia": 118.0, "South Africa": 121.0, "USA": 126.0, "Indonesia": 126.0},
}
FOB_BASIS = ("Indicative FOB, quality-adjusted to a reference specification per cargo; "
             "synthetic planning values, not contract prices.")


def fob_usd_mt(cargo_type: str, origin: str) -> float:
    """FOB price for this cargo from this origin; the cargo's highest listed
    price when the origin is not in the table, so an unknown lane is never
    made to look cheap."""
    prices = COMMODITY_FOB_USD_MT[cargo_key(cargo_type)]
    for name, price in prices.items():
        if name.lower() == (origin or "").strip().lower():
            return price
    return max(prices.values())


# ---------------------------------------------------------------------------
# Vessel principal dimensions
# ---------------------------------------------------------------------------
# Typical LOA and beam per class, used when a vessel row predates the loa_m /
# beam_m columns. Checked against every berth's LOA and beam limit.
CLASS_DIMENSIONS = {
    "handysize": {"loa_m": 180.0, "beam_m": 28.0},
    "supramax":  {"loa_m": 199.9, "beam_m": 32.3},
    "panamax":   {"loa_m": 225.0, "beam_m": 32.3},
    "capesize":  {"loa_m": 292.0, "beam_m": 45.0},
}


def vessel_dimensions(vessel) -> tuple:
    """(LOA, beam) in metres for a vessel row, falling back to its class."""
    fallback = CLASS_DIMENSIONS.get(str(getattr(vessel, "class_type", "")).strip().lower(), {})
    loa = getattr(vessel, "loa_m", None) or fallback.get("loa_m") or 0.0
    beam = getattr(vessel, "beam_m", None) or fallback.get("beam_m") or 0.0
    return float(loa), float(beam)


# ---------------------------------------------------------------------------
# Origin load ports
# ---------------------------------------------------------------------------
# The engine used to treat an origin as a country, so nothing stopped it
# sending a ship to a load port that could not take her. Each origin now loads
# at a named terminal with its own draft, length and beam limits, loading rate
# and typical queue (drafts are tidal-window sailing drafts). Representative planning values, in keeping with the rest
# of the dataset - replace with terminal handbooks in production.
LOAD_PORTS = {
    "Australia": {
        "coal":    {"name": "Hay Point / Dalrymple Bay (QLD)", "code": "AUHPT", "draft_m": 18.5,
                    "max_loa": 300.0, "max_beam_m": 50.0, "load_rate_mt_d": 55000.0, "avg_wait_days": 5.5},
        "thermal": {"name": "Newcastle (NSW)", "code": "AUNTL", "draft_m": 16.0,
                    "max_loa": 300.0, "max_beam_m": 50.0, "load_rate_mt_d": 70000.0, "avg_wait_days": 3.5},
        "ore":     {"name": "Port Hedland (WA)", "code": "AUPHE", "draft_m": 18.9,
                    "max_loa": 330.0, "max_beam_m": 58.0, "load_rate_mt_d": 120000.0, "avg_wait_days": 1.5},
    },
    "Indonesia": {
        "coal":    {"name": "Taboneo anchorage (South Kalimantan)", "code": "IDTBO", "draft_m": 22.0,
                    "max_loa": 330.0, "max_beam_m": 60.0, "load_rate_mt_d": 15000.0, "avg_wait_days": 2.5},
        "ore":     {"name": "Taboneo anchorage (South Kalimantan)", "code": "IDTBO", "draft_m": 22.0,
                    "max_loa": 330.0, "max_beam_m": 60.0, "load_rate_mt_d": 15000.0, "avg_wait_days": 2.5},
    },
    "South Africa": {
        "coal":    {"name": "Richards Bay Coal Terminal", "code": "ZARCB", "draft_m": 19.0,
                    "max_loa": 300.0, "max_beam_m": 50.0, "load_rate_mt_d": 65000.0, "avg_wait_days": 3.0},
        "ore":     {"name": "Saldanha Bay", "code": "ZASDB", "draft_m": 21.5,
                    "max_loa": 360.0, "max_beam_m": 65.0, "load_rate_mt_d": 100000.0, "avg_wait_days": 2.0},
    },
    "USA": {
        "coal":    {"name": "Hampton Roads (Norfolk, VA)", "code": "USORF", "draft_m": 15.2,
                    "max_loa": 300.0, "max_beam_m": 50.0, "load_rate_mt_d": 45000.0, "avg_wait_days": 4.0},
        "ore":     {"name": "Baltimore (MD)", "code": "USBAL", "draft_m": 15.2,
                    "max_loa": 300.0, "max_beam_m": 50.0, "load_rate_mt_d": 40000.0, "avg_wait_days": 3.0},
    },
}
LOAD_PORT_BASIS = ("Representative terminal limits and loading rates; synthetic planning "
                   "values, not terminal handbook figures.")


def load_port(origin: str, cargo_type: str) -> dict | None:
    """The terminal this cargo loads at from this origin, or None for an
    origin the table does not know (no constraint is invented for it)."""
    terminals = None
    for name, table in LOAD_PORTS.items():
        if name.lower() == (origin or "").strip().lower():
            terminals = table
            break
    if not terminals:
        return None
    key = cargo_key(cargo_type)
    family = "ore" if key.startswith("iron_ore") else ("thermal" if key == "thermal_coal" else "coal")
    return terminals.get(family) or terminals.get("coal")


# ---------------------------------------------------------------------------
# Berth congestion by month
# ---------------------------------------------------------------------------
# The engine used a single average queue per berth all year round. Queues on
# the east coast are seasonal: monsoon weather stops cargo work, the month
# after it clears the backlog, and Jan-Mar carries the financial-year-end
# import push. Each factor is a planning assumption, stated here so it can be
# challenged and replaced with berth-occupancy data.
CONGESTION_FACTORS = {
    "monsoon": 1.35,          # berth lists this month as weather-affected
    "post_monsoon": 1.15,     # first month after the berth's monsoon season
    "fy_end_rush": 1.10,      # January-March import push
}


def _monsoon_months(port) -> list:
    return [int(m) for m in str(getattr(port, "monsoon_months", "") or "").split(",")
            if m.strip().isdigit()]


def congestion_factor(port, month: int) -> tuple:
    """(multiplier, reason) for this berth's queue in this month."""
    months = _monsoon_months(port)
    if month in months:
        return CONGESTION_FACTORS["monsoon"], "monsoon weather downtime"
    if months and month == (max(months) % 12) + 1:
        return CONGESTION_FACTORS["post_monsoon"], "post-monsoon backlog"
    if month in (1, 2, 3):
        return CONGESTION_FACTORS["fy_end_rush"], "financial-year-end import rush"
    return 1.0, "normal"


def forecast_wait_days(port, month: int) -> float:
    """Expected berth queue, in days, for one arrival in the given month."""
    factor, _ = congestion_factor(port, month)
    return float(getattr(port, "avg_wait_days", 0.0) or 0.0) * factor