"""Formal, downloadable PDF documents for the reports module.

The print-preview templates (``reports/_print_base.html``) are styled for the
browser's own print engine, which is the right tool for putting paper in a
printer. "Export PDF" is a different job: it has to hand back a real ``.pdf``
file without a dialog, so this module renders the same document structure with
fpdf2 - matching letterhead, table and footer conventions, so a printed sheet
and an exported file read as the same official document.

Fonts: fpdf2's core fonts are latin-1 only and cannot encode the peso sign used
everywhere else in the app, so DejaVu (free to redistribute) is vendored in
``static/fonts/`` and subset-embedded into each file.
"""

import os
from datetime import date

from django.conf import settings
from django.http import HttpResponse
from fpdf import FPDF

FONT_DIR = os.path.join(settings.STATICFILES_DIRS[0], "fonts")
FONTS = (
    ("Sans", "", "DejaVuSans.ttf"),
    ("Sans", "B", "DejaVuSans-Bold.ttf"),
    ("Serif", "", "DejaVuSerif.ttf"),
    ("Serif", "B", "DejaVuSerif-Bold.ttf"),
)

# Palette mirrors the CSS custom properties in reports/_print_base.html.
BRAND = (47, 107, 79)
BRAND_INK = (39, 76, 59)
BRAND_SOFT = (238, 245, 240)
INK = (26, 31, 38)
INK_SOFT = (63, 72, 84)
MUTED = (107, 114, 128)
PAGE_MUTED = (138, 148, 141)
LINE = (213, 221, 216)
LINE_STRONG = (185, 198, 191)
HAIR = (236, 239, 240)
STRIPE = (247, 250, 248)
TOTAL_BG = (234, 240, 236)
TONES = {
    "pos": ((20, 83, 45), (236, 253, 243), (187, 231, 203)),
    "neg": ((153, 27, 27), (253, 241, 241), (240, 192, 192)),
    "warn": ((138, 75, 11), (255, 246, 234), (244, 207, 160)),
}

MARGIN_X = 14
MARGIN_TOP = 15
FOOTER_BAND = 22  # bottom reserve for the running footer
CONTENT_LIMIT = 297 - FOOTER_BAND

CELL_PAD_X = 2.2
CELL_PAD_Y = 1.5
BODY_SIZE = 8
ROW_LINE_H = 3.6  # one line of 8pt body text
MIN_COL_W = 12
MAX_COL_RATIO = 0.45  # no single column may take more than this share of the page

META_PANEL_W = 62


# --------------------------------------------------------------------------- #
#  Value formatting
# --------------------------------------------------------------------------- #
def _text(value):
    return _dash_if_empty("" if value is None else str(value))


def _dash_if_empty(value):
    return value.strip() or "-"


def _date(value):
    return value.strftime("%b %d, %Y") if isinstance(value, date) else _text(value)


def _number(value):
    return f"{value:,}" if value is not None else "-"


def _money(value):
    """Peso amount, matching the rest of the app (₱1,234.56)."""
    return "-" if value is None else f"₱{value:,.2f}"


def _quantity(value):
    """Decimal amount without trailing zeros, e.g. 12 / 12.5 / 0.75."""
    if value is None:
        return "-"
    return f"{value:,.2f}".rstrip("0").rstrip(".") or "0"


def _batch(flock):
    return flock.batch_number if flock else "-"


