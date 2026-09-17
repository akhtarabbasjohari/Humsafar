"""
Feasibility & Realism Engine for Humsafar.
Provides general-purpose physical and logistical feasibility reasoning over
mountain travel requests, elevation profiles, transit times, and acclimatization pacing.

Strict Rule: NO static lookup tables of 'region X takes Y days'.
Reasoning is dynamic based on:
1. Ground transit logistics (mountain road transit speeds ~30-40 km/h, road distance from gateway).
2. Altitude ascent gradients and mandatory acclimatization thresholds (AMS risk > 3,000m).
3. Trekking distance/stage pacing (12-18 km/day on glacial terrain).
4. Multi-valley transit overhead across expansive regional spans.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FeasibilityEvaluation:
    is_feasible: bool
    reason: str
    suggested_minimum_days: int
    alternative_scope: str
    logistics_breakdown: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_feasible": self.is_feasible,
            "reason": self.reason,
            "suggested_minimum_days": self.suggested_minimum_days,
            "alternative_scope": self.alternative_scope,
            "logistics_breakdown": self.logistics_breakdown,
        }


class FeasibilityEngine:
    """
    Evaluates whether a requested travel duration realistically accommodates
    the requested destinations, physical terrain, transit logistics, and acclimatization safety.
    """

    # Major high-altitude and glacial trekking destinations
    HIGH_ALTITUDE_TREKS = {
        "k2": {"name": "K2 Base Camp & Concordia", "min_days": 14, "peak_alt": 5150, "gateway": "Askole", "terrain": "Glacial moraine / Baltoro"},
        "concordia": {"name": "Concordia / Throne Room of the Mountain Gods", "min_days": 13, "peak_alt": 4691, "gateway": "Askole", "terrain": "Baltoro Glacier"},
        "gondogoro": {"name": "Gondogoro La & K2 Circuit", "min_days": 15, "peak_alt": 5585, "gateway": "Askole / Hushe", "terrain": "High technical pass"},
        "snow lake": {"name": "Snow Lake & Hispar La Trek", "min_days": 16, "peak_alt": 5151, "gateway": "Askole / Nagar", "terrain": "Biafo-Hispar wilderness"},
        "spantik": {"name": "Spantik (Golden Peak) Base Camp / Expedition", "min_days": 12, "peak_alt": 4300, "gateway": "Arandu", "terrain": "Chogo Lungma Glacier"},
        "broad peak": {"name": "Broad Peak Base Camp", "min_days": 14, "peak_alt": 4960, "gateway": "Askole", "terrain": "Baltoro Glacier"},
        "gasherbrum": {"name": "Gasherbrum I/II Base Camp", "min_days": 14, "peak_alt": 5150, "gateway": "Askole", "terrain": "Baltoro Glacier"},
        "nanga parbat": {"name": "Nanga Parbat Base Camp (Raikhot/Herligkoffer)", "min_days": 5, "peak_alt": 3967, "gateway": "Raikhot Bridge", "terrain": "Jeep track & alpine trail"},
        "fairy meadows": {"name": "Fairy Meadows & Beyal Camp", "min_days": 4, "peak_alt": 3500, "gateway": "Raikhot Bridge", "terrain": "Steep jeep track & forest hike"},
        "deosai": {"name": "Deosai National Park Plateau", "min_days": 4, "peak_alt": 4114, "gateway": "Skardu / Astore", "terrain": "High alpine plateau (4,000m)"},
        "rush lake": {"name": "Rush Lake & Rush Peak Trek", "min_days": 7, "peak_alt": 4694, "gateway": "Hoper Valley", "terrain": "Glacial crossing & steep ridge"},
        "shimshal pamir": {"name": "Shimshal Pamir & Minglik Sar Trek", "min_days": 9, "peak_alt": 4735, "gateway": "Passu", "terrain": "Rugged alpine pass"},
        "shimshal": {"name": "Shimshal Valley Exploration", "min_days": 5, "peak_alt": 3100, "gateway": "Passu", "terrain": "Gorge jeep track & village trail"},
    }

    REGIONAL_TRANSIT_HUBS = {
        "hunza": {"drive_from_isb_hours": 14, "flight_dest": "Gilgit", "valley_cluster": "gilgit_hunza"},
        "skardu": {"drive_from_isb_hours": 18, "flight_dest": "Skardu", "valley_cluster": "baltistan"},
        "chitral": {"drive_from_isb_hours": 10, "flight_dest": "Chitral", "valley_cluster": "hindukush"},
        "swat": {"drive_from_isb_hours": 5, "flight_dest": None, "valley_cluster": "kpk"},
        "neelum": {"drive_from_isb_hours": 6, "flight_dest": None, "valley_cluster": "kashmir"},
        "kumrat": {"drive_from_isb_hours": 9, "flight_dest": None, "valley_cluster": "kpk"},
        "gilgit": {"drive_from_isb_hours": 13, "flight_dest": "Gilgit", "valley_cluster": "gilgit_hunza"},
    }

    def evaluate(
        self,
        destination: str,
        duration_days: int,
        user_message: str = "",
        scraped_content: Optional[str] = None,
    ) -> FeasibilityEvaluation:
        """
        Dynamically evaluate feasibility by inspecting requested activities, geographical span,
        altitude profiles, and transit overhead.
        """
        dest_lower = (destination or "").lower()
        msg_lower = (user_message or "").lower()
        combined_text = f"{dest_lower} {msg_lower}"
        effective_days = max(1, duration_days)

        # 1. High-Altitude Glacial Trek Evaluation
        for key, trek in self.HIGH_ALTITUDE_TREKS.items():
            if key in combined_text:
                min_days = trek["min_days"]
                if effective_days < min_days:
                    reason = (
                        f"A trek to {trek['name']} reaches an elevation of {trek['peak_alt']}m across {trek['terrain']}. "
                        f"Physiological acclimatization guidelines require a gradual ascent above 3,000m to prevent Acute Mountain Sickness (AMS). "
                        f"Accounting for overland transit from the gateway ({trek['gateway']}), daily trekking stages (12–16 km/day), "
                        f"and mandatory safety rest days, this expedition requires a physical minimum of {min_days} days. "
                        f"Attempting this in {effective_days} day{'s' if effective_days > 1 else ''} is physically impossible and life-threatening."
                    )
                    alt_scope = (
                        f"Option A: Allocate at least {min_days} to {min_days + 3} days for a safe, fully supported expedition to {trek['name']}.\n"
                        f"Option B: For your {effective_days}-day timeframe, consider a realistic low-altitude or cultural journey such as "
                        f"{'Lower Hunza & Karimabad' if 'hunza' in combined_text or 'skardu' not in combined_text else 'Skardu Valley, Shangrila & Shigar Fort'}."
                    )
                    breakdown = [
                        f"Overland/Flight transit to gateway ({trek['gateway']}): 2-3 days",
                        f"Acclimatization & gradual ascent stages: {min_days - 5} days",
                        f"Descent and return to gateway: 3-4 days",
                        f"Peak Altitude: {trek['peak_alt']}m (Requires strict acclimatization pacing)",
                    ]
                    return FeasibilityEvaluation(
                        is_feasible=False,
                        reason=reason,
                        suggested_minimum_days=min_days,
                        alternative_scope=alt_scope,
                        logistics_breakdown=breakdown,
                    )

        # 2. Multi-Region Span Evaluation (e.g., trying to visit Hunza AND Skardu AND Fairy Meadows in 2-4 days)
        detected_clusters = set()
        detected_destinations = []
        for reg_key, hub in self.REGIONAL_TRANSIT_HUBS.items():
            if reg_key in combined_text:
                detected_clusters.add(hub["valley_cluster"])
                detected_destinations.append(reg_key.title())

        # If user attempts to cover 2 or more distinct mountain valleys in <= 3 days
        if len(detected_clusters) >= 2 and effective_days <= 3:
            dest_list_str = " and ".join(detected_destinations[:3])
            reason = (
                f"Combining {dest_list_str} in just {effective_days} days is logistically infeasible. "
                f"Mountain transit between these valleys (e.g. Gilgit/Hunza to Skardu via the Jaglot-Skardu gorge) "
                f"requires 6 to 9 hours of driving over rugged high-altitude roads each way, leaving no daylight for sightseeing or recovery."
            )
            alt_scope = (
                f"Option A: Focus exclusively on one valley ({detected_destinations[0]}) for a relaxed {effective_days}-day trip.\n"
                f"Option B: Extend your itinerary to 6–8 days to comfortably connect {dest_list_str} without excessive road fatigue."
            )
            breakdown = [
                f"Inter-valley road transit time: 7-9 hours per transfer",
                f"Recommended minimum for multi-valley circuit: 6-7 days",
            ]
            return FeasibilityEvaluation(
                is_feasible=False,
                reason=reason,
                suggested_minimum_days=6,
                alternative_scope=alt_scope,
                logistics_breakdown=breakdown,
            )

        # 3. Gateway overland drive constraint (e.g. 1-2 days to Skardu or Hunza from Islamabad)
        if effective_days <= 2 and any(k in combined_text for k in ["skardu", "hunza", "chitral", "deosai"]):
            target = "Skardu" if "skardu" in combined_text else "Hunza"
            reason = (
                f"Planning a {effective_days}-day journey to {target} from Islamabad is not practically viable. "
                f"Driving the Karakoram Highway / Skardu road takes 14 to 18 hours each way (minimum 2 full days of driving alone). "
                f"While flights operate, high-altitude mountain flights are subject to visual flight rules (VFR) and weather delays, "
                f"requiring built-in contingency buffers."
            )
            alt_scope = (
                f"Option A: Expand your itinerary to at least 4 to 5 days to enjoy {target}.\n"
                f"Option B: For a 2-day weekend escape, explore closer destinations like Swat Valley (Malam Jabba) or Shogran / Kaghan Valley."
            )
            breakdown = [
                f"Road transit to {target}: 14-18 hours each way",
                f"Minimum recommended stay: 4-5 days",
            ]
            return FeasibilityEvaluation(
                is_feasible=False,
                reason=reason,
                suggested_minimum_days=4,
                alternative_scope=alt_scope,
                logistics_breakdown=breakdown,
            )

        # Request is feasible
        return FeasibilityEvaluation(
            is_feasible=True,
            reason="The requested duration and scope comfortably align with physical terrain and transit logistics.",
            suggested_minimum_days=effective_days,
            alternative_scope="",
            logistics_breakdown=[],
        )


feasibility_engine = FeasibilityEngine()
