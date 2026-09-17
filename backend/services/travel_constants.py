"""
Centralized Travel Constants for Humsafar.
Single source of truth for company identity, operational boundaries,
and web search filtering. All service modules import from here
instead of defining their own copies.
"""

import os

# Updated live exchange rate: 1 USD ≈ 278 PKR (configurable via .env)
USD_TO_PKR_RATE = float(os.getenv("USD_TO_PKR_RATE", "278.0"))

def convert_pkr_to_usd(pkr_amount: float) -> int:
    """Converts PKR to USD using current exchange rate benchmark."""
    if not pkr_amount or pkr_amount <= 0:
        return 0
    return int(round(pkr_amount / USD_TO_PKR_RATE))

def convert_usd_to_pkr(usd_amount: float) -> int:
    """Converts USD to PKR using current exchange rate benchmark."""
    if not usd_amount or usd_amount <= 0:
        return 0
    return int(round(usd_amount * USD_TO_PKR_RATE))

# Company Identity
COMPANY_NAME = "Askoli Adventure"
COMPANY_WEBSITE = "https://askoliadventure.com"
COMPANY_EMAIL = "info@askoliadventure.com"
BOOKING_ADVISORY = (
    "Permit processing and logistics coordination require "
    "6 to 8 weeks advance booking."
)

CONTACT_DETAILS = {
    "company": COMPANY_NAME,
    "website": COMPANY_WEBSITE,
    "email": COMPANY_EMAIL,
    "advisory": BOOKING_ADVISORY,
}

# Operational mountain regions (used in system prompts)
OPERATIONAL_REGIONS = (
    "Karakoram, Himalayas, Hindukush, Gilgit-Baltistan, Hunza, "
    "Skardu, Swat, Chitral, Fairy Meadows, and surrounding valleys"
)

OPERATIONAL_REGIONS_DETAILED = """- Karakoram Range (K2, Concordia, Baltoro, Broad Peak, Gasherbrums, Spantik, Rakaposhi, Hunza, Skardu, Shigar, Khaplu, Hushe)
- Himalayas (Nanga Parbat, Fairy Meadows, Deosai National Park, Astore, Rama)
- Hindukush Range & KPK Mountain Valleys (Chitral, Kalash Valleys, Tirich Mir, Swat, Kalam, Kumrat Valley)
- Azad Jammu & Kashmir alpine valleys (Neelum Valley)"""

# Social media domains to exclude from web search results
SOCIAL_MEDIA_DOMAINS = frozenset({
    "facebook.com", "fb.com", "m.facebook.com",
    "instagram.com",
    "twitter.com", "x.com", "mobile.twitter.com",
    "tiktok.com",
    "youtube.com", "m.youtube.com", "youtu.be",
    "reddit.com", "old.reddit.com",
    "pinterest.com",
    "linkedin.com",
    "snapchat.com",
    "threads.net",
    "quora.com",
    "tumblr.com",
    "wa.me", "whatsapp.com",
})