# --------------------------------------------------------------------------- #
#  Renderer
# --------------------------------------------------------------------------- #
class _ReportPDF(FPDF):
    def __init__(self, doc):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.doc = doc
        self.head = None  # (caption, headers, widths, aligns) of the table in progress
        self.set_auto_page_break(False)
        self.set_margins(MARGIN_X, MARGIN_TOP, MARGIN_X)
        self.set_title(doc["title"])
        self.set_subject(doc["subtitle"])
        self.set_author(doc["farm"]["name"])
        self.set_creator("Farm Management System")
        self.alias_nb_pages()
        for family, style, filename in FONTS:
            self.add_font(family, style, os.path.join(FONT_DIR, filename))

    # ---------- page furniture ---------- #
    def header(self):
        if self.page_no() == 1:
            self._letterhead()
        else:
            self._running_head()

    def footer(self):
        base = self.h - FOOTER_BAND + 6
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        self.line(MARGIN_X, base - 3.2, self.w - MARGIN_X, base - 3.2)
        self.set_font("Sans", "", 6.8)
        self.set_text_color(*PAGE_MUTED)
        farm = self.doc["farm"]
        left = farm["name"] + (f"  ·  {farm['location']}" if farm["location"] else "")
        third = self.epw / 3
        self.set_xy(MARGIN_X, base)
        self.cell(third, 4, left, align="L")
        self.set_xy(MARGIN_X + third, base)
        self.cell(third, 4, self.doc["title"], align="C")
        self.set_xy(MARGIN_X + 2 * third, base)
        self.cell(third, 4, f"Page {self.page_no()} of {{nb}}", align="R")

    def _letterhead(self):
        farm = self.doc["farm"]
        self.set_y(MARGIN_TOP)

        logo_path = farm.get("logo_path")
        logo_w = 0.0
        if logo_path and os.path.exists(logo_path):
            self.image(logo_path, MARGIN_X, MARGIN_TOP, w=15)
            logo_w = 20

        name_w = self.epw - META_PANEL_W - logo_w
        self.set_font("Serif", "B", 15)
        self.set_text_color(*BRAND)
        for line in self._wrap(farm["name"], name_w)[:2]:
            self.set_xy(MARGIN_X + logo_w, self.get_y())
            self.cell(name_w, 6.4, line, align="L")
            self.set_y(self.get_y() + 6.4)
        if farm["location"]:
            self.set_x(MARGIN_X + logo_w)
            self.set_font("Sans", "", 8)
            self.set_text_color(*MUTED)
            self.multi_cell(name_w, 3.8, farm["location"], align="L")

        # The panel an auditor reads first: what, over what period, by whom, when.
        self._meta_panel(MARGIN_TOP - 0.5, farm)

        rule_y = max(self.get_y(), MARGIN_TOP + 25) + 3.5
        self.set_draw_color(*BRAND)
        self.set_line_width(0.9)
        self.line(MARGIN_X, rule_y, self.w - MARGIN_X, rule_y)
        self.set_draw_color(*LINE_STRONG)
        self.set_line_width(0.2)
        self.line(MARGIN_X, rule_y + 1.4, self.w - MARGIN_X, rule_y + 1.4)

        self.set_y(rule_y + 5)
        self.set_font("Serif", "B", 13)
        self.set_text_color(*INK)
        self.cell(self.epw, 7, self.doc["title"], align="L")
        self.set_y(self.get_y() + 7)
        self.set_font("Sans", "", 8.5)
        self.set_text_color(*MUTED)
        self.cell(self.epw, 4.4, self.doc["subtitle"], align="L")
        self.set_y(self.get_y() + 7)

    def _meta_panel(self, top, farm):
        rows = (
            ("Report", self.doc["title"]),
            ("Period", self.doc["period"]),
            ("Generated", farm["generated"]),
            ("Prepared by", farm["prepared_by"]),
        )
        x = self.w - MARGIN_X - META_PANEL_W
        label_w = 21
        value_w = META_PANEL_W - label_w
        y = top
        for label, value in rows:
            self.set_font("Sans", "", 7.4)
            lines = self._wrap(_text(value), value_w - 1)
            self.set_font("Sans", "", 6.4)
            self.set_text_color(*INK_SOFT)
            self.set_xy(x, y)
            self.cell(label_w, 3.4, label.upper(), align="L")
            self.set_font("Sans", "", 7.4)
            self.set_text_color(*INK)
            for i, line in enumerate(lines):
                self.set_xy(x + label_w, y + i * 3.4)
                self.cell(value_w, 3.4, line, align="R")
            y += len(lines) * 3.4 + 0.8
        self.set_y(max(self.get_y(), y))

    def _running_head(self):
        self.set_font("Sans", "", 7.4)
        self.set_text_color(*MUTED)
        self.set_xy(MARGIN_X, MARGIN_TOP)
        self.cell(self.epw * 0.6, 4, self.doc["farm"]["name"], align="L")
        self.set_xy(MARGIN_X + self.epw * 0.6, MARGIN_TOP)
        self.cell(self.epw * 0.4, 4, self.doc["title"], align="R")
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        self.line(MARGIN_X, MARGIN_TOP + 5, self.w - MARGIN_X, MARGIN_TOP + 5)
        self.set_y(MARGIN_TOP + 9)

    # ---------- primitives ---------- #
    def _wrap(self, text, width):
        """Word wrap, then hard-break any token still wider than its column."""
        lines = []
        for paragraph in str(text).splitlines() or [""]:
            paragraph = paragraph.strip()
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for word in paragraph.split():
                trial = f"{current} {word}".strip()
                if not current or self.get_string_width(trial) <= width:
                    current = trial
                    continue
                lines.append(current)
                current = word
            lines.append(current)

        fixed = []
        for line in lines:
            while self.get_string_width(line) > width and len(line) > 1:
                cut = len(line)
                while cut > 1 and self.get_string_width(line[:cut]) > width:
                    cut -= 1
                fixed.append(line[: cut - 1].rstrip())
                line = line[cut - 1 :]
            fixed.append(line)
        return fixed or [""]

    def _room(self, needed):
        """Return True after starting a new page when `needed` mm no longer fit."""
        if self.get_y() + needed <= CONTENT_LIMIT:
            return False
        self.add_page()
        return True

    # ---------- summary cards ---------- #
    def summary_cards(self, cards):
        if not cards:
            return
        per_row = 4
        card_h = 17
        gap = 2.6
        card_w = (self.epw - gap * (per_row - 1)) / per_row
        for start in range(0, len(cards), per_row):
            row = cards[start : start + per_row]
            self._room(card_h + 6)
            top = self.get_y()
            for i, card in enumerate(row):
                x = MARGIN_X + i * (card_w + gap)
                self.set_draw_color(*LINE)
                self.set_line_width(0.2)
                self.set_fill_color(255, 255, 255)
                self.rect(x, top, card_w, card_h, style="DF")
                self.set_fill_color(*BRAND)
                self.rect(x, top, card_w, 1.1, style="F")
                tone = TONES.get(card.get("tone"))
                self.set_font("Sans", "", 6.4)
                self.set_text_color(*MUTED)
                self.set_xy(x + CELL_PAD_X, top + 3)
                self.cell(card_w - 2 * CELL_PAD_X, 3.4, card["label"].upper(), align="L")
                self.set_font("Serif", "B", 12)
                self.set_text_color(*(tone[0] if tone else INK))
                value = self._wrap(_text(card["value"]), card_w - 2 * CELL_PAD_X)[0]
                self.set_xy(x + CELL_PAD_X, top + 8.6)
                self.cell(card_w - 2 * CELL_PAD_X, 6, value, align="L")
            self.set_y(top + card_h + 6)

    # ---------- tables ---------- #
    def table(self, section):
        headers = section["headers"]
        aligns = section.get("align", "l" * len(headers))
        widths = section.get("widths") or self._column_widths(headers, section["rows"])
        caption = section.get("caption", "")
        self.head = (caption, headers, widths, aligns)

        self._room(14)
        if caption:
            self.set_font("Sans", "B", 9)
            self.set_text_color(*BRAND_INK)
            self.set_x(MARGIN_X)
            self.cell(self.epw, 4.6, caption, align="L")
            self.set_y(self.get_y() + 1.6)
        self._table_head()
        for i, row in enumerate(section["rows"]):
            self._table_row(row, stripe=i % 2 == 1)
        if section.get("totals"):
            if self.get_y() + 8 > CONTENT_LIMIT:
                self.add_page()
                self._table_head(continued=True)
            self._table_totals(section["totals"])
        self.head = None
        self.set_y(self.get_y() + 5)

    def _column_widths(self, headers, rows):
        avail = self.epw
        self.set_font("Sans", "B", 7)
        natural = [self.get_string_width(_text(h)) + 2 * CELL_PAD_X for h in headers]
        self.set_font("Sans", "", BODY_SIZE)
        for row in rows:
            for i, cell in enumerate(row):
                text = _text(cell[0] if isinstance(cell, tuple) else cell)
                natural[i] = max(natural[i], self.get_string_width(text) + 2 * CELL_PAD_X)
        ceiling = avail * MAX_COL_RATIO
        widths = [min(w, ceiling) for w in natural]
        scale = avail / sum(widths)
        widths = [max(w * scale, MIN_COL_W) for w in widths]
        total = sum(widths)
        return [w * avail / total for w in widths]

    def _table_head(self, continued=False):
        caption, headers, widths, aligns = self.head
        self._room(8)
        top = self.get_y()
        height = 6.6
        self.set_font("Sans", "B", 7)
        self.set_text_color(*BRAND_INK)
        self.set_fill_color(*BRAND_SOFT)
        self.set_draw_color(*LINE_STRONG)
        self.set_line_width(0.3)
        x = MARGIN_X
        for i, label in enumerate(headers):
            self.set_xy(x + CELL_PAD_X * 0.8, top)
            self.cell(
                widths[i] - CELL_PAD_X * 1.6,
                height,
                label.upper(),
                align=aligns[i].upper(),
                fill=True,
                border="B",
            )
            x += widths[i]
        if continued and caption:
            self.set_font("Sans", "", 7)
            self.set_text_color(*MUTED)
            self.set_xy(MARGIN_X, top + height + 0.4)
            self.cell(self.epw, 3, f"{caption} (continued)", align="L")
            self.set_y(top + height + 3.6)
        else:
            self.set_y(top + height)

    def _table_row(self, cells, widths=None, aligns=None, stripe=False):
        if widths is None:
            widths = self.head[2]
        if aligns is None:
            aligns = self.head[3]
        self.set_font("Sans", "", BODY_SIZE)
        laid = []
        for value, width in zip(cells, widths):
            tone = None
            if isinstance(value, tuple):
                value, tone = value
            text = _text(value)
            laid.append((self._wrap(text, width - 2 * CELL_PAD_X), tone))
        row_h = max(len(lines) for lines, _ in laid) * ROW_LINE_H + 2 * CELL_PAD_Y
        if self.get_y() + row_h > CONTENT_LIMIT:
            self.add_page()
            self._table_head(continued=True)
        top = self.get_y()
        if stripe:
            self.set_fill_color(*STRIPE)
            self.rect(MARGIN_X, top, self.epw, row_h, style="F")
        x = MARGIN_X
        for i, (lines, tone) in enumerate(laid):
            self.set_text_color(*(TONES[tone][0] if tone else INK))
            for j, line in enumerate(lines):
                self.set_xy(x + CELL_PAD_X, top + CELL_PAD_Y + j * ROW_LINE_H)
                self.cell(widths[i] - 2 * CELL_PAD_X, ROW_LINE_H, line, align=aligns[i].upper())
            x += widths[i]
        self.set_draw_color(*HAIR)
        self.set_line_width(0.2)
        self.line(MARGIN_X, top + row_h, self.w - MARGIN_X, top + row_h)
        self.set_y(top + row_h)

    def _table_totals(self, cells):
        _, _, widths, aligns = self.head
        top = self.get_y()
        height = 6.6
        self.set_font("Sans", "B", BODY_SIZE)
        self.set_fill_color(*TOTAL_BG)
        self.rect(MARGIN_X, top, self.epw, height, style="F")
        x = MARGIN_X
        for i, value in enumerate(cells):
            tone = None
            if isinstance(value, tuple):
                value, tone = value
            self.set_text_color(*(TONES[tone][0] if tone else BRAND_INK))
            self.set_xy(x + CELL_PAD_X, top + (height - ROW_LINE_H) / 2)
            self.cell(widths[i] - 2 * CELL_PAD_X, ROW_LINE_H, _text(value), align=aligns[i].upper())
            x += widths[i]
        self.set_draw_color(*LINE_STRONG)
        self.set_line_width(0.3)
        self.line(MARGIN_X, top, self.w - MARGIN_X, top)
        self.line(MARGIN_X, top + height, self.w - MARGIN_X, top + height)
        self.set_y(top + height)

    # ---------- notes / facts / signature ---------- #
    def note(self, section):
        tone = TONES.get(section.get("tone"), (BRAND_INK, BRAND_SOFT, LINE_STRONG))
        body_w = self.epw - 12
        self.set_font("Sans", "", 7.8)
        lines = [(line, True) for line in self._wrap(section["heading"], body_w)]
        for item in section.get("items", []):
            lines.extend((line, False) for line in self._wrap(f"\u2022 {item}", body_w))
        box_h = len(lines) * 3.7 + 6
        if self.get_y() + box_h > CONTENT_LIMIT:
            self.add_page()
        top = self.get_y()
        self.set_fill_color(*tone[1])
        self.rect(MARGIN_X, top, self.epw, box_h, style="F")
        self.set_fill_color(*tone[0])
        self.rect(MARGIN_X, top, 1.2, box_h, style="F")
        self.set_draw_color(*tone[2])
        self.set_line_width(0.2)
        self.rect(MARGIN_X, top, self.epw, box_h, style="D")
        self.set_text_color(*tone[0])
        for i, (line, is_heading) in enumerate(lines):
            self.set_font("Sans", "B" if is_heading else "", 7.8)
            self.set_xy(MARGIN_X + 6, top + 3 + i * 3.7)
            self.cell(body_w, 3.7, line, align="L")
        self.set_y(top + box_h + 5)

    def facts(self, items):
        self._room(8)
        top = self.get_y()
        x = MARGIN_X
        for label, value in items:
            value = _text(value)
            self.set_font("Sans", "", BODY_SIZE)
            self.set_text_color(*MUTED)
            self.set_xy(x, top)
            label_w = self.get_string_width(f"{label}:") + 2
            self.cell(label_w, 4.2, f"{label}:", align="L")
            self.set_font("Sans", "B", BODY_SIZE)
            self.set_text_color(*INK)
            self.set_xy(x + label_w, top)
            self.cell(self.get_string_width(value) + 2, 4.2, value, align="L")
            x += label_w + self.get_string_width(value) + 14
        self.set_y(top + 7)

    def empty_state(self, message):
        """Dashed holding box for a period with no records, as on the print page."""
        height = 26
        if self.get_y() + height > CONTENT_LIMIT:
            self.add_page()
        top = self.get_y()
        self.set_draw_color(*LINE_STRONG)
        self.set_line_width(0.3)
        self.rect(MARGIN_X, top, self.epw, height, style="D")
        self.set_font("Sans", "", 9)
        self.set_text_color(*MUTED)
        self.set_xy(MARGIN_X, top + (height - 5) / 2)
        self.cell(self.epw, 5, message, align="C")
        self.set_y(top + height + 5)

    def signature_block(self):
        if self.get_y() + 26 > CONTENT_LIMIT:
            self.add_page()
        top = self.get_y() + 6
        half = self.epw / 2
        line_y = top + 15
        blocks = (
            ("Prepared by", self.doc["farm"]["prepared_by"]),
            ("Approved by", ""),
        )
        self.set_draw_color(*LINE_STRONG)
        self.set_line_width(0.3)
        self.line(MARGIN_X + 8, line_y, MARGIN_X + half - 20, line_y)
        self.line(MARGIN_X + half + 8, line_y, self.w - MARGIN_X - 4, line_y)
        for i, (label, name) in enumerate(blocks):
            x = MARGIN_X + i * half
            if name:
                self.set_font("Sans", "", 7.4)
                self.set_text_color(*INK)
                self.set_xy(x, line_y - 4.4)
                self.cell(half - 28, 3.6, name, align="L")
            self.set_font("Sans", "", 6.4)
            self.set_text_color(*MUTED)
            self.set_xy(x, line_y + 1.4)
            self.cell(half - 28, 3.4, label.upper(), align="L")
        self.set_y(line_y + 8)


