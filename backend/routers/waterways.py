from fastapi import APIRouter, HTTPException
from typing import Any

router = APIRouter()

WATERWAYS: list[dict[str, Any]] = [
    {"id": "suez-canal", "name": "Suez Canal", "region": "North Africa / Red Sea", "countries": "Egypt", "type": "Canal", "length_km": 193, "importance": "Shortest sea link between Europe and Asia; critical Europe-Asia container corridor.", "ports": ["Port Said", "Suez", "Jeddah"], "traffic": "HIGH", "coordinates": [[31.26, 32.31], [30.59, 32.27], [29.95, 32.55]]},
    {"id": "panama-canal", "name": "Panama Canal", "region": "Central America", "countries": "Panama", "type": "Canal", "length_km": 82, "importance": "Connects Atlantic and Pacific trade lanes and reduces the Cape Horn detour.", "ports": ["Cristobal", "Balboa", "Colon"], "traffic": "HIGH", "coordinates": [[9.31, -79.92], [9.08, -79.68], [8.95, -79.56]]},
    {"id": "strait-of-malacca", "name": "Strait of Malacca", "region": "Southeast Asia", "countries": "Malaysia / Indonesia / Singapore", "type": "International Strait", "length_km": 800, "importance": "Primary Indian Ocean-Pacific gateway and one of the world's busiest shipping corridors.", "ports": ["Singapore", "Port Klang", "Tanjung Pelepas"], "traffic": "HIGH", "coordinates": [[5.88, 95.32], [3.25, 100.75], [1.25, 103.85]]},
    {"id": "strait-of-hormuz", "name": "Strait of Hormuz", "region": "Persian Gulf", "countries": "Iran / Oman / United Arab Emirates", "type": "International Strait", "length_km": 167, "importance": "Strategic energy chokepoint linking the Persian Gulf with the Gulf of Oman.", "ports": ["Jebel Ali", "Bandar Abbas", "Fujairah"], "traffic": "HIGH", "coordinates": [[26.58, 56.25], [26.35, 56.55], [26.15, 57.05]]},
    {"id": "bab-el-mandeb", "name": "Bab-el-Mandeb", "region": "Red Sea / Gulf of Aden", "countries": "Yemen / Djibouti / Eritrea", "type": "International Strait", "length_km": 32, "importance": "Gateway between the Red Sea and Gulf of Aden on the Asia-Europe route.", "ports": ["Djibouti", "Aden", "Port Sudan"], "traffic": "HIGH", "coordinates": [[12.65, 43.35], [12.55, 43.15], [12.45, 43.05]]},
    {"id": "english-channel", "name": "English Channel", "region": "Northwest Europe", "countries": "United Kingdom / France", "type": "International Strait", "length_km": 560, "importance": "Dense European short-sea and North Atlantic approach corridor.", "ports": ["Port of Dover", "Le Havre", "Southampton"], "traffic": "HIGH", "coordinates": [[50.95, -1.45], [50.65, -0.25], [50.25, 1.15]]},
    {"id": "bosporus", "name": "Bosporus Strait", "region": "Türkiye / Black Sea", "countries": "Türkiye", "type": "International Strait", "length_km": 31, "importance": "Connects the Black Sea with the Sea of Marmara and Mediterranean trade network.", "ports": ["Istanbul", "Mersin", "Constanta"], "traffic": "MODERATE", "coordinates": [[41.25, 29.05], [41.08, 29.06], [40.95, 29.10]]},
    {"id": "singapore-strait", "name": "Singapore Strait", "region": "Southeast Asia", "countries": "Singapore / Indonesia", "type": "International Strait", "length_km": 105, "importance": "Critical approach to Singapore transshipment hub and Malacca route.", "ports": ["Singapore", "Batam", "Tanjung Pelepas"], "traffic": "HIGH", "coordinates": [[1.35, 103.65], [1.18, 104.05], [1.02, 104.35]]},
    {"id": "danish-straits", "name": "Danish Straits", "region": "Baltic Sea / North Sea", "countries": "Denmark / Sweden", "type": "International Strait", "length_km": 150, "importance": "Controls maritime access between the Baltic Sea and North Sea.", "ports": ["Copenhagen", "Gothenburg", "Gdansk"], "traffic": "MODERATE", "coordinates": [[56.10, 12.55], [55.65, 12.60], [54.95, 12.15]]},
    {"id": "gibraltar-strait", "name": "Gibraltar Strait", "region": "Western Mediterranean", "countries": "Spain / Morocco", "type": "International Strait", "length_km": 60, "importance": "Atlantic-Mediterranean gateway for Europe, Africa, and Asia trade.", "ports": ["Algeciras", "Tangier Med", "Gibraltar"], "traffic": "HIGH", "coordinates": [[36.15, -5.95], [35.98, -5.55], [35.90, -5.35]]},
    {"id": "cape-of-good-hope", "name": "Cape of Good Hope Route", "region": "Southern Africa", "countries": "South Africa", "type": "Strategic Route", "length_km": 450, "importance": "Alternative southern route around Africa when Red Sea access is constrained.", "ports": ["Cape Town", "Durban", "Port Elizabeth"], "traffic": "MODERATE", "coordinates": [[-33.90, 18.35], [-34.20, 22.00], [-29.85, 31.05]]},
    {"id": "indian-ocean-route", "name": "Major Indian Ocean Shipping Route", "region": "Indian Ocean", "countries": "India / Sri Lanka / Oman / Singapore", "type": "Shipping Route", "length_km": 5200, "importance": "Connects Indian manufacturing and energy markets with Europe and East Asia.", "ports": ["Chennai", "Colombo", "Mumbai", "Singapore"], "traffic": "HIGH", "coordinates": [[13.08, 80.29], [6.93, 79.85], [1.25, 103.85]]},
    {"id": "pacific-route", "name": "Major Pacific Shipping Route", "region": "North Pacific", "countries": "United States / Japan / China", "type": "Shipping Route", "length_km": 8500, "importance": "Core Asia-Pacific container and bulk trade corridor.", "ports": ["Los Angeles", "Yokohama", "Shanghai"], "traffic": "HIGH", "coordinates": [[33.74, -118.27], [35.45, 139.65], [31.23, 121.47]]},
    {"id": "atlantic-route", "name": "Major Atlantic Shipping Route", "region": "North Atlantic", "countries": "United States / Canada / United Kingdom", "type": "Shipping Route", "length_km": 5600, "importance": "High-volume transatlantic container, Ro-Ro, and energy corridor.", "ports": ["New York", "Rotterdam", "Felixstowe"], "traffic": "HIGH", "coordinates": [[40.67, -74.05], [45.00, -35.00], [51.95, 4.14]]},
]

