"""Génération du rapport complet des ateliers au format DOCX."""

from django.contrib.staticfiles import finders
from django.utils import timezone
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .charts import (
    render_animations_chart,
    render_communes_chart,
    render_monthly_chart,
    render_type_chart,
)

PRIMARY = RGBColor(0x4A, 0x6F, 0xA5)
DARK = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x5A, 0x6F, 0x80)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SECTIONS = (
    "Synthèse",
    "Indicateurs clés",
    "Évolution mensuelle",
    "Répartition par type et par commune",
    "Résumé par commune et animations",
    "Synthèse des animations",
    "Ateliers les plus fréquentés",
    "Communication et affiches",
    "Méthode et définitions",
    "Annexe — Regroupement des intitulés",
)


def _fmt_int(value):
    return f"{int(value or 0):,}".replace(",", "\u00a0")


def _fmt_num(value):
    return f"{float(value or 0):.1f}".replace(".", ",")


def _fmt_date(value):
    return value.strftime("%d/%m/%Y") if value else "—"


def _fmt_period(first_date, last_date):
    if not first_date and not last_date:
        return "—"
    if first_date == last_date:
        return _fmt_date(first_date)
    return f"{_fmt_date(first_date)} – {_fmt_date(last_date)}"


def _fmt_datetime(value):
    if value is None:
        value = timezone.now()
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%d/%m/%Y à %H:%M")