# --------------------------------------------------------------------------- #
#  Document payloads
# --------------------------------------------------------------------------- #
def _document(ctx, cards, sections, signature=True):
    end = ctx.get("end_date") or date.today()
    return {
        "title": ctx["report_title"],
        "subtitle": ctx["report_subtitle"],
        "period": ctx["date_range"],
        "period_slug": f"{end:%Y-%m-%d}",
        "farm": {
            "name": ctx["farm_name"],
            "location": ctx["farm_location"],
            "prepared_by": ctx["prepared_by"],
            "generated": f"{ctx['generated_at']:%b %d, %Y, %I:%M %p}",
            "logo_path": ctx.get("farm_logo_path"),
        },
        "cards": cards,
        "sections": sections,
        "signature": signature,
    }


def production_document(ctx):
    records = ctx["records"]
    rows = [
        [
            _date(r.production_date),
            _batch(r.flock),
            _number(r.total_eggs),
            _number(r.good_eggs),
            _number(r.cracked_eggs),
            _number(r.rejected_eggs),
        ]
        for r in records
    ]
    cards = [
        {"label": "Total Eggs", "value": _number(ctx["total_eggs"])},
        {"label": "Good Eggs", "value": _number(ctx["total_good"]), "tone": "pos"},
        {"label": "Cracked Eggs", "value": _number(ctx["total_cracked"]), "tone": "warn"},
        {"label": "Rejected Eggs", "value": _number(ctx["total_rejected"]), "tone": "neg"},
    ]
    sections = [
        {
            "kind": "table",
            "caption": "Daily Production Records",
            "headers": ["Date", "Flock", "Total", "Good", "Cracked", "Rejected"],
            "align": "llrrrr",
            "rows": rows,
            "totals": [
                "Totals",
                f"{len(rows)} record{'s' if len(rows) != 1 else ''}",
                _number(ctx["total_eggs"]),
                _number(ctx["total_good"]),
                _number(ctx["total_cracked"]),
                _number(ctx["total_rejected"]),
            ],
        }
    ]
    if not rows:
        sections = [{"kind": "empty", "text": "No production records were found for this period."}]
    return _document(ctx, cards, sections)