VESSELS: list[dict[str, Any]] = [
    {"id": "vessel-imo-1", "name": "MV SAIL Horizon", "mmsi": "419001234", "imo": "9123456", "flag": "India", "type": "Cargo", "speed_knots": 13.4, "heading": 92, "destination": "Singapore", "eta": "2026-09-05 06:00 UTC", "last_update": "2026-09-04 10:18 UTC", "position": [1.30, 103.20], "waterway_id": "singapore-strait"},
    {"id": "vessel-imo-2", "name": "Ocean Meridian", "mmsi": "563778901", "imo": "9234567", "flag": "Singapore", "type": "Container", "speed_knots": 17.1, "heading": 305, "destination": "Rotterdam", "eta": "2026-09-13 18:00 UTC", "last_update": "2026-09-04 10:15 UTC", "position": [35.95, -5.65], "waterway_id": "gibraltar-strait"},
    {"id": "vessel-imo-3", "name": "Eastern Fortune", "mmsi": "477112908", "imo": "9345678", "flag": "Hong Kong", "type": "Tanker", "speed_knots": 11.8, "heading": 180, "destination": "Jebel Ali", "eta": "2026-09-05 20:00 UTC", "last_update": "2026-09-04 10:12 UTC", "position": [26.30, 56.70], "waterway_id": "strait-of-hormuz"},
    {"id": "vessel-imo-4", "name": "Capesize Atlas", "mmsi": "636019876", "imo": "9456789", "flag": "Liberia", "type": "Cargo", "speed_knots": 12.6, "heading": 118, "destination": "Port Klang", "eta": "2026-09-05 11:00 UTC", "last_update": "2026-09-04 10:09 UTC", "position": [3.65, 99.40], "waterway_id": "strait-of-malacca"},
    {"id": "vessel-imo-5", "name": "Blue Bengal", "mmsi": "419445677", "imo": "9567890", "flag": "India", "type": "Cargo", "speed_knots": 14.2, "heading": 275, "destination": "Port Said", "eta": "2026-09-06 02:00 UTC", "last_update": "2026-09-04 10:05 UTC", "position": [29.70, 32.40], "waterway_id": "suez-canal"},
    {"id": "vessel-imo-6", "name": "Pacific Link", "mmsi": "367901234", "imo": "9678901", "flag": "United States", "type": "Container", "speed_knots": 18.3, "heading": 250, "destination": "Balboa", "eta": "2026-09-05 15:00 UTC", "last_update": "2026-09-04 10:02 UTC", "position": [9.12, -79.70], "waterway_id": "panama-canal"},
    {"id": "vessel-imo-7", "name": "North Sea Trader", "mmsi": "244998877", "imo": "9789012", "flag": "Netherlands", "type": "Tanker", "speed_knots": 10.4, "heading": 65, "destination": "Copenhagen", "eta": "2026-09-04 22:00 UTC", "last_update": "2026-09-04 09:58 UTC", "position": [55.60, 12.58], "waterway_id": "danish-straits"},
    {"id": "vessel-imo-8", "name": "Indian Ocean Star", "mmsi": "419556688", "imo": "9890123", "flag": "India", "type": "Passenger", "speed_knots": 19.2, "heading": 145, "destination": "Colombo", "eta": "2026-09-04 18:00 UTC", "last_update": "2026-09-04 09:54 UTC", "position": [8.90, 80.10], "waterway_id": "indian-ocean-route"},
]


