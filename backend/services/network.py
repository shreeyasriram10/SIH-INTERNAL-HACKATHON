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