def _set_cell_background(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _set_cell(
    cell,
    text,
    bold=False,
    size=8.5,
    color=None,
    align=None,
):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    return run


def _set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def _add_field(paragraph, field):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = field
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(separate)
    run._r.append(placeholder)
    run._r.append(end)


def _style_document(doc):
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = DARK
    normal.paragraph_format.space_after = Pt(6)

    for level, size in ((1, 16), (2, 13), (3, 11)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = PRIMARY
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True

    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)


def _add_cover(doc, context):
    logo_path = finders.find("img/logo/logo.png")
    if logo_path:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        shape = paragraph.add_run().add_picture(logo_path, width=Cm(4.5))
        shape._inline.docPr.set("descr", "Logo Médi@'pass")
        shape._inline.docPr.set("title", "Logo Médi@'pass")

    for _ in range(3):
        doc.add_paragraph()

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Rapport complet")
    run.bold = True
    run.font.size = Pt(30)
    run.font.color.rgb = PRIMARY

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("des ateliers")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = PRIMARY

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(str(context.get("selected_year", "")))
    run.bold = True
    run.font.size = Pt(24)
    run.font.color.rgb = DARK

    synthese = context.get("synthese") or {}
    scope = synthese.get("perimetre") or "Tous les ateliers de l'année"
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(scope)
    run.font.size = Pt(12)
    run.font.color.rgb = MUTED

    for _ in range(5):
        doc.add_paragraph()

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(
        f"Généré le {_fmt_datetime(context.get('report_generated_at'))}"
    )
    run.font.size = Pt(10)
    run.font.color.rgb = MUTED

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(
        "Données agrégées par commune et par animation — aucun nominatif."
    )
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED

    doc.add_page_break()


def _add_sommaire(doc):
    doc.add_heading("Sommaire", level=1)
    for entry in SECTIONS:
        doc.add_paragraph(entry, style="List Bullet")
    doc.add_page_break()


def _add_header_footer(doc, context):
    year = context.get("selected_year", "")
    section = doc.sections[0]
    section.different_first_page_header_footer = True

    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run(f"Rapport complet des ateliers {year}")
    run.font.size = Pt(8)
    run.font.color.rgb = MUTED

    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(f"Médi@'pass — Ateliers {year} — page ")
    run.font.size = Pt(8)
    run.font.color.rgb = MUTED
    _add_field(paragraph, "PAGE")
    run = paragraph.add_run(" sur ")
    run.font.size = Pt(8)
    run.font.color.rgb = MUTED
    _add_field(paragraph, "NUMPAGES")


def _add_table(
    doc,
    headers,
    rows,
    widths=None,
    aligns=None,
    font_size=8.5,
):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    header_row = table.rows[0]
    for index, header in enumerate(headers):
        cell = header_row.cells[index]
        _set_cell(
            cell,
            header,
            bold=True,
            size=8,
            color=WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
        _set_cell_background(cell, "4A6FA5")
    _set_repeat_table_header(header_row)

    for values in rows:
        row = table.add_row()
        for index, value in enumerate(values):
            align = aligns[index] if aligns else None
            _set_cell(row.cells[index], value, size=font_size, align=align)

    if widths:
        for index, width in enumerate(widths):
            table.columns[index].width = Cm(width)
            for row in table.rows:
                row.cells[index].width = Cm(width)
    return table


def _add_chart(doc, buffer, caption):
    buffer.seek(0)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(2)
    shape = paragraph.add_run().add_picture(buffer, width=Cm(16.5))
    shape._inline.docPr.set("descr", caption)
    shape._inline.docPr.set("title", caption)

    caption_paragraph = doc.add_paragraph()
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_paragraph.paragraph_format.space_after = Pt(10)
    run = caption_paragraph.add_run(caption)
    run.italic = True
    run.font.size = Pt(8)
    run.font.color.rgb = MUTED


def _add_synthese(doc, context):
    doc.add_heading("Synthèse", level=1)
    synthese = context.get("synthese") or {}
    scope = synthese.get("perimetre")
    if scope:
        paragraph = doc.add_paragraph()
        run = paragraph.add_run(f"Périmètre : {scope}")
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED

    phrases = synthese.get("phrases") or []
    if not phrases:
        doc.add_paragraph("Aucune donnée pour rédiger la synthèse.")
        return

    doc.add_paragraph(phrases[0])
    for phrase in phrases[1:]:
        doc.add_paragraph(phrase, style="List Bullet")


def _add_kpi_table(doc, context, animation_report):
    totals = animation_report["totals"]
    animation_count = totals.get("animations", 0)
    commune_count = totals.get("communes", 0)

    table = doc.add_table(rows=2, cols=4)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    cells = [
        (
            "Ateliers",
            _fmt_int(context.get("total_workshops", 0)),
            f"{_fmt_int(context.get('total_accueil_classe', 0))} accueils de classe",
        ),
        (
            "Ateliers classiques",
            _fmt_int(context.get("total_workshops_except_class", 0)),
            "hors accueils de classe",
        ),
        (
            "Accueils de classe",
            _fmt_int(context.get("total_accueil_classe", 0)),
            "ateliers dédiés aux classes",
        ),
        (
            "Communes",
            _fmt_int(commune_count),
            "communes couvertes",
        ),
        (
            "Inscrits",
            _fmt_int(context.get("total_registered", 0)),
            "personnes inscrites",
        ),
        (
            "Présents",
            _fmt_int(context.get("total_attendees", 0)),
            "participants présents",
        ),
        (
            "Taux de présence",
            f"{_fmt_num(context.get('attendance_rate', 0))} %",
            "présents / inscrits",
        ),
        (
            "Animations",
            _fmt_int(animation_count),
            "intitulés regroupés",
        ),
    ]

    for index, (label, value, sub) in enumerate(cells):
        row = index // 4
        column = index % 4
        cell = table.rows[row].cells[column]
        _set_cell_background(cell, "EEF3F9")

        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(label.upper())
        run.font.size = Pt(7)
        run.font.color.rgb = MUTED
        run.bold = True

        paragraph = cell.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(value)
        run.font.size = Pt(17)
        run.bold = True
        run.font.color.rgb = PRIMARY

        paragraph = cell.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(sub)
        run.font.size = Pt(7)
        run.font.color.rgb = MUTED

        cell.width = Cm(4.2)

    doc.add_paragraph()


def _add_monthly(doc, context):
    doc.add_heading("Évolution mensuelle", level=1)
    year = context.get("selected_year", "")
    monthly = context.get("workshops_by_month") or []
    month_types = (
        context.get("report_month_type_cross") or context.get("month_type_cross") or []
    )

    if not monthly:
        doc.add_paragraph("Aucune donnée mensuelle.")
        return

    rows = []
    for month, month_type in zip(monthly, month_types):
        rows.append(
            [
                month.get("label", ""),
                _fmt_int(month_type.get("classic_count", 0)),
                _fmt_int(month_type.get("class_count", 0)),
                _fmt_int(month.get("count", 0)),
                _fmt_int(month.get("total_registered", 0)),
                _fmt_int(month.get("total_attendees", 0)),
                f"{_fmt_num(month.get('attendance_rate', 0))} %",
            ]
        )

    _add_table(
        doc,
        [
            "Mois",
            "Classiques",
            "Accueils",
            "Total",
            "Inscrits",
            "Présents",
            "Taux",
        ],
        rows,
        widths=[2.4, 2.4, 2.2, 2.0, 2.6, 2.6, 2.2],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )
    _add_chart(
        doc,
        render_monthly_chart(monthly, month_types, f"Ateliers par mois — {year}"),
        "Figure 1 — Répartition mensuelle des ateliers classiques et des "
        "accueils de classe.",
    )


def _add_types_and_communes(doc, context, animation_report):
    doc.add_heading("Répartition par type et par commune", level=1)
    totals = animation_report["totals"]

    registered = context.get("total_registered", 0)
    attendees = context.get("total_attendees", 0)
    type_rows = [
        [
            "Classiques",
            _fmt_int(totals.get("classics", 0)),
            _fmt_int(totals.get("classics_registered", 0)),
            _fmt_int(totals.get("classics_attendees", 0)),
            f"{_fmt_num(totals.get('classics_attendance_rate', 0))} %",
        ],
        [
            "Accueils de classe",
            _fmt_int(totals.get("class_welcome", 0)),
            _fmt_int(totals.get("class_welcome_registered", 0)),
            _fmt_int(totals.get("class_welcome_attendees", 0)),
            f"{_fmt_num(totals.get('class_welcome_attendance_rate', 0))} %",
        ],
        [
            "Total",
            _fmt_int(totals.get("sessions", 0)),
            _fmt_int(registered),
            _fmt_int(attendees),
            f"{_fmt_num(context.get('attendance_rate', 0))} %",
        ],
    ]
    _add_table(
        doc,
        ["Type", "Ateliers", "Inscrits", "Présents", "Taux"],
        type_rows,
        widths=[4.6, 3.0, 3.0, 3.0, 2.6],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )
    _add_chart(
        doc,
        render_type_chart(
            totals.get("classics", 0),
            totals.get("class_welcome", 0),
            "Ateliers classiques et accueils de classe",
        ),
        "Figure 2 — Répartition des ateliers selon leur type.",
    )

    doc.add_heading("Détail par commune", level=2)
    communes = context.get("commune_table_data") or []
    if not communes:
        doc.add_paragraph("Aucune donnée par commune.")
        return

    rows = []
    for commune in communes:
        rows.append(
            [
                commune.get("commune", "Non défini"),
                _fmt_int(commune.get("total_ateliers", 0)),
                _fmt_int(commune.get("ateliers_classiques", 0)),
                _fmt_int(commune.get("accueils_classe", 0)),
                _fmt_int(commune.get("total_participants", 0)),
                _fmt_int(commune.get("total_presents", 0)),
                f"{_fmt_num(commune.get('attendance_rate', 0))} %",
            ]
        )

    _add_table(
        doc,
        [
            "Commune",
            "Ateliers",
            "Classiques",
            "Accueils",
            "Inscrits",
            "Présents",
            "Taux",
        ],
        rows,
        widths=[4.0, 2.2, 2.3, 2.1, 2.2, 2.2, 2.0],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )
    commune_chart_title = f"Ateliers par commune — {context.get('selected_year', '')}"
    if len(communes) > 12:
        commune_chart_title += " (top 12)"
    _add_chart(
        doc,
        render_communes_chart(communes, commune_chart_title),
        "Figure 3 — Nombre d'ateliers par commune, classiques et accueils de classe.",
    )


def _add_animations_by_commune(doc, animation_report):
    doc.add_heading("Résumé par commune et animations", level=1)
    doc.add_paragraph(
        "Les intitulés ont été regroupés lorsqu'ils ne diffèrent que par "
        "leur format (Atelier, Initiation, Découverte, Soirée, etc.). "
        "Les variantes exactes sont listées dans l'annexe."
    )

    by_commune = animation_report.get("by_commune") or []
    if not by_commune:
        doc.add_paragraph("Aucune donnée par commune.")
        return

    for index, commune in enumerate(by_commune):
        doc.add_heading(
            f"{commune['commune']} — {commune['total_ateliers']} atelier(s), "
            f"{commune['animations_count']} animation(s)",
            level=2,
        )
        paragraph = doc.add_paragraph()
        run = paragraph.add_run(
            f"{_fmt_int(commune['registered'])} inscrits · "
            f"{_fmt_int(commune['attendees'])} présents · "
            f"taux de présence {_fmt_num(commune['attendance_rate'])} %"
        )
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED

        rows = []
        for animation in commune["animations"]:
            rows.append(
                [
                    animation["label"],
                    _fmt_int(animation["sessions"]),
                    _fmt_int(animation["registered"]),
                    _fmt_int(animation["attendees"]),
                    f"{_fmt_num(animation['attendance_rate'])} %",
                    _fmt_period(animation["first_date"], animation["last_date"]),
                ]
            )

        if rows:
            _add_table(
                doc,
                [
                    "Animation",
                    "Séances",
                    "Inscrits",
                    "Présents",
                    "Taux",
                    "Période",
                ],
                rows,
                widths=[5.2, 1.8, 2.0, 2.0, 1.8, 3.4],
                aligns=[
                    None,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.CENTER,
                ],
            )
        else:
            doc.add_paragraph("Aucune animation sur cette commune.")

        if index < len(by_commune) - 1:
            doc.add_paragraph()


def _add_global_animations(doc, animation_report, context):
    doc.add_heading("Synthèse des animations", level=1)
    groups = animation_report.get("groups") or []
    if not groups:
        doc.add_paragraph("Aucune animation sur le périmètre.")
        return

    rows = []
    for group in groups:
        rows.append(
            [
                group["label"],
                _fmt_int(group.get("commune_count", len(group.get("communes", [])))),
                _fmt_int(group["sessions"]),
                _fmt_int(group["registered"]),
                _fmt_int(group["attendees"]),
                f"{_fmt_num(group['attendance_rate'])} %",
            ]
        )

    _add_table(
        doc,
        ["Animation", "Communes", "Séances", "Inscrits", "Présents", "Taux"],
        rows,
        widths=[5.6, 2.0, 2.0, 2.2, 2.2, 1.8],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )

    _add_chart(
        doc,
        render_animations_chart(
            groups,
            f"Top 10 des animations par séances — {context.get('selected_year', '')}",
        ),
        "Figure 4 — Animations les plus programmées, après regroupement des intitulés.",
    )


def _add_tops(doc, context):
    doc.add_heading("Ateliers les plus fréquentés", level=1)

    most_registered = list(context.get("most_registered") or [])
    doc.add_heading("Top 5 par inscrits", level=2)
    if most_registered:
        rows = [
            [
                _fmt_date(workshop.date),
                workshop.name,
                workshop.location.name if workshop.location else "—",
                _fmt_int(workshop.number_registered),
                _fmt_int(workshop.number_attendees),
            ]
            for workshop in most_registered
        ]
        _add_table(
            doc,
            ["Date", "Atelier", "Lieu", "Inscrits", "Présents"],
            rows,
            widths=[2.2, 6.2, 4.2, 2.0, 2.0],
            aligns=[
                None,
                None,
                None,
                WD_ALIGN_PARAGRAPH.RIGHT,
                WD_ALIGN_PARAGRAPH.RIGHT,
            ],
        )
    else:
        doc.add_paragraph("Aucune donnée.")

    best_attendance = list(context.get("best_attendance") or [])
    doc.add_heading("Top 5 par taux de présence", level=2)
    if best_attendance:
        rows = [
            [
                _fmt_date(workshop.date),
                workshop.name,
                workshop.location.name if workshop.location else "—",
                _fmt_int(workshop.number_registered),
                _fmt_int(workshop.number_attendees),
                f"{_fmt_num(workshop.attendance_rate)} %",
            ]
            for workshop in best_attendance
        ]
        _add_table(
            doc,
            ["Date", "Atelier", "Lieu", "Inscrits", "Présents", "Taux"],
            rows,
            widths=[2.0, 5.0, 3.4, 1.8, 1.8, 1.6],
            aligns=[
                None,
                None,
                None,
                WD_ALIGN_PARAGRAPH.RIGHT,
                WD_ALIGN_PARAGRAPH.RIGHT,
                WD_ALIGN_PARAGRAPH.RIGHT,
            ],
        )
    else:
        doc.add_paragraph("Aucune donnée.")


def _add_communication(doc, context):
    doc.add_heading("Communication et affiches", level=1)

    communication = context.get("communication_stats") or {}
    total = context.get("total_workshops", 0)
    rows = []
    for key, label in (
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("mail", "Email"),
        ("portail", "Portail"),
        ("vdn", "VDN"),
    ):
        count = communication.get(key, 0) or 0
        rate = round(count / total * 100, 1) if total else 0.0
        rows.append([label, _fmt_int(count), f"{_fmt_num(rate)} %"])

    _add_table(
        doc,
        ["Canal", "Ateliers relayés", "Part"],
        rows,
        widths=[6.0, 5.0, 4.0],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )

    poster = context.get("poster_stats") or {}
    rows = [
        [
            "Affiches requises",
            _fmt_int(poster.get("required", 0)),
            f"{_fmt_num(poster.get('required_rate', 0))} % des ateliers",
        ],
        [
            "Affiches validées",
            _fmt_int(poster.get("valide", 0)),
            f"{_fmt_num(poster.get('valide_rate', 0))} % des requises",
        ],
        [
            "Ateliers avec visuel",
            _fmt_int(poster.get("with_image", 0)),
            "affiche ou visuel disponible",
        ],
    ]
    doc.add_heading("Affiches", level=2)
    _add_table(
        doc,
        ["Indicateur", "Nombre", "Précision"],
        rows,
        widths=[6.0, 3.0, 7.0],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            None,
        ],
    )


def _add_method(doc, context, animation_report):
    doc.add_heading("Méthode et définitions", level=1)
    scope = (context.get("synthese") or {}).get("perimetre")
    bullets = [
        "Source : base de données des ateliers Médi@'pass.",
        f"Période : année {context.get('selected_year', '')}.",
        f"Périmètre : {scope or 'tous les ateliers de l’année'}.",
        (
            "Inscrits : nombre de personnes inscrites renseigné pour chaque "
            "atelier. Présents : nombre de participants effectivement présents."
        ),
        (
            "Taux de présence : présents divisés par inscrits. Il n’est pas "
            "calculé lorsque le nombre d’inscrits est nul."
        ),
        (
            "Regroupement des intitulés : casse, accents, pluriels et mots de "
            "format (Atelier, Initiation, Découverte, Soirée, Tournoi, etc.) "
            "sont neutralisés. Les sujets différents restent séparés."
        ),
        "Les données sont agrégées : le rapport ne contient aucun nominatif.",
        f"Rapport généré le {_fmt_datetime(context.get('report_generated_at'))}.",
    ]
    for bullet in bullets:
        doc.add_paragraph(bullet, style="List Bullet")

    doc.add_heading("Annexe — Regroupement des intitulés", level=1)
    merged = animation_report.get("merged_groups") or []
    if not merged:
        doc.add_paragraph("Aucun regroupement nécessaire : chaque intitulé est unique.")
        return

    rows = [
        [
            group["label"],
            " · ".join(group["variants"]),
            _fmt_int(group["sessions"]),
        ]
        for group in merged
    ]
    _add_table(
        doc,
        ["Animation", "Variantes regroupées", "Séances"],
        rows,
        widths=[4.6, 10.0, 2.0],
        aligns=[
            None,
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
        font_size=8,
    )


def _empty_animation_report():
    return {
        "groups": [],
        "by_commune": [],
        "merged_groups": [],
        "totals": {
            "animations": 0,
            "sessions": 0,
            "registered": 0,
            "attendees": 0,
            "attendance_rate": 0.0,
            "class_welcome": 0,
            "classics": 0,
            "classics_registered": 0,
            "classics_attendees": 0,
            "classics_attendance_rate": 0.0,
            "class_welcome_registered": 0,
            "class_welcome_attendees": 0,
            "class_welcome_attendance_rate": 0.0,
            "communes": 0,
        },
        "has_data": False,
    }


def build_workshop_report_docx(context):
    """Construit le document Word du rapport complet des ateliers."""
    animation_report = context.get("animation_report") or _empty_animation_report()

    doc = Document()
    _style_document(doc)
    _add_cover(doc, context)
    _add_header_footer(doc, context)
    _add_sommaire(doc)
    _add_synthese(doc, context)
    doc.add_heading("Indicateurs clés", level=1)
    _add_kpi_table(doc, context, animation_report)
    _add_monthly(doc, context)
    _add_types_and_communes(doc, context, animation_report)
    _add_animations_by_commune(doc, animation_report)
    _add_global_animations(doc, animation_report, context)
    _add_tops(doc, context)
    _add_communication(doc, context)
    _add_method(doc, context, animation_report)
    return doc
