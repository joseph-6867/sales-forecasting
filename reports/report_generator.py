# ================================================================
# reports/report_generator.py  —  PDF & Excel Report Generation
# ================================================================

import io
import pandas as pd
import numpy as np
from datetime import datetime
from reportlab.lib.pagesizes  import letter, A4
from reportlab.lib.styles     import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units       import inch
from reportlab.lib             import colors
from reportlab.platypus        import (SimpleDocTemplate, Paragraph, Spacer,
                                       Table, TableStyle, HRFlowable, PageBreak)
from reportlab.lib.enums       import TA_CENTER, TA_LEFT, TA_RIGHT


# ── Colour constants for PDF ──────────────────────────────────
_PRIMARY   = colors.HexColor("#6366F1")
_SUCCESS   = colors.HexColor("#10B981")
_WARNING   = colors.HexColor("#F59E0B")
_DANGER    = colors.HexColor("#EF4444")
_BG        = colors.HexColor("#1E293B")
_TEXT      = colors.HexColor("#1E293B")
_LIGHT     = colors.HexColor("#F1F5F9")
_BORDER    = colors.HexColor("#E2E8F0")


def _styles():
    ss = getSampleStyleSheet()
    custom = {
        "Title": ParagraphStyle("Title", parent=ss["Title"],
                                fontSize=22, textColor=_PRIMARY,
                                spaceAfter=6, alignment=TA_CENTER),
        "H1": ParagraphStyle("H1", parent=ss["Heading1"],
                              fontSize=14, textColor=_PRIMARY, spaceAfter=4),
        "H2": ParagraphStyle("H2", parent=ss["Heading2"],
                              fontSize=12, textColor=_TEXT, spaceAfter=4),
        "Body": ParagraphStyle("Body", parent=ss["Normal"],
                               fontSize=9, textColor=_TEXT, spaceAfter=2),
        "Caption": ParagraphStyle("Caption", parent=ss["Normal"],
                                  fontSize=8, textColor=colors.grey,
                                  spaceAfter=2, alignment=TA_CENTER),
        "Kpi": ParagraphStyle("Kpi", parent=ss["Normal"],
                              fontSize=11, textColor=_PRIMARY,
                              spaceAfter=2, alignment=TA_CENTER),
    }
    # Register custom styles into the stylesheet (avoid accessing private attrs)
    for name, style in custom.items():
        # ensure the style has the correct name
        style.name = name
        try:
            ss.add(style)
        except Exception:
            # If a style with this name already exists, replace it
            if name in ss.byName:
                ss.byName[name] = style
            else:
                ss.add(style)
    return ss, custom


def _table_style(header_color=None):
    hc = header_color or _PRIMARY
    return TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  hc),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0),  9),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE",      (0,1), (-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [_LIGHT, colors.white]),
        ("GRID",          (0,0), (-1,-1), 0.4, _BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ])


# ── PDF Report ────────────────────────────────────────────────

