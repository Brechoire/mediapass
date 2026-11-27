"""Graphiques PNG du rapport complet des ateliers.

Les graphiques sont dessinés avec Pillow, déjà utilisé par le projet,
puis intégrés dans le document Word. Aucun fichier temporaire n'est créé.
"""

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PRIMARY = "#4A6FA5"
PRIMARY_LIGHT = "#7FA7D9"
ACCENT = "#D9A441"
GRID = "#E2E8F0"
TEXT = "#1E293B"
MUTED = "#5A6F80"

FONT_DIRS = (
    Path(__file__).resolve().parent.parent / "static" / "fonts",
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/usr/share/fonts/TTF"),
    Path("/usr/share/fonts/dejavu"),
    Path("/usr/share/fonts/liberation-sans"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
)

REGULAR_FONTS = (
    "segoeui.ttf",
    "arial.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "Arial.ttf",
    "Helvetica.ttc",
)
BOLD_FONTS = (
    "segoeuib.ttf",
    "arialbd.ttf",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "Arial Bold.ttf",
)


@lru_cache(maxsize=32)
def _font(size, bold=False):
    """Police système avec accents, ou police Pillow en dernier recours."""
    candidates = BOLD_FONTS if bold else REGULAR_FONTS
    for directory in FONT_DIRS:
        for filename in candidates:
            path = directory / filename
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    continue
    return ImageFont.load_default(size=size)


def _fmt_int(value):
    return f"{int(value or 0):,}".replace(",", " ")


def _truncate(text, max_chars):
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _new_image(title, width, height):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 28), title, font=_font(32, bold=True), fill=TEXT, anchor="la")
    return image, draw


def _empty_image(title, width, height):
    image, draw = _new_image(title, width, height)
    draw.text(
        (width / 2, height / 2),
        "Aucune donnée disponible",
        font=_font(28),
        fill=MUTED,
        anchor="mm",
    )
    return image


def _save_png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


def _draw_legend(draw, x, y, entries):
    """Dessine une légende simple et renvoie la position suivante."""
    font = _font(18)
    for label, color in entries:
        draw.rounded_rectangle((x, y + 3, x + 18, y + 21), radius=3, fill=color)
        draw.text((x + 26, y), label, font=font, fill=MUTED, anchor="la")
        x += 26 + int(draw.textlength(label, font=font)) + 34
    return x


def _draw_grid(draw, left, top, right, bottom, max_value, steps=5):
    font = _font(16)
    for index in range(steps + 1):
        value = max_value * index / steps
        y = bottom - (bottom - top) * index / steps
        color = GRID if index else "#CBD5E1"
        draw.line((left, y, right, y), fill=color, width=1)
        draw.text(
            (left - 12, y),
            _fmt_int(round(value)),
            font=font,
            fill=MUTED,
            anchor="rm",
        )