def death_document(ctx):
    records = ctx["records"]
    rows = [
        [_date(r.date_recorded), _batch(r.flock), _number(r.quantity), _text(r.cause_of_death)]
        for r in records
    ]
    cards = [
        {"label": "Total Deaths", "value": _number(ctx["total_mortality"]), "tone": "neg"},
        {"label": "Records", "value": _number(len(rows))},
    ]
    sections = [
        {
            "kind": "table",
            "caption": "Death Records",
            "headers": ["Date", "Flock", "Quantity", "Cause"],
            "align": "llrl",
            "rows": rows,
            "totals": ["Total", "", _number(ctx["total_mortality"]), ""],
        }
    ]
    if not rows:
        sections = [{"kind": "empty", "text": "No death records were found for this period."}]
    return _document(ctx, cards, sections)


def sales_document(ctx):
    records = ctx["records"]
    rows = [
        [
            _date(r.date_sold),
            _text(r.product_name),
            _text(r.buyer),
            _quantity(r.quantity),
            _money(r.total_amount),
        ]
        for r in records
    ]
    cards = [
        {"label": "Total Sales", "value": _money(ctx["total_sales"]), "tone": "pos"},
        {"label": "Transactions", "value": _number(len(rows))},
    ]
    sections = [
        {
            "kind": "table",
            "caption": "Sales Records",
            "headers": ["Date", "Product", "Buyer", "Quantity", "Amount"],
            "align": "llllr",
            "rows": rows,
            "totals": ["Total", "", "", "", _money(ctx["total_sales"])],
        }
    ]
    if not rows:
        sections = [{"kind": "empty", "text": "No sales records were found for this period."}]
    return _document(ctx, cards, sections)