def generate_pdf_report(project_name, kpis, monthly_df,
                         forecast_df, insights, recommendations,
                         model_metrics=None):
    """
    Generate a full PDF business report.
    Returns bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=0.75*inch, rightMargin=0.75*inch,
                             topMargin=0.75*inch,  bottomMargin=0.75*inch)
    ss, cs = _styles()
    story  = []
    now    = datetime.now().strftime("%B %d, %Y")

    # ── Cover ──────────────────────────────────────────────
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("📊 Sales Forecasting Platform", cs["Title"]))
    story.append(Paragraph("Business Analytics Report", cs["H1"]))
    story.append(HRFlowable(width="100%", thickness=2, color=_PRIMARY))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"Project: <b>{project_name}</b>", cs["Body"]))
    story.append(Paragraph(f"Generated: {now}", cs["Body"]))
    story.append(Paragraph(f"Date Range: {kpis.get('date_range','N/A')}", cs["Body"]))
    story.append(Spacer(1, 0.3*inch))

    # ── KPI Summary Table ──────────────────────────────────
    story.append(Paragraph("Executive KPI Summary", cs["H1"]))
    story.append(Spacer(1, 0.1*inch))

    def _fmt(v):
        try:
            fv = float(v)
            if abs(fv) >= 1_000_000: return f"${fv/1_000_000:.2f}M"
            if abs(fv) >= 1_000:      return f"${fv/1_000:.1f}K"
            return f"{fv:,.2f}"
        except: return str(v)

    kpi_rows = [
        ["Metric", "Value"],
        ["Total Sales",    _fmt(kpis.get("total_sales", 0))],
        ["Average Sales",  _fmt(kpis.get("avg_sales", 0))],
        ["Max Transaction",_fmt(kpis.get("max_sales", 0))],
        ["Total Transactions", f"{int(kpis.get('transactions',0)):,}"],
        ["30-Day Growth",  f"{kpis.get('growth_pct',0):+.1f}%"],
        ["Date Range",     kpis.get("date_range","N/A")],
    ]
    t = Table(kpi_rows, colWidths=[3*inch, 3*inch])
    t.setStyle(_table_style())
    story.append(t)
    story.append(Spacer(1, 0.3*inch))

    # ── Monthly Sales Table ────────────────────────────────
    if monthly_df is not None and not monthly_df.empty:
        story.append(Paragraph("Monthly Sales Summary", cs["H1"]))
        story.append(Spacer(1, 0.1*inch))
        mdf = monthly_df.copy()
        cols = list(mdf.columns)
        rows = [cols] + [[str(round(v, 2)) if isinstance(v, float) else str(v)
                          for v in row] for row in mdf.head(24).values.tolist()]
        t2 = Table(rows, colWidths=[2.5*inch] * min(len(cols), 3))
        t2.setStyle(_table_style(_PRIMARY))
        story.append(t2)
        story.append(Spacer(1, 0.3*inch))

    # ── Model Metrics ──────────────────────────────────────
    if model_metrics:
        story.append(Paragraph("Model Performance Metrics", cs["H1"]))
        story.append(Spacer(1, 0.1*inch))
        m_rows = [["Model", "MAE", "RMSE", "R²", "MAPE"]]
        for m in model_metrics:
            m_rows.append([
                m.get("model_name",""),
                f"{m.get('mae',0):.2f}",
                f"{m.get('rmse',0):.2f}",
                f"{m.get('r2',0):.4f}",
                f"{m.get('mape',0):.2f}%",
            ])
        t3 = Table(m_rows, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1*inch, 1.1*inch])
        t3.setStyle(_table_style())
        story.append(t3)
        story.append(Spacer(1, 0.3*inch))

    # ── Forecast Table ─────────────────────────────────────
    if forecast_df is not None and not forecast_df.empty:
        story.append(Paragraph("Sales Forecast", cs["H1"]))
        story.append(Spacer(1, 0.1*inch))
        fdf = forecast_df.copy()
        if "date" in fdf.columns:
            fdf["date"] = pd.to_datetime(fdf["date"]).dt.strftime("%Y-%m-%d")
        f_rows = [list(fdf.columns)] + [
            [str(round(v, 2)) if isinstance(v, float) else str(v) for v in row]
            for row in fdf.head(30).values.tolist()
        ]
        t4 = Table(f_rows, colWidths=[2.5*inch, 2.5*inch])
        t4.setStyle(_table_style(_SUCCESS))
        story.append(t4)
        story.append(Spacer(1, 0.3*inch))

    story.append(PageBreak())

    # ── Insights ───────────────────────────────────────────
    story.append(Paragraph("Business Insights", cs["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BORDER))
    story.append(Spacer(1, 0.1*inch))
    for ins in insights:
        clean = ins.replace("**","").replace("*","")
        story.append(Paragraph(f"• {clean}", cs["Body"]))
    story.append(Spacer(1, 0.2*inch))

    # ── Recommendations ────────────────────────────────────
    story.append(Paragraph("AI Recommendations", cs["H1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_BORDER))
    story.append(Spacer(1, 0.1*inch))
    for rec in recommendations:
        clean = rec.replace("**","").replace("*","")
        story.append(Paragraph(f"→ {clean}", cs["Body"]))

    # ── Footer ─────────────────────────────────────────────
    story.append(Spacer(1, 0.4*inch))
    story.append(HRFlowable(width="100%", thickness=1, color=_BORDER))
    story.append(Paragraph(
        f"Generated by Sales Forecasting Platform  ·  {now}",
        cs["Caption"]
    ))

    doc.build(story)
    return buf.getvalue()


# ── Excel Report ──────────────────────────────────────────────

def generate_excel_report(project_name, kpis, monthly_df,
                           forecast_df, daily_df, model_metrics=None):
    """
    Generate a multi-sheet Excel workbook.
    Returns bytes.
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        wb = writer.book

        # ── Sheet 1: KPI Summary ──────────────────────────
        kpi_data = {
            "Metric": ["Total Sales","Average Sales","Max Transaction",
                       "Total Transactions","30-Day Growth","Date Range"],
            "Value": [
                round(float(kpis.get("total_sales",0)), 2),
                round(float(kpis.get("avg_sales",0)), 2),
                round(float(kpis.get("max_sales",0)), 2),
                int(kpis.get("transactions",0)),
                f"{kpis.get('growth_pct',0):+.1f}%",
                kpis.get("date_range","N/A"),
            ]
        }
        pd.DataFrame(kpi_data).to_excel(writer, sheet_name="KPI Summary", index=False)

        # ── Sheet 2: Monthly Sales ────────────────────────
        if monthly_df is not None and not monthly_df.empty:
            monthly_df.to_excel(writer, sheet_name="Monthly Sales", index=False)

        # ── Sheet 3: Daily Sales ──────────────────────────
        if daily_df is not None and not daily_df.empty:
            daily_df.head(500).to_excel(writer, sheet_name="Daily Sales", index=False)

        # ── Sheet 4: Forecast ─────────────────────────────
        if forecast_df is not None and not forecast_df.empty:
            fdf = forecast_df.copy()
            if "date" in fdf.columns:
                fdf["date"] = pd.to_datetime(fdf["date"]).dt.strftime("%Y-%m-%d")
            fdf.to_excel(writer, sheet_name="Forecast", index=False)

        # ── Sheet 5: Model Metrics ────────────────────────
        if model_metrics:
            pd.DataFrame(model_metrics).to_excel(
                writer, sheet_name="Model Metrics", index=False
            )

    return buf.getvalue()
