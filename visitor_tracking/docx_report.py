"""Génération des exports DOCX du rapport annuel de fréquentation."""

from datetime import datetime

from django.contrib.staticfiles import finders
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

PRIMARY = RGBColor(0x4A, 0x6F, 0xA5)
DARK = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x5A, 0x6F, 0x80)
GREEN = RGBColor(0x15, 0x80, 0x3D)
RED = RGBColor(0xDC, 0x26, 0x26)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


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
    size=9,
    color=None,
    align=None,
    mono=False,
):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    if mono:
        run.font.name = "Consolas"
        run.font.size = Pt(7.5)
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


def _fmt_int(value):
    return f"{int(value):,}".replace(",", "\u00a0")


def _fmt_num(value):
    return f"{float(value):.1f}".replace(".", ",")


def _fmt_pct(value):
    if value is None:
        return "—"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_fmt_num(value)} %"


def _fmt_date(value):
    return value.strftime("%d/%m/%Y") if value else "—"


def _bar(value, max_value, width=18):
    if not max_value or not value:
        return ""
    filled = max(1, round(value / max_value * width))
    return "█" * filled


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


def _add_cover(doc, report, detailed):
    logo_path = finders.find("img/logo/logo.png")
    if logo_path:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(logo_path, width=Cm(4.5))

    for _ in range(3):
        doc.add_paragraph()

    title = "Rapport d'activité" if detailed else "Bilan d'activité"
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(title)
    run.bold = True
    run.font.size = Pt(28)
    run.font.color.rgb = PRIMARY

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(str(report["year"]))
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = DARK

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(report["scope"]["label"])
    run.font.size = Pt(18)
    run.font.color.rgb = PRIMARY

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(report["synthese"]["perimetre"])
    run.font.size = Pt(10.5)
    run.font.color.rgb = MUTED

    for _ in range(6):
        doc.add_paragraph()

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(f"Généré le {datetime.now():%d/%m/%Y à %H:%M}")
    run.font.size = Pt(10)
    run.font.color.rgb = MUTED

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(
        "Données agrégées par espace et par jour — aucun nominatif."
    )
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED

    doc.add_page_break()


def _add_sommaire(doc):
    doc.add_heading("Sommaire", level=1)
    entries = [
        "Synthèse",
        "Évolution mensuelle",
        "Par trimestre",
        "Moyenne par jour de semaine",
        "Faits marquants",
        "Détail par espace",
        "Meilleurs jours",
        "Qualité des pointages",
        "Fermetures",
        "Méthode et définitions",
        "Annexe — Répartition mensuelle par espace",
    ]
    for entry in entries:
        doc.add_paragraph(entry, style="List Bullet")
    doc.add_page_break()


def _add_header_footer(doc, report):
    section = doc.sections[0]
    section.different_first_page_header_footer = True

    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run(
        f"Rapport d'activité {report['year']} — " f"{report['scope']['label']}"
    )
    run.font.size = Pt(8)
    run.font.color.rgb = MUTED

    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run(f"{report['scope']['label']} — {report['year']} — page ")
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
    font_size=9,
    mono_columns=None,
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
            size=8.5,
            color=WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
        _set_cell_background(cell, "4A6FA5")
    _set_repeat_table_header(header_row)

    for values in rows:
        row = table.add_row()
        for index, value in enumerate(values):
            align = aligns[index] if aligns else None
            _set_cell(
                row.cells[index],
                value,
                size=font_size,
                align=align,
                mono=bool(mono_columns and index in mono_columns),
            )

    if widths:
        for row in table.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = Cm(width)
    return table