def expense_document(ctx):
    records = ctx["records"]
    rows = [
        [_date(r.expense_date), _text(r.category), _text(r.description), _money(r.amount)]
        for r in records
    ]
    cards = [
        {"label": "Total Expenses", "value": _money(ctx["total_expenses"]), "tone": "neg"},
        {"label": "Records", "value": _number(len(rows))},
    ]
    sections = [
        {
            "kind": "table",
            "caption": "Expense Records",
            "headers": ["Date", "Category", "Description", "Amount"],
            "align": "llll",
            "rows": rows,
            "totals": ["Total", "", "", _money(ctx["total_expenses"])],
        }
    ]
    if not rows:
        sections = [{"kind": "empty", "text": "No expense records were found for this period."}]
    return _document(ctx, cards, sections)


def inventory_document(ctx):
    items = list(ctx["items"])
    low = {item.pk for item in ctx["low_stock"]}
    expired = {item.pk for item in ctx["expired"]}
    rows = []
    for item in items:
        if item.pk in expired:
            status = ("EXPIRED", "neg")
        elif item.pk in low:
            status = ("LOW STOCK", "warn")
        else:
            status = ("IN STOCK", "pos")
        rows.append(
            [
                _text(item.name),
                _text(item.category),
                f"{_quantity(item.quantity)} {_text(item.unit)}",
                _date(item.expiration_date) if item.expiration_date else "No expiry",
                status,
            ]
        )
    cards = [
        {"label": "Items on Hand", "value": _number(len(items))},
        {"label": "Low Stock", "value": _number(len(low)), "tone": "warn"},
        {"label": "Expired", "value": _number(len(expired)), "tone": "neg"},
    ]
    sections = []
    if low:
        sections.append(
            {
                "kind": "note",
                "tone": "warn",
                "heading": f"Low stock alerts ({len(low)})",
                "items": [
                    f"{item.name}: {_quantity(item.quantity)} {item.unit} on hand, reorder level {_quantity(item.reorder_level)}"
                    for item in ctx["low_stock"]
                ],
            }
        )
    if expired:
        sections.append(
            {
                "kind": "note",
                "tone": "neg",
                "heading": f"Expired items ({len(expired)})",
                "items": [
                    f"{item.name}: expired {_date(item.expiration_date)}" for item in ctx["expired"]
                ],
            }
        )
    if rows:
        sections.append(
            {
                "kind": "table",
                "caption": "Inventory on Hand",
                "headers": ["Item", "Category", "Quantity", "Expiry", "Status"],
                "align": "lllll",
                "rows": rows,
            }
        )
    else:
        sections.append({"kind": "empty", "text": "No inventory items are currently active."})
    return _document(ctx, cards, sections)


