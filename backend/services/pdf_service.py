"""
PDF Generation Service for Humsafar Itineraries.
Generates clean, professional PDF documents using ReportLab with custom styling,
brand color palettes (#0F2C3E Deep Navy and #0D9488 Teal), day-to-day schedules,
inclusions/exclusions, and high-altitude mountain gear checklists.
"""

import io
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)

# Humsafar Brand Colors
NAVY = colors.HexColor("#0F2C3E")
TEAL = colors.HexColor("#0D9488")
LIGHT_TEAL = colors.HexColor("#F0FDFA")
SLATE_DARK = colors.HexColor("#1E293B")
SLATE_MUTED = colors.HexColor("#64748B")
SLATE_BORDER = colors.HexColor("#E2E8F0")
EMERALD_BG = colors.HexColor("#ECFDF5")
EMERALD_TEXT = colors.HexColor("#065F46")
AMBER_BG = colors.HexColor("#FFFBEB")
AMBER_TEXT = colors.HexColor("#92400E")


def _clean_text(val: Any) -> str:
    """Strip dangerous characters and XML/HTML tags for ReportLab paragraphs."""
    if val is None:
        return ""
    txt = str(val)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return txt.strip()


def generate_itinerary_pdf(itinerary: Dict[str, Any]) -> bytes:
    """
    Generate a formatted PDF for an expedition itinerary.
    Includes plan heading, summary table, day-by-day route, inclusions & exclusions,
    and mountain gear packing checklist.
    """
    buffer = io.BytesIO()

    # Create document with 0.5-inch margins
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=itinerary.get("title", "Expedition Itinerary"),
        author="Humsafar - Askoli Adventure",
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    header_title_style = ParagraphStyle(
        "HeaderBrand",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=NAVY,
    )

    plan_heading_style = ParagraphStyle(
        "PlanHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=NAVY,
        spaceAfter=6,
    )

    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=SLATE_DARK,
    )

    body_muted_style = ParagraphStyle(
        "BodyMuted",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=SLATE_MUTED,
    )

    day_title_style = ParagraphStyle(
        "DayTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=NAVY,
    )

    story = []

    # 1. Top Brand Banner
    top_table_data = [
        [
            Paragraph("<b>HUMSAFAR</b> • Askoli Adventure", header_title_style),
            Paragraph("<b>Plan better. Travel farther.</b><br/><font color='#64748B'>askoliadventure.com</font>", body_muted_style),
        ]
    ]
    top_table = Table(top_table_data, colWidths=[340, 180])
    top_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(top_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceBefore=4, spaceAfter=12))

    # 2. Plan Name Heading
    title = _clean_text(itinerary.get("title", "Expedition Itinerary"))
    story.append(Paragraph(title, plan_heading_style))

    # 3. Metadata Summary Box
    region = _clean_text(itinerary.get("region") or itinerary.get("destination") or "Northern Pakistan")
    duration = _clean_text(itinerary.get("duration") or itinerary.get("days") or itinerary.get("duration_days") or "7 Days")
    if str(duration).isdigit():
        duration = f"{duration} Days"
    price = _clean_text(itinerary.get("estimated_price_pkr") or itinerary.get("estimatedPrice") or itinerary.get("price") or "Market Rate Calculated")
    if price and not price.startswith("PKR") and str(price).replace(".", "").isdigit():
        price = f"PKR {float(price):,.2f}"

    conf_label = _clean_text(itinerary.get("confidence_label") or itinerary.get("confidenceLabel") or "from our official listing")

    meta_cells = [
        [
            Paragraph(f"<b>Destination:</b> {region}", body_style),
            Paragraph(f"<b>Duration:</b> {duration}", body_style),
        ],
        [
            Paragraph(f"<b>Estimated Cost:</b> {price}", body_style),
            Paragraph(f"<b>Verification:</b> {conf_label}", body_style),
        ],
    ]
    meta_table = Table(meta_cells, colWidths=[260, 260])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_TEAL),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CCFBF1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCFBF1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 4. Day-by-Day Route Itinerary
    day_by_day = itinerary.get("day_by_day") or itinerary.get("dayByDay")
    if not day_by_day and isinstance(itinerary.get("itinerary_data"), dict):
        day_by_day = itinerary["itinerary_data"].get("day_by_day")

    story.append(Paragraph("Day-by-Day Route Itinerary", section_heading_style))

    if day_by_day and isinstance(day_by_day, list):
        day_rows = []
        for idx, stage in enumerate(day_by_day):
            d_num = stage.get("day", idx + 1)
            d_title = _clean_text(stage.get("title", f"Stage {d_num}"))
            d_desc = _clean_text(stage.get("description", ""))
            d_alt = _clean_text(stage.get("altitude", ""))

            alt_txt = f" <font color='#0D9488'>({d_alt})</font>" if d_alt else ""
            header_p = Paragraph(f"<b>Day {d_num}:</b> {d_title}{alt_txt}", day_title_style)
            desc_p = Paragraph(d_desc, body_style) if d_desc else Paragraph("Expedition trail trekking and acclimatization.", body_muted_style)

            day_rows.append([
                Paragraph(f"<b>{d_num}</b>", ParagraphStyle("DayBadge", fontName="Helvetica-Bold", fontSize=9, textColor=TEAL, alignment=1)),
                [header_p, desc_p]
            ])

        day_table = Table(day_rows, colWidths=[30, 490])
        day_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, SLATE_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("LEFTPADDING", (1, 0), (1, -1), 6),
            ])
        )
        story.append(day_table)
    else:
        story.append(Paragraph("Day-by-day stages coordinated directly by native mountain guides based on seasonal trail conditions.", body_style))

    story.append(Spacer(1, 10))

    # 5. Inclusions & Exclusions
    inclusions = itinerary.get("inclusions")
    exclusions = itinerary.get("exclusions")
    if not inclusions and isinstance(itinerary.get("itinerary_data"), dict):
        inclusions = itinerary["itinerary_data"].get("inclusions")
        exclusions = itinerary["itinerary_data"].get("exclusions")

    inc_list = inclusions if isinstance(inclusions, list) and inclusions else [
        "Licensed mountain guide & Balti porters",
        "All camp meals, dining tent, and all-weather tents",
        "Dedicated 4x4 mountain jeep transfers",
        "National park entry and trekking permits",
    ]
    exc_list = exclusions if isinstance(exclusions, list) and exclusions else [
        "International flights and Pakistan visa fees",
        "Mandatory high-altitude evacuation insurance",
        "Personal trekking equipment (-15°C bag, boots)",
        "Staff gratuities and personal expenses",
    ]

    inc_h_style = ParagraphStyle("IncH", fontName="Helvetica-Bold", fontSize=9.5, textColor=colors.HexColor("#065F46"))
    exc_h_style = ParagraphStyle("ExcH", fontName="Helvetica-Bold", fontSize=9.5, textColor=NAVY)

    inc_exc_rows = [
        [
            Paragraph("<b>Included Services</b>", inc_h_style),
            Paragraph("<b>Excluded Services</b>", exc_h_style),
        ]
    ]

    max_items = max(len(inc_list), len(exc_list))
    for i in range(max_items):
        inc_p = (
            Paragraph(f"<font color='#0D9488'><b>+</b></font> {_clean_text(inc_list[i])}", body_style)
            if i < len(inc_list)
            else Paragraph("", body_style)
        )
        exc_p = (
            Paragraph(f"<font color='#64748B'><b>-</b></font> {_clean_text(exc_list[i])}", body_muted_style)
            if i < len(exc_list)
            else Paragraph("", body_muted_style)
        )
        inc_exc_rows.append([inc_p, exc_p])

    inc_exc_table = Table(inc_exc_rows, colWidths=[255, 255])
    inc_exc_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#F0FDF4")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#CBD5E1")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )

    story.append(Paragraph("Logistics: Inclusions & Exclusions", section_heading_style))
    story.append(inc_exc_table)

    story.append(Spacer(1, 10))

    # 6. Essential Mountain Gear & Packing Checklist
    equipment = itinerary.get("equipment")
    if not equipment and isinstance(itinerary.get("itinerary_data"), dict):
        equipment = itinerary["itinerary_data"].get("equipment")

    gear_list = equipment if isinstance(equipment, list) and equipment else [
        "Sturdy, broken-in high-altitude trekking boots",
        "4-season (-15°C) sleeping bag with insulated ground pad",
        "Layering system (merino wool base, fleece, Gore-Tex waterproof shell)",
        "Category 4 UV glacier sunglasses and SPF 50+ sunblock",
        "Telescopic trekking poles and headlamp with spare batteries",
        "Personal first aid kit with altitude medication (Diamox)",
    ]

    gear_items = []
    for i in range(0, len(gear_list), 2):
        col1 = Paragraph(f"• {_clean_text(gear_list[i])}", body_style)
        col2 = Paragraph(f"• {_clean_text(gear_list[i+1])}", body_style) if i + 1 < len(gear_list) else Paragraph("", body_style)
        gear_items.append([col1, col2])

    gear_table = Table(gear_items, colWidths=[260, 260])
    gear_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])
    )

    story.append(Paragraph("Essential Mountain Gear & Packing Checklist", section_heading_style))
    story.append(gear_table)

    story.append(Spacer(1, 10))

    # 7. Operational Notes & Contact Footer
    notes = _clean_text(itinerary.get("notes") or "")
    advisory = "Government trekking permits and high-altitude logistics require 6–8 weeks advance booking."
    footer_text = f"<b>Operational Note:</b> {advisory}"
    if notes:
        footer_text += f"<br/><b>Traveler Notes:</b> {notes}"
    footer_text += f"<br/><font color='#64748B'>Generated via Humsafar for Askoli Adventure on {datetime.now(timezone.utc).strftime('%B %d, %Y')}. Official inquiry: askoliadventure.com</font>"

    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.5, color=SLATE_BORDER, spaceBefore=6, spaceAfter=6),
        Paragraph(footer_text, body_muted_style),
    ]))

    # Build document
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