def _source() -> str:
    return "SYNTHETIC"


def _with_status(item: dict[str, Any]) -> dict[str, Any]:
    result = dict(item)
    result["data_source"] = _source()
    result["vessel_count"] = sum(v["waterway_id"] == item["id"] for v in VESSELS)
    result["traffic"] = "HIGH" if result["vessel_count"] >= 2 else "MODERATE" if result["vessel_count"] == 1 else "LOW"
    return result


@router.get("")
def list_waterways() -> dict[str, Any]:
    return {"data_source": _source(), "waterways": [_with_status(item) for item in WATERWAYS], "vessels": VESSELS}


@router.get("/{waterway_id}")
def get_waterway(waterway_id: str) -> dict[str, Any]:
    item = next((waterway for waterway in WATERWAYS if waterway["id"] == waterway_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Waterway not found")
    result = _with_status(item)
    result["vessels"] = [v for v in VESSELS if v["waterway_id"] == waterway_id]
    return result


@router.get("/{waterway_id}/vessels")
def get_waterway_vessels(waterway_id: str) -> dict[str, Any]:
    if not any(waterway["id"] == waterway_id for waterway in WATERWAYS):
        raise HTTPException(status_code=404, detail="Waterway not found")
    return {"data_source": _source(), "waterway_id": waterway_id, "vessels": [v for v in VESSELS if v["waterway_id"] == waterway_id]}


@router.get("/vessels/all")
def get_all_waterway_vessels() -> dict[str, Any]:
    return {"data_source": _source(), "vessels": VESSELS}