def profit_loss_document(ctx):
    profit = ctx["profit_loss"]
    cards = [
        {"label": "Total Sales", "value": _money(ctx["total_sales"]), "tone": "pos"},
        {"label": "Total Expenses", "value": _money(ctx["total_expenses"]), "tone": "neg"},
        {
            "label": f"Net {'Profit' if profit >= 0 else 'Loss'}",
            "value": _money(profit),
            "tone": "pos" if profit >= 0 else "neg",
        },
    ]
    sections = [
        {
            "kind": "table",
            "caption": "Financial Summary",
            "headers": ["Metric", "Amount"],
            "align": "lr",
            "rows": [
                ["Total revenue from sales", _money(ctx["total_sales"])],
                ["Total recorded expenses", _money(ctx["total_expenses"])],
            ],
            "totals": [f"Net {'Profit' if profit >= 0 else 'Loss'}", _money(profit)],
        },
        {"kind": "facts", "items": [("Profit margin", ctx["margin_display"])]},
    ]
    return _document(ctx, cards, sections)


DOCUMENTS = {
    "production": production_document,
    "deaths": death_document,
    "sales": sales_document,
    "expenses": expense_document,
    "inventory": inventory_document,
    "profit-loss": profit_loss_document,
}


# --------------------------------------------------------------------------- #
#  Entry points
# --------------------------------------------------------------------------- #
def build(doc):
    """Render a document payload to PDF bytes."""
    pdf = _ReportPDF(doc)
    pdf.add_page()
    pdf.summary_cards(doc.get("cards", []))
    for section in doc["sections"]:
        kind = section["kind"]
        if kind == "table":
            pdf.table(section)
        elif kind == "note":
            pdf.note(section)
        elif kind == "facts":
            pdf.facts(section["items"])
        elif kind == "empty":
            pdf.empty_state(section["text"])
    if doc.get("signature", True):
        pdf.signature_block()
    return bytes(pdf.output())


def response(slug, ctx):
    """Build and attach the PDF for one report, e.g. sales_report_2026-11-12.pdf."""
    document = DOCUMENTS[slug](ctx)
    pdf_bytes = build(document)
    filename = f"{slug.replace('-', '_')}_report_{document['period_slug']}.pdf"
    http = HttpResponse(pdf_bytes, content_type="application/pdf")
    http["Content-Disposition"] = f'attachment; filename="{filename}"'
    return http