def _add_kpi_table(doc, report):
    totals = report["totals"]
    record = totals["record"]
    variation = totals["variation"]

    table = doc.add_table(rows=2, cols=3)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    cells = [
        (
            "Total visiteurs",
            _fmt_int(totals["total"]),
            f"sur {_fmt_int(totals['pointed_days'])} jours pointés",
            PRIMARY,
        ),
        (
            "Moyenne / jour pointé",
            _fmt_num(totals["avg_per_pointed_day"]),
            f"{_fmt_num(totals['avg_per_open_day'])} / jour ouvré pointé",
            PRIMARY,
        ),
        (
            f"Année {report['period']['n1_year']}",
            (_fmt_int(totals["n1_total"]) if totals["n1_has_data"] else "—"),
            (
                report["period"]["n1_label"]
                if totals["n1_has_data"]
                else "aucune donnée"
            ),
            PRIMARY,
        ),
        (
            "Variation vs N-1",
            _fmt_pct(variation),
            "vs année précédente",
            (
                GREEN
                if variation and variation > 0
                else RED if variation and variation < 0 else PRIMARY
            ),
        ),
        (
            "Jours pointés",
            _fmt_int(totals["pointed_days"]),
            (
                f"{_fmt_num(totals['completeness'])} % de complétude"
                if totals["completeness"] is not None
                else "méthode historique"
            ),
            PRIMARY,
        ),
        (
            "Record",
            _fmt_int(record["total"]) if record else "—",
            (f"{record['date']:%d/%m/%Y}" if record else "aucun jour pointé"),
            PRIMARY,
        ),
    ]

    for index, (label, value, sub, color) in enumerate(cells):
        row = index // 3
        column = index % 3
        cell = table.rows[row].cells[column]
        cell.text = ""
        _set_cell_background(cell, "EEF3F9")

        paragraph = cell.paragraphs[0]
        run = paragraph.add_run(label.upper())
        run.font.size = Pt(7.5)
        run.font.color.rgb = MUTED
        run.bold = True

        paragraph = cell.add_paragraph()
        run = paragraph.add_run(value)
        run.font.size = Pt(18)
        run.bold = True
        run.font.color.rgb = color

        paragraph = cell.add_paragraph()
        run = paragraph.add_run(sub)
        run.font.size = Pt(7.5)
        run.font.color.rgb = MUTED

        cell.width = Cm(5.6)


def _add_synthese(doc, report):
    doc.add_heading("Synthèse", level=1)
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(f"Périmètre : {report['synthese']['perimetre']}")
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED

    phrases = report["synthese"]["phrases"]
    if not phrases:
        doc.add_paragraph("Aucune donnée pour rédiger la synthèse.")
        return

    doc.add_paragraph(phrases[0])
    for phrase in phrases[1:]:
        doc.add_paragraph(phrase, style="List Bullet")


def _add_monthly(doc, report):
    doc.add_heading("Évolution mensuelle", level=1)
    monthly = report["monthly"]
    max_total = max((row["total"] for row in monthly), default=0)
    rows = []
    for row in monthly:
        if row["is_future"]:
            total = "—"
            n1 = "—"
            variation = "—"
            share = "—"
            bar = ""
        else:
            total = _fmt_int(row["total"])
            n1 = _fmt_int(row["n1"]) if row["n1"] else "—"
            variation = _fmt_pct(row["variation"])
            share = f"{_fmt_num(row['share'])} %"
            bar = _bar(row["total"], max_total)
        label = row["month"]
        if row["is_current"]:
            label += " (en cours)"
        rows.append([label, total, n1, variation, share, bar])

    _add_table(
        doc,
        ["Mois", "Total", "N-1", "Variation", "Part", "Visualisation"],
        rows,
        widths=[3.4, 2.2, 2.2, 2.2, 1.8, 4.2],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            None,
        ],
        mono_columns={5},
    )
    if report["period"]["is_partial"]:
        doc.add_paragraph(
            "Les mois à venir ne sont pas comptés dans l'année en cours."
        ).runs[0].font.size = Pt(8)


def _add_quarterly(doc, report):
    doc.add_heading("Par trimestre", level=1)
    rows = []
    for row in report["quarterly"]:
        label = row["name"]
        if row["is_current"]:
            label += " (en cours)"
        rows.append(
            [
                label,
                _fmt_int(row["total"]),
                _fmt_int(row["n1"]) if row["n1"] else "—",
                _fmt_pct(row["variation"]),
                f"{_fmt_num(row['share'])} %",
            ]
        )
    _add_table(
        doc,
        ["Trimestre", "Total", "N-1", "Variation", "Part"],
        rows,
        widths=[3.2, 2.8, 2.8, 2.8, 2.4],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )


def _add_weekday(doc, report):
    doc.add_heading("Moyenne par jour de semaine", level=1)
    rows = [
        [
            row["name"],
            _fmt_int(row["total"]),
            _fmt_num(row["avg"]),
            f"{_fmt_num(row['share'])} %",
        ]
        for row in report["weekday"]
    ]
    _add_table(
        doc,
        ["Jour", "Total", "Moyenne", "Part"],
        rows,
        widths=[3.2, 3.2, 3.2, 3.2],
        aligns=[
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
            WD_ALIGN_PARAGRAPH.RIGHT,
        ],
    )
    if report["totals"]["sunday_days"]:
        doc.add_paragraph(
            f"{_fmt_int(report['totals']['sunday_days'])} dimanche(s) "
            f"pointé(s) : {_fmt_int(report['totals']['sunday_total'])} "
            "visiteurs (ouvertures exceptionnelles)."
        )


