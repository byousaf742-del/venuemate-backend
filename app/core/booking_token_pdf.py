"""
booking_token_pdf.py
Place at: backend/app/core/booking_token_pdf.py

Add to requirements.txt:
  reportlab==4.2.0
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Palette matching the original VenueMate pink theme ───────────────────────
PRIMARY       = colors.HexColor("#E91E8C")   # hot pink
PRIMARY_DARK  = colors.HexColor("#AD1457")   # deep pink
PRIMARY_LIGHT = colors.HexColor("#FCE4EC")   # light pink tint
SECONDARY     = colors.HexColor("#FF6B9D")   # rose
ON_SURFACE    = colors.HexColor("#1C1B1F")
MUTED         = colors.HexColor("#757575")
SURFACE       = colors.HexColor("#FFFFFF")
BG            = colors.HexColor("#FFF5F8")
OUTLINE       = colors.HexColor("#E0E0E0")
SUCCESS       = colors.HexColor("#2E7D32")
SUCCESS_BG    = colors.HexColor("#E8F5E9")
ERROR         = colors.HexColor("#C62828")
ERROR_BG      = colors.HexColor("#FFEBEE")
WARNING       = colors.HexColor("#F57C00")
WARNING_BG    = colors.HexColor("#FFF3E0")
INFO          = colors.HexColor("#1565C0")
INFO_BG       = colors.HexColor("#E3F2FD")
WHITE         = colors.white

# ── Styles ───────────────────────────────────────────────────────────────────
def s(name, size=10, color=ON_SURFACE, bold=False, align=TA_LEFT, leading=None):
    return ParagraphStyle(
        name,
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=leading or size * 1.4,
    )

S_HEADER_TITLE = s("ht", 22, WHITE,    bold=True,  align=TA_CENTER)
S_HEADER_SUB   = s("hs", 10, PRIMARY_LIGHT,         align=TA_CENTER)
S_TOKEN_NUM    = s("tn", 15, PRIMARY,  bold=True,  align=TA_CENTER)
S_STATUS       = s("st", 11, SUCCESS,  bold=True,  align=TA_CENTER)
S_ISSUED       = s("is",  8, MUTED,                align=TA_CENTER)
S_SECTION      = s("sc",  8, MUTED,    bold=True)
S_LABEL        = s("lb",  9, MUTED)
S_VALUE        = s("vl", 10, ON_SURFACE, bold=True)
S_BULLET       = s("bu", 10, ON_SURFACE)
S_FOOTER       = s("ft",  8, MUTED,                align=TA_CENTER)
S_BAL_LABEL    = s("bl", 10, ON_SURFACE, bold=True)
S_BAL_VALUE    = s("bv", 11, PRIMARY,   bold=True)


def _row(label, value):
    return [Paragraph(label, S_LABEL), Paragraph(str(value) if value else "—", S_VALUE)]


def generate_booking_token_pdf(booking: dict, venue: dict, customer: dict, owner: dict) -> bytes:
    """
    Returns PDF bytes for a booking confirmation token.

    Parameters
    ----------
    booking  : dict — booking document (with 'id' as string)
    venue    : dict — venue document
    customer : dict — customer user document
    owner    : dict — owner user document
    """
    buf = io.BytesIO()
    W_PAGE = A4[0]
    M = 18 * mm
    W = W_PAGE - 2 * M

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=M, rightMargin=M,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = Table([[Paragraph("VenueMate", S_HEADER_TITLE)]], colWidths=[W])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), PRIMARY),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(hdr)

    sub = Table([[Paragraph("BOOKING CONFIRMATION TOKEN", S_HEADER_SUB)]], colWidths=[W])
    sub.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), PRIMARY_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(sub)
    story.append(Spacer(1, 4 * mm))

    # ── Token pill ────────────────────────────────────────────────────────────
    token_val = booking.get("confirmation_token", "N/A")
    issued_on = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    pill = Table([
        [Paragraph(token_val, S_TOKEN_NUM)],
        [Paragraph("CONFIRMED ✓", S_STATUS)],
        [Paragraph(f"Issued: {issued_on}", S_ISSUED)],
    ], colWidths=[W])
    pill.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), PRIMARY_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEABOVE",     (0, 0), (-1, 0),  1.5, PRIMARY),
        ("LINEBELOW",     (0, -1), (-1, -1), 1.5, PRIMARY),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(pill)
    story.append(Spacer(1, 5 * mm))

    # ── Info block helper ─────────────────────────────────────────────────────
    def info_block(title, rows):
        story.append(Paragraph(title.upper(), S_SECTION))
        story.append(Spacer(1, 1 * mm))
        tbl = Table(rows, colWidths=[W * 0.38, W * 0.62])
        tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [SURFACE, BG]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.8, OUTLINE),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, OUTLINE),
            ("ROUNDEDCORNERS", [6]),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4 * mm))

    # ── Venue details ─────────────────────────────────────────────────────────
    loc = venue.get("location", {})
    address = ", ".join(
        p for p in [loc.get("address", ""), loc.get("area", ""), loc.get("city", "")] if p
    ) or "—"
    cap = venue.get("capacity", {})
    pricing = venue.get("pricing", {})

    info_block("Venue Details", [
        _row("Venue Name",   venue.get("name", "—")),
        _row("Type",         venue.get("type", "—").capitalize()),
        _row("Address",      address),
        _row("Min Capacity", str(cap.get("min", "—"))),
        _row("Max Capacity", str(cap.get("max", "—"))),
        _row("Base Price",   f"PKR {pricing.get('base_per_day', 0):,} / day"),
    ])

    # ── Customer details ──────────────────────────────────────────────────────
    info_block("Customer Details", [
        _row("Full Name", customer.get("name", "—")),
        _row("Email",     customer.get("email", "—")),
        _row("Phone",     customer.get("phone", "—")),
    ])

    # ── Owner details ─────────────────────────────────────────────────────────
    info_block("Owner / Host Details", [
        _row("Name",  owner.get("name", "—")),
        _row("Email", owner.get("email", "—")),
        _row("Phone", owner.get("phone", "—")),
    ])

    # ── Booking details ───────────────────────────────────────────────────────
    info_block("Booking Details", [
        _row("Booking ID",  booking.get("id", "—")),
        _row("Event Date",  booking.get("event_date", "—")),
        _row("Event Time",  booking.get("event_time", "—")),
        _row("Event Type",  booking.get("event_type", "—")),
        _row("Guest Count", str(booking.get("guest_count", "—"))),
        _row("Notes",       booking.get("notes") or "None"),
    ])

    # ── Services requested ────────────────────────────────────────────────────
    services = booking.get("services_requested", [])
    if services:
        story.append(Paragraph("SERVICES REQUESTED", S_SECTION))
        story.append(Spacer(1, 1 * mm))
        svc_rows = [[Paragraph(f"• {s}", S_BULLET)] for s in services]
        svc_tbl = Table(svc_rows, colWidths=[W])
        svc_tbl.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [SURFACE, BG]),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("BOX",           (0, 0), (-1, -1), 0.8, OUTLINE),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, OUTLINE),
            ("ROUNDEDCORNERS", [6]),
        ]))
        story.append(svc_tbl)
        story.append(Spacer(1, 4 * mm))

    # ── Payment summary ───────────────────────────────────────────────────────
    total   = booking.get("total_amount", 0)
    advance = booking.get("advance_paid", 0)
    balance = total - advance

    story.append(Paragraph("PAYMENT SUMMARY", S_SECTION))
    story.append(Spacer(1, 1 * mm))
    pay_tbl = Table([
        [Paragraph("Total Amount", S_LABEL),  Paragraph(f"PKR {total:,}",   S_VALUE)],
        [Paragraph("Advance Paid", S_LABEL),  Paragraph(f"PKR {advance:,}", S_VALUE)],
        [Paragraph("Balance Due",  S_BAL_LABEL), Paragraph(f"PKR {balance:,}", S_BAL_VALUE)],
    ], colWidths=[W * 0.5, W * 0.5])
    pay_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, 1), [SURFACE, BG]),
        ("BACKGROUND",    (0, 2), (-1, 2), PRIMARY_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("BOX",           (0, 0), (-1, -1), 0.8, OUTLINE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, OUTLINE),
        ("LINEABOVE",     (0, 2), (-1, 2),  1.5, PRIMARY),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(pay_tbl)
    story.append(Spacer(1, 6 * mm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.8, color=OUTLINE))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "This document is your official proof of booking issued by VenueMate.<br/>"
        "Present this token at the venue on your event day.<br/>"
        "For support, contact us via the VenueMate app.",
        S_FOOTER
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()
