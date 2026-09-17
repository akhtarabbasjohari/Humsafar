"""
Pricing Calculation & Cost Modeling Service for Humsafar.
Guarantees concrete, realistic dual-currency pricing (PKR & USD) with itemized cost breakdowns
across all regions (Gilgit-Baltistan, KPK, Sindh, Balochistan, Punjab, Kashmir, and International).
Mandates that 'Pricing upon inquiry' is NEVER displayed to travelers.
"""

from typing import Dict, Any, Optional, List
import re


def calculate_realistic_tour_pricing(
    title: str,
    destination: str,
    duration_days: int = 7,
    party_size: int = 2,
    existing_price: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculates realistic market pricing for any tour or expedition in PKR and USD,
    ensuring 'Pricing upon inquiry' is NEVER displayed.
    Provides itemized cost breakdowns (transport, guide, porters, permits, accommodation, meals).
    """
    # If a concrete numeric price already exists (not "upon inquiry"), preserve and format
    if existing_price:
        clean_p = str(existing_price).strip()
        lower_p = clean_p.lower()
        if "inquiry" not in lower_p and "contact" not in lower_p and "tbd" not in lower_p:
            if "pkr" in lower_p or "$" in clean_p or any(c.isdigit() for c in clean_p):
                return {
                    "price": clean_p,
                    "pricing_breakdown": {
                        "total_range": clean_p,
                        "basis": f"Confirmed official catalog rate for party of {party_size}",
                        "items": [
                            {"category": "Official Package Rate", "cost": clean_p, "usd": "Included"},
                        ],
                    }
                }

    combined = f"{title} {destination}".lower()
    days = max(int(duration_days) if duration_days else 7, 1)

    # 0. High-Altitude Peak Climbing Expeditions (8,000m / 7,000m / 6,000m Summits)
    is_climbing_expedition = (
        any(k in combined for k in ["expedition", "climb", "summit", "mountaineer", "8611", "8051", "8000m", "7000m"])
        and any(k in combined for k in ["k2", "broad peak", "gasherbrum", "spantik", "nanga parbat", "masherbrum", "latok", "passu peak", "khosar gang", "peak", "expedition"])
        and "base camp trek" not in combined
        and "concordia trek" not in combined
    )

    if is_climbing_expedition:
        daily_min_pkr = 36000
        daily_max_pkr = 48000
        transport_pct = 0.15
        guide_pct = 0.20
        porters_pct = 0.28
        meals_pct = 0.15
        permits_pct = 0.16
        hotels_pct = 0.06

    # 1. Glacier & High-Altitude Wilderness Treks (K2 Base Camp, Concordia, Baltoro, Gondogoro La, Snow Lake, etc.)
    elif any(k in combined for k in [
        "k2", "concordia", "baltoro", "gondogoro", "broad peak", "gasherbrum",
        "spantik", "nanga parbat", "snow lake", "biafo", "hispar", "trango",
        "trek", "glacier"
    ]):
        daily_min_pkr = 22000
        daily_max_pkr = 26000
        transport_pct = 0.22
        guide_pct = 0.18
        porters_pct = 0.25
        meals_pct = 0.18
        permits_pct = 0.10
        hotels_pct = 0.07

    # 2. Alpine Valley & Plateau Treks (Gilgit-Baltistan, KPK, Swat, Chitral, Hushe, Nangma, Deosai)
    elif any(k in combined for k in [
        "deosai", "fairy meadows", "nangma", "hushe", "shimshal", "rush lake",
        "rakaposhi", "passu", "chitral", "kalash", "kumrat", "swat", "kalam",
        "trek", "valley", "lake", "pass", "plateau"
    ]):
        daily_min_pkr = 18000
        daily_max_pkr = 23000
        transport_pct = 0.28
        guide_pct = 0.20
        porters_pct = 0.15
        meals_pct = 0.18
        permits_pct = 0.07
        hotels_pct = 0.12

    # 3. Sindh, Coastal & Desert Heritage Tours (Karachi, Gorakh Hill, Mohenjo-daro, Makran, Gwadar, Thar)
    elif any(k in combined for k in [
        "karachi", "sindh", "gorakh", "mohenjo", "thatta", "makran",
        "gwadar", "thar", "coastal", "beach"
    ]):
        daily_min_pkr = 14000
        daily_max_pkr = 19000
        transport_pct = 0.35
        guide_pct = 0.18
        porters_pct = 0.05
        meals_pct = 0.22
        permits_pct = 0.05
        hotels_pct = 0.15

    # 4. International Travel Destinations (Paris, Nepal, Turkey, Dubai, etc.)
    elif any(k in combined for k in [
        "paris", "tokyo", "dubai", "london", "nepal", "turkey", "everest",
        "kilimanjaro", "alps", "switzerland", "iceland", "international"
    ]):
        daily_min_pkr = 39000
        daily_max_pkr = 53000
        transport_pct = 0.30
        guide_pct = 0.20
        porters_pct = 0.08
        meals_pct = 0.22
        permits_pct = 0.05
        hotels_pct = 0.15

    # 5. Cultural, Road & Sightseeing Tours (Hunza, Skardu, Lahore, Islamabad, etc.)
    else:
        daily_min_pkr = 16000
        daily_max_pkr = 21000
        transport_pct = 0.32
        guide_pct = 0.20
        porters_pct = 0.08
        meals_pct = 0.20
        permits_pct = 0.05
        hotels_pct = 0.15

    total_min_pkr = int(days * daily_min_pkr)
    total_max_pkr = int(days * daily_max_pkr)

    from services.travel_constants import USD_TO_PKR_RATE
    pkr_usd_rate = USD_TO_PKR_RATE
    min_usd = int(round(total_min_pkr / pkr_usd_rate / 10.0) * 10)
    max_usd = int(round(total_max_pkr / pkr_usd_rate / 10.0) * 10)

    price_str = f"PKR {total_min_pkr:,} – {total_max_pkr:,} (${min_usd:,} – ${max_usd:,} USD)"

    breakdown_list = [
        {
            "category": "Private 4x4 Mountain Transport & Transfers",
            "cost": f"PKR {int(total_min_pkr * transport_pct):,} – {int(total_max_pkr * transport_pct):,}",
            "usd": f"${int(min_usd * transport_pct)} – ${int(max_usd * transport_pct)}",
        },
        {
            "category": "Licensed Mountain Guide & Expedition Leaders",
            "cost": f"PKR {int(total_min_pkr * guide_pct):,} – {int(total_max_pkr * guide_pct):,}",
            "usd": f"${int(min_usd * guide_pct)} – ${int(max_usd * guide_pct)}",
        },
        {
            "category": "High Altitude Porters (HAPs), Base Camp Staff & Fixed Line Crew" if is_climbing_expedition else "Local Porters / Camp Logistics Crew",
            "cost": f"PKR {int(total_min_pkr * porters_pct):,} – {int(total_max_pkr * porters_pct):,}",
            "usd": f"${int(min_usd * porters_pct)} – ${int(max_usd * porters_pct)}",
        },
        {
            "category": "All Nutritious Trail & Camp Meals (Breakfast, Lunch, Dinner)",
            "cost": f"PKR {int(total_min_pkr * meals_pct):,} – {int(total_max_pkr * meals_pct):,}",
            "usd": f"${int(min_usd * meals_pct)} – ${int(max_usd * meals_pct)}",
        },
        {
            "category": "Climbing Royalty Fees, Liaison Officer & Environmental Bonds" if is_climbing_expedition else "National Park Permits, Trekking Fees & Environmental Bonds",
            "cost": f"PKR {int(total_min_pkr * permits_pct):,} – {int(total_max_pkr * permits_pct):,}",
            "usd": f"${int(min_usd * permits_pct)} – ${int(max_usd * permits_pct)}",
        },
        {
            "category": "Staging Hotels, Base Camp Mess/Tents & High Camp Altitude Tents" if is_climbing_expedition else "Staging Hotel Stays & 2-Person Expedition Tents",
            "cost": f"PKR {int(total_min_pkr * hotels_pct):,} – {int(total_max_pkr * hotels_pct):,}",
            "usd": f"${int(min_usd * hotels_pct)} – ${int(max_usd * hotels_pct)}",
        },
    ]

    return {
        "price": price_str,
        "min_pkr": total_min_pkr,
        "max_pkr": total_max_pkr,
        "min_usd": min_usd,
        "max_usd": max_usd,
        "daily_rate": f"PKR {daily_min_pkr:,} – {daily_max_pkr:,} / day",
        "pricing_breakdown": {
            "total_range": price_str,
            "basis": f"Estimated realistic market rate per person for party of {party_size} ({days} Days)",
            "party_size": party_size,
            "duration_days": days,
            "items": breakdown_list,
        },
    }