def render_monthly_chart(monthly_rows, month_type_rows, title):
    """Barres empilées : ateliers classiques / accueils, par mois."""
    width, height = 1600, 820
    totals = [int(row.get("count") or 0) for row in monthly_rows]
    if not any(totals):
        return _save_png(_empty_image(title, width, height))
    if not month_type_rows:
        month_type_rows = [{} for _ in monthly_rows]
    else:
        month_type_rows = list(month_type_rows) + [{}] * max(
            0, len(monthly_rows) - len(month_type_rows)
        )

    image, draw = _new_image(title, width, height)
    _draw_legend(
        draw,
        40,
        82,
        [("Classiques", PRIMARY), ("Accueils de classe", ACCENT)],
    )

    left, top, right, bottom = 100, 140, width - 50, height - 90
    max_value = max(
        1,
        max(
            int(row.get("classic_count") or 0) + int(row.get("class_count") or 0)
            for row in month_type_rows
        ),
    )
    # Arrondi supérieur pour des graduations lisibles.
    step = max(1, (max_value + 4) // 5)
    max_value = step * 5
    _draw_grid(draw, left, top, right, bottom, max_value)

    plot_width = right - left
    slot = plot_width / max(1, len(monthly_rows))
    bar_width = min(70, slot * 0.55)

    for index, (month_row, type_row) in enumerate(zip(monthly_rows, month_type_rows)):
        classic = int(type_row.get("classic_count") or 0)
        class_welcome = int(type_row.get("class_count") or 0)
        total = classic + class_welcome
        x_center = left + slot * (index + 0.5)
        x0 = x_center - bar_width / 2
        x1 = x_center + bar_width / 2

        if classic:
            classic_height = (bottom - top) * classic / max_value
            draw.rounded_rectangle(
                (x0, bottom - classic_height, x1, bottom),
                radius=4,
                fill=PRIMARY,
            )
        if class_welcome:
            class_height = (bottom - top) * class_welcome / max_value
            base = bottom - (bottom - top) * classic / max_value
            draw.rounded_rectangle(
                (x0, base - class_height, x1, base),
                radius=4,
                fill=ACCENT,
            )
        if total:
            total_height = (bottom - top) * total / max_value
            draw.text(
                (x_center, bottom - total_height - 12),
                _fmt_int(total),
                font=_font(17),
                fill=TEXT,
                anchor="mb",
            )
        draw.text(
            (x_center, bottom + 16),
            str(month_row.get("label") or ""),
            font=_font(17),
            fill=MUTED,
            anchor="ma",
        )

    draw.line((left, bottom, right, bottom), fill="#CBD5E1", width=2)
    return _save_png(image)


def render_communes_chart(communes, title, limit=12):
    """Barres horizontales empilées : classiques / accueils par commune."""
    width, height = 1600, max(620, 150 + 74 * min(limit, max(1, len(communes))))
    if not communes:
        return _save_png(_empty_image(title, width, 620))

    rows = sorted(
        communes,
        key=lambda row: (
            -(
                int(row.get("ateliers_classiques") or 0)
                + int(row.get("accueils_classe") or 0)
            ),
            str(row.get("commune") or "").casefold(),
        ),
    )[:limit]

    image, draw = _new_image(title, width, height)
    _draw_legend(
        draw,
        40,
        82,
        [("Classiques", PRIMARY), ("Accueils de classe", ACCENT)],
    )

    left, top, right, bottom = 330, 150, width - 120, height - 40
    max_value = max(
        1,
        max(
            int(row.get("ateliers_classiques") or 0)
            + int(row.get("accueils_classe") or 0)
            for row in rows
        ),
    )
    plot_width = right - left
    row_height = (bottom - top) / max(1, len(rows))
    bar_height = min(42, row_height * 0.58)

    for index, row in enumerate(rows):
        classic = int(row.get("ateliers_classiques") or 0)
        class_welcome = int(row.get("accueils_classe") or 0)
        total = classic + class_welcome
        y_center = top + row_height * (index + 0.5)
        y0 = y_center - bar_height / 2
        y1 = y_center + bar_height / 2

        draw.text(
            (left - 18, y_center),
            _truncate(row.get("commune") or "Non défini", 30),
            font=_font(19),
            fill=TEXT,
            anchor="rm",
        )
        if classic:
            classic_width = plot_width * classic / max_value
            draw.rounded_rectangle(
                (left, y0, left + classic_width, y1),
                radius=4,
                fill=PRIMARY,
            )
        if class_welcome:
            class_width = plot_width * class_welcome / max_value
            start = left + plot_width * classic / max_value
            draw.rounded_rectangle(
                (start, y0, start + class_width, y1),
                radius=4,
                fill=ACCENT,
            )
        draw.text(
            (left + plot_width * total / max_value + 12, y_center),
            _fmt_int(total),
            font=_font(18),
            fill=TEXT,
            anchor="lm",
        )

    draw.line((left, top - 10, left, bottom), fill="#CBD5E1", width=2)
    return _save_png(image)


def render_type_chart(classics, accueils, title):
    """Deux barres verticales : ateliers classiques et accueils de classe."""
    width, height = 1200, 620
    if not classics and not accueils:
        return _save_png(_empty_image(title, width, height))

    image, draw = _new_image(title, width, height)
    left, top, right, bottom = 120, 140, width - 120, height - 80
    max_value = max(1, int(classics or 0), int(accueils or 0))
    step = max(1, (max_value + 3) // 4)
    max_value = step * 4
    _draw_grid(draw, left, top, right, bottom, max_value)

    values = [
        ("Classiques", int(classics or 0), PRIMARY),
        ("Accueils de classe", int(accueils or 0), ACCENT),
    ]
    slot = (right - left) / len(values)
    bar_width = min(180, slot * 0.45)

    for index, (label, value, color) in enumerate(values):
        x_center = left + slot * (index + 0.5)
        x0 = x_center - bar_width / 2
        x1 = x_center + bar_width / 2
        bar_height = (bottom - top) * value / max_value
        draw.rounded_rectangle(
            (x0, bottom - bar_height, x1, bottom), radius=6, fill=color
        )
        draw.text(
            (x_center, bottom - bar_height - 14),
            _fmt_int(value),
            font=_font(24),
            fill=TEXT,
            anchor="mb",
        )
        draw.text(
            (x_center, bottom + 18),
            label,
            font=_font(20),
            fill=MUTED,
            anchor="ma",
        )

    draw.line((left, bottom, right, bottom), fill="#CBD5E1", width=2)
    return _save_png(image)


def render_animations_chart(groups, title, limit=10):
    """Barres horizontales : top des animations par nombre de séances."""
    width, height = 1600, max(620, 150 + 64 * min(limit, max(1, len(groups))))
    if not groups:
        return _save_png(_empty_image(title, width, 620))

    rows = groups[:limit]
    image, draw = _new_image(title, width, height)

    left, top, right, bottom = 560, 130, width - 140, height - 40
    max_value = max(1, max(int(row.get("sessions") or 0) for row in rows))
    plot_width = right - left
    row_height = (bottom - top) / max(1, len(rows))
    bar_height = min(36, row_height * 0.58)

    for index, row in enumerate(rows):
        sessions = int(row.get("sessions") or 0)
        y_center = top + row_height * (index + 0.5)
        y0 = y_center - bar_height / 2
        y1 = y_center + bar_height / 2

        draw.text(
            (left - 18, y_center),
            _truncate(row.get("label") or "Sans intitulé", 46),
            font=_font(19),
            fill=TEXT,
            anchor="rm",
        )
        bar_width = plot_width * sessions / max_value
        draw.rounded_rectangle((left, y0, left + bar_width, y1), radius=4, fill=PRIMARY)
        draw.text(
            (left + bar_width + 12, y_center),
            _fmt_int(sessions),
            font=_font(18),
            fill=TEXT,
            anchor="lm",
        )

    draw.line((left, top - 10, left, bottom), fill="#CBD5E1", width=2)
    return _save_png(image)
