from fastapi import APIRouter, HTTPException
from typing import Any

router = APIRouter()

# Each route is a chain of [lat, lon] waypoints that stays at sea: along the
# canal axis, the strait's navigation channel or the ocean lane. The map joins
# them with straight segments, so a route drawn from its end ports alone cut
# across land. The Pacific route runs west across the date line, so its Asian
# waypoints carry longitudes below -180 to keep the line continuous.
WATERWAYS: list[dict[str, Any]] = [
    {"id": "suez-canal", "name": "Suez Canal", "region": "North Africa / Red Sea", "countries": "Egypt", "type": "Canal", "length_km": 193, "importance": "Shortest sea link between Europe and Asia; critical Europe-Asia container corridor.", "ports": ["Port Said", "Suez", "Jeddah"], "traffic": "HIGH", "coordinates": [[31.3, 32.33], [31.1, 32.31], [30.75, 32.31], [30.57, 32.29], [30.33, 32.4], [30.18, 32.48], [29.95, 32.56], [29.85, 32.57]]},
    {"id": "panama-canal", "name": "Panama Canal", "region": "Central America", "countries": "Panama", "type": "Canal", "length_km": 82, "importance": "Connects Atlantic and Pacific trade lanes and reduces the Cape Horn detour.", "ports": ["Cristobal", "Balboa", "Colon"], "traffic": "HIGH", "coordinates": [[9.38, -79.92], [9.27, -79.92], [9.2, -79.86], [9.12, -79.78], [9.11, -79.7], [9.05, -79.66], [9.02, -79.61], [9.0, -79.59], [8.95, -79.56], [8.88, -79.52]]},
    {"id": "strait-of-malacca", "name": "Strait of Malacca", "region": "Southeast Asia", "countries": "Malaysia / Indonesia / Singapore", "type": "International Strait", "length_km": 800, "importance": "Primary Indian Ocean-Pacific gateway and one of the world's busiest shipping corridors.", "ports": ["Singapore", "Port Klang", "Tanjung Pelepas"], "traffic": "HIGH", "coordinates": [[5.9, 95.3], [5.3, 97.5], [4.4, 99.2], [3.2, 100.6], [2.4, 101.6], [1.6, 102.9], [1.2, 103.55]]},
    {"id": "strait-of-hormuz", "name": "Strait of Hormuz", "region": "Persian Gulf", "countries": "Iran / Oman / United Arab Emirates", "type": "International Strait", "length_km": 167, "importance": "Strategic energy chokepoint linking the Persian Gulf with the Gulf of Oman.", "ports": ["Jebel Ali", "Bandar Abbas", "Fujairah"], "traffic": "HIGH", "coordinates": [[26.4, 55.3], [26.5, 56.1], [26.58, 56.45], [26.3, 56.8], [25.8, 57.1]]},
    {"id": "bab-el-mandeb", "name": "Bab-el-Mandeb", "region": "Red Sea / Gulf of Aden", "countries": "Yemen / Djibouti / Eritrea", "type": "International Strait", "length_km": 32, "importance": "Gateway between the Red Sea and Gulf of Aden on the Asia-Europe route.", "ports": ["Djibouti", "Aden", "Port Sudan"], "traffic": "HIGH", "coordinates": [[13.3, 42.9], [12.75, 43.25], [12.55, 43.35], [12.35, 43.6], [12.1, 44.0]]},
    {"id": "english-channel", "name": "English Channel", "region": "Northwest Europe", "countries": "United Kingdom / France", "type": "International Strait", "length_km": 560, "importance": "Dense European short-sea and North Atlantic approach corridor.", "ports": ["Port of Dover", "Le Havre", "Southampton"], "traffic": "HIGH", "coordinates": [[51.05, 1.45], [50.75, 0.5], [50.45, -0.8], [50.2, -2.5], [49.9, -4.5], [49.5, -5.8]]},
    {"id": "bosporus", "name": "Bosporus Strait", "region": "Türkiye / Black Sea", "countries": "Türkiye", "type": "International Strait", "length_km": 31, "importance": "Connects the Black Sea with the Sea of Marmara and Mediterranean trade network.", "ports": ["Istanbul", "Mersin", "Constanta"], "traffic": "MODERATE", "coordinates": [[41.235, 29.145], [41.212, 29.125], [41.19, 29.1], [41.178, 29.083], [41.15, 29.075], [41.122, 29.083], [41.102, 29.061], [41.084, 29.061], [41.07, 29.052], [41.055, 29.04], [41.045, 29.03], [41.033, 29.012], [41.02, 29.0], [41.005, 28.985], [40.985, 28.975]]},
    {"id": "singapore-strait", "name": "Singapore Strait", "region": "Southeast Asia", "countries": "Singapore / Indonesia", "type": "International Strait", "length_km": 105, "importance": "Critical approach to Singapore transshipment hub and Malacca route.", "ports": ["Singapore", "Batam", "Tanjung Pelepas"], "traffic": "HIGH", "coordinates": [[1.2, 103.55], [1.18, 103.75], [1.23, 103.95], [1.25, 104.15], [1.3, 104.4]]},
    {"id": "danish-straits", "name": "Danish Straits", "region": "Baltic Sea / North Sea", "countries": "Denmark / Sweden", "type": "International Strait", "length_km": 150, "importance": "Controls maritime access between the Baltic Sea and North Sea.", "ports": ["Copenhagen", "Gothenburg", "Gdansk"], "traffic": "MODERATE", "coordinates": [[56.3, 12.25], [56.05, 12.63], [55.9, 12.7], [55.72, 12.72], [55.55, 12.73], [55.3, 12.8], [54.95, 13.0]]},
    {"id": "gibraltar-strait", "name": "Gibraltar Strait", "region": "Western Mediterranean", "countries": "Spain / Morocco", "type": "International Strait", "length_km": 60, "importance": "Atlantic-Mediterranean gateway for Europe, Africa, and Asia trade.", "ports": ["Algeciras", "Tangier Med", "Gibraltar"], "traffic": "HIGH", "coordinates": [[36.0, -6.2], [35.97, -5.75], [35.97, -5.45], [36.05, -5.2], [36.15, -4.9]]},
    {"id": "cape-of-good-hope", "name": "Cape of Good Hope Route", "region": "Southern Africa", "countries": "South Africa", "type": "Strategic Route", "length_km": 450, "importance": "Alternative southern route around Africa when Red Sea access is constrained.", "ports": ["Cape Town", "Durban", "Port Elizabeth"], "traffic": "MODERATE", "coordinates": [[-33.8, 18.35], [-34.3, 18.2], [-34.9, 19.0], [-35.1, 20.0], [-34.4, 23.0], [-34.1, 25.8], [-33.3, 27.8], [-31.5, 30.3], [-29.9, 31.1]]},
    {"id": "indian-ocean-route", "name": "Major Indian Ocean Shipping Route", "region": "Indian Ocean", "countries": "India / Sri Lanka / Oman / Singapore", "type": "Shipping Route", "length_km": 5200, "importance": "Connects Indian manufacturing and energy markets with Europe and East Asia.", "ports": ["Chennai", "Colombo", "Mumbai", "Singapore"], "traffic": "HIGH", "coordinates": [[18.9, 72.7], [15.0, 72.6], [10.0, 74.8], [7.5, 77.2], [6.9, 79.6], [5.75, 80.3], [5.9, 82.5], [6.0, 90.0], [6.2, 95.0], [5.3, 97.5], [4.4, 99.2], [3.2, 100.6], [2.4, 101.6], [1.6, 102.9], [1.2, 103.55]]},
    {"id": "pacific-route", "name": "Major Pacific Shipping Route", "region": "North Pacific", "countries": "United States / Japan / China", "type": "Shipping Route", "length_km": 8500, "importance": "Core Asia-Pacific container and bulk trade corridor.", "ports": ["Los Angeles", "Yokohama", "Shanghai"], "traffic": "HIGH", "coordinates": [[33.72, -118.27], [33.5, -120.0], [38.0, -130.0], [44.0, -150.0], [47.0, -170.0], [47.0, -190.0], [43.0, -205.0], [35.3, -219.0], [34.75, -219.75], [34.9, -220.2], [34.3, -221.0], [33.3, -224.0], [32.4, -227.0], [31.2, -228.2], [30.88, -229.2], [30.75, -229.7], [30.8, -231.0], [31.1, -236.5], [31.25, -237.8]]},
    {"id": "atlantic-route", "name": "Major Atlantic Shipping Route", "region": "North Atlantic", "countries": "United States / Canada / United Kingdom", "type": "Shipping Route", "length_km": 5600, "importance": "High-volume transatlantic container, Ro-Ro, and energy corridor.", "ports": ["New York", "Rotterdam", "Felixstowe"], "traffic": "HIGH", "coordinates": [[40.5, -73.8], [40.3, -70.0], [41.5, -60.0], [45.0, -45.0], [48.5, -25.0], [49.5, -10.0], [49.8, -5.5], [50.3, -1.5], [51.0, 1.5], [51.9, 3.5], [51.98, 4.05]]},
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