def _add_spaces(doc, report):
    doc.add_heading("Détail par espace", level=1)
    rows = []
    for space in report["spaces"]:
        label = space["name"]
        if not space["is_active"]:
            label += " (inactif)"
        rows.append(
            [
                label,
                _fmt_int(space["total"]),
                f"{_fmt_num(space['share'])} %",
                _fmt_num(space["avg"]) if space["days"] else "—",
                _fmt_int(space["days"]),
                _fmt_int(space["n1"]) if space["n1"] else "—",
                _fmt_pct(space["variation"]),
            ]
        )
    _add_table(
        doc,
        [
            "Espace",
            "Total",
            "Part",
            "Moy./jour",
            "Jours",
            "N-1",
            "Variation",
        ],
        rows,
        widths=[4.2, 2.0, 1.6, 1.8, 1.4, 1.8, 1.8],
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


def _add_highlights(doc, report):
    doc.add_heading("Faits marquants", level=1)
    totals = report["totals"]
    rows = []
    if totals["record"]:
        record = totals["record"]
        spaces = ", ".join(
            f"{item['name']} ({_fmt_int(item['total'])})" for item in record["spaces"]
        )
        rows.append(
            [
                "Meilleur jour",
                f"{_fmt_date(record['date'])} — "
                f"{_fmt_int(record['total'])} visiteurs",
            ]
        )
        if spaces:
            rows.append(["Détail du record", spaces])
    if totals["best_weekday"]:
        rows.append(
            [
                "Jour de semaine dominant",
                f"{totals['best_weekday']['name']} — "
                f"{_fmt_num(totals['best_weekday']['avg'])} visiteurs "
                "en moyenne",
            ]
        )
    if totals["best_month"]:
        rows.append(
            [
                "Mois le plus actif",
                f"{totals['best_month']['month']} — "
                f"{_fmt_int(totals['best_month']['total'])} visiteurs",
            ]
        )
    if report["best_week"]:
        week = report["best_week"]
        rows.append(
            [
                "Meilleure semaine",
                f"du {_fmt_date(week['start'])} au {_fmt_date(week['end'])} "
                f"— {_fmt_int(week['total'])} visiteurs",
            ]
        )
    if report["worst_week"]:
        week = report["worst_week"]
        rows.append(
            [
                "Semaine la plus calme",
                f"du {_fmt_date(week['start'])} au {_fmt_date(week['end'])} "
                f"— {_fmt_int(week['total'])} visiteurs",
            ]
        )

    if rows:
        _add_table(
            doc,
            ["Indicateur", "Valeur"],
            rows,
            widths=[4.5, 12.0],
            aligns=[None, None],
        )


def _add_top_days(doc, report):
    doc.add_heading("Meilleurs jours", level=1)
    rows = []
    for index, item in enumerate(report["top_days"], start=1):
        spaces = ", ".join(
            f"{space['name']} ({_fmt_int(space['total'])})" for space in item["spaces"]
        )
        rows.append(
            [
                index,
                _fmt_date(item["date"]),
                _fmt_int(item["total"]),
                spaces or "—",
            ]
        )
    if not rows:
        doc.add_paragraph("Aucun jour pointé avec des visiteurs.")
        return
    _add_table(
        doc,
        ["#", "Date", "Visiteurs", "Espaces"],
        rows,
        widths=[1.2, 3.2, 2.4, 10.0],
        aligns=[
            WD_ALIGN_PARAGRAPH.CENTER,
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            None,
        ],
    )


def _add_completeness(doc, report, compact=False):
    totals = report["totals"]
    if report["period"]["method"] != "v2":
        doc.add_heading("Qualité des pointages", level=1)
        doc.add_paragraph(
            "Méthode historique : les totaux et les moyennes sont "
            "conservés tels qu'ils ont été publiés. La complétude n'est "
            "pas recalculée pour cette année."
        )
        doc.add_paragraph(
            f"Jours pointés : {_fmt_int(totals['pointed_days'])}. "
            f"Dernière mise à jour : "
            f"{totals['last_update']:%d/%m/%Y %H:%M}"
            if totals["last_update"]
            else f"Jours pointés : {_fmt_int(totals['pointed_days'])}."
        )
        return

    if compact:
        doc.add_heading("Qualité des pointages", level=1)
        doc.add_paragraph(
            f"{_fmt_int(totals['open_pointed_days'])} jours d'ouverture "
            f"pointés sur {_fmt_int(totals['expected_days'])} attendus "
            f"({_fmt_num(totals['completeness'])} % de complétude)."
        )
        if totals["missing_days"]:
            doc.add_paragraph(
                f"{_fmt_int(totals['missing_days'])} jours d'ouverture "
                "sans pointage."
            )
        if totals["closure_days"]:
            doc.add_paragraph(
                f"{_fmt_int(totals['closure_days'])} jours de fermeture " "déclarés."
            )
        if totals["exceptional_days"]:
            doc.add_paragraph(
                f"{_fmt_int(totals['exceptional_days'])} pointage(s) sur "
                f"jour non ouvert ({_fmt_int(totals['exceptional_total'])} "
                "visiteurs)."
            )
        return

    doc.add_heading("Qualité des pointages", level=1)
    rows = [
        [
            "Jours d'ouverture",
            _fmt_int(totals["expected_days"]),
        ],
        [
            "Jours d'ouverture pointés",
            _fmt_int(totals["open_pointed_days"]),
        ],
        [
            "Jours d'ouverture sans pointage",
            _fmt_int(totals["missing_days"]),
        ],
        [
            "Complétude",
            f"{_fmt_num(totals['completeness'])} %",
        ],
        [
            "Jours de fermeture",
            _fmt_int(totals["closure_days"]),
        ],
        [
            "Pointages sur fermeture",
            _fmt_int(totals["closure_pointed_days"]),
        ],
        [
            "Jours pointés à zéro",
            _fmt_int(totals["zero_days"]),
        ],
        [
            "Dernière mise à jour",
            (
                f"{totals['last_update']:%d/%m/%Y %H:%M}"
                if totals["last_update"]
                else "—"
            ),
        ],
    ]
    if report["spaces_without_data"]:
        rows.append(
            [
                "Espaces sans pointage",
                ", ".join(space["name"] for space in report["spaces_without_data"]),
            ]
        )
    _add_table(
        doc,
        ["Indicateur", "Valeur"],
        rows,
        widths=[6.0, 10.5],
        aligns=[None, WD_ALIGN_PARAGRAPH.RIGHT],
    )
    if totals["sunday_days"]:
        doc.add_paragraph(
            f"{_fmt_int(totals['sunday_days'])} dimanche(s) pointé(s) "
            f"({_fmt_int(totals['sunday_total'])} visiteurs) : "
            "ouvertures exceptionnelles. Ils sont conservés dans le total "
            "mais ne sont pas comptés dans les jours attendus."
        )


def _add_closures(doc, report):
    doc.add_heading("Fermetures", level=1)
    rows = report.get("closure_rows") or []
    if not rows:
        doc.add_paragraph("Aucune fermeture déclarée sur la période.")
        return
    table_rows = [
        [
            f"Du {closure['start']:%d/%m/%Y} au {closure['end']:%d/%m/%Y}",
            closure["kind_label"],
            _fmt_int(closure["days"]),
            closure["label"] or "—",
        ]
        for closure in rows
    ]
    _add_table(
        doc,
        ["Période", "Motif", "Jours ouvrés", "Précision"],
        table_rows,
        widths=[5.0, 4.0, 2.2, 5.0],
        aligns=[
            None,
            None,
            WD_ALIGN_PARAGRAPH.RIGHT,
            None,
        ],
    )


def _add_method(doc, report, detailed=False):
    doc.add_heading("Méthode et définitions", level=1)
    period = report["period"]
    totals = report["totals"]

    doc.add_paragraph(f"Périmètre : {report['synthese']['perimetre']}.")
    doc.add_paragraph(f"Période : {period['label']} ({period['status_label']}).")
    doc.add_paragraph(
        "Source : pointages manuels saisis dans Médi@'pass, agrégés par "
        "espace et par jour. Aucune donnée nominative n'est utilisée."
    )

    if period["method"] == "v2":
        doc.add_paragraph(
            f"Jours d'ouverture habituels : "
            f"{period['opening_weekdays_label']}. Les jours habituellement "
            "fermés et les fermetures déclarées ne sont pas comptés dans "
            "les jours attendus."
        )
        doc.add_paragraph(
            f"Fermetures déclarées : {_fmt_int(totals['closure_days'])} "
            "jour(s) ouvré(s). Un pointage sur un jour non ouvert reste "
            "dans le total et est signalé comme ouverture exceptionnelle."
        )
        doc.add_paragraph(
            f"Moyenne par jour pointé : total ÷ nombre de dates pointées. "
            f"Ici : {_fmt_int(totals['total'])} ÷ "
            f"{_fmt_int(totals['pointed_days'])} = "
            f"{_fmt_num(totals['avg_per_pointed_day'])}."
        )
        if detailed:
            doc.add_paragraph(
                f"Moyenne par jour d'ouverture pointé : visiteurs des "
                f"jours ouverts ÷ jours d'ouverture pointés = "
                f"{_fmt_num(totals['avg_per_open_day'])}."
            )
    else:
        doc.add_paragraph(
            "Méthode historique : les totaux et les moyennes sont "
            "conservés tels qu'ils ont été publiés. La règle des dimanches "
            "et la complétude ne sont pas recalculées pour cette année."
        )

    doc.add_paragraph(
        f"Comparaison N-1 : {period['n1_label']} " f"({period['n1_year']})."
    )
    if period["n1_method_note"]:
        doc.add_paragraph(period["n1_method_note"])

    if detailed:
        doc.add_paragraph(
            "Les pourcentages de variation ne sont calculés que si la "
            "valeur N-1 est strictement positive ; sinon la cellule "
            "affiche « — »."
        )


def _add_annex(doc, report):
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Cm(29.7)
    section.page_height = Cm(21)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(1.5)
    section.right_margin = Cm(1.5)

    doc.add_heading("Annexe — Répartition mensuelle par espace", level=1)
    headers = ["Espace"] + report["matrix"]["months_short"] + ["Total"]
    rows = []
    for row in report["matrix"]["rows"]:
        rows.append(
            [row["name"]]
            + [_fmt_int(value) if value else "—" for value in row["values"]]
            + [_fmt_int(row["total"])]
        )
    _add_table(
        doc,
        headers,
        rows,
        widths=[3.8] + [1.55] * 12 + [1.9],
        aligns=[None] + [WD_ALIGN_PARAGRAPH.RIGHT] * 13,
        font_size=8,
    )
    doc.add_paragraph("Les mois à venir de l'année en cours sont à zéro.").runs[
        0
    ].font.size = Pt(8)


def build_annual_report_docx(report, detailed=False):
    """Construit le document Word du rapport annuel.

    Args:
        report: dictionnaire produit par ``AnnualReportService.build``.
        detailed: True pour le rapport détaillé, False pour le bilan.

    Returns:
        docx.Document: document prêt à être enregistré dans une réponse.
    """
    doc = Document()
    _style_document(doc)
    doc.core_properties.title = (
        f"{'Rapport' if detailed else 'Bilan'} d'activité "
        f"{report['year']} — {report['scope']['label']}"
    )
    doc.core_properties.author = "Médi@'pass"
    doc.core_properties.subject = "Rapport annuel de fréquentation"

    _add_cover(doc, report, detailed)
    _add_header_footer(doc, report)
    if detailed:
        _add_sommaire(doc)

    _add_kpi_table(doc, report)
    _add_synthese(doc, report)
    _add_monthly(doc, report)

    if detailed:
        _add_quarterly(doc, report)
        _add_weekday(doc, report)
        _add_highlights(doc, report)
        _add_spaces(doc, report)
        _add_top_days(doc, report)
        _add_completeness(doc, report, compact=False)
        _add_closures(doc, report)
        _add_method(doc, report, detailed=True)
        _add_annex(doc, report)
    else:
        doc.add_heading("Top des espaces", level=1)
        rows = []
        for index, space in enumerate(report["spaces"][:3], start=1):
            rows.append(
                [
                    index,
                    space["name"],
                    _fmt_int(space["total"]),
                    f"{_fmt_num(space['share'])} %",
                    _fmt_num(space["avg"]) if space["days"] else "—",
                ]
            )
        if rows:
            _add_table(
                doc,
                ["#", "Espace", "Total", "Part", "Moy./jour"],
                rows,
                widths=[1.2, 6.0, 3.0, 2.4, 2.4],
                aligns=[
                    WD_ALIGN_PARAGRAPH.CENTER,
                    None,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                    WD_ALIGN_PARAGRAPH.RIGHT,
                ],
            )
        else:
            doc.add_paragraph("Aucun espace avec des visiteurs.")

        _add_completeness(doc, report, compact=True)
        _add_method(doc, report, detailed=False)

    return doc
