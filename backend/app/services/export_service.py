import io
import csv
import json
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def export_mom_csv(mom: Dict[str, Any]) -> str:
    """Generate CSV string of action items."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Task", "Owner", "Deadline", "Deadline Status", "Priority", "Status", "Evidence"])
    
    for item in mom.get("action_items", []):
        writer.writerow([
            item.get("task", ""),
            item.get("owner", ""),
            item.get("deadline", ""),
            item.get("deadline_status", ""),
            item.get("priority", ""),
            item.get("status", ""),
            item.get("evidence", "")
        ])
    return output.getvalue()

def export_mom_pdf(mom: Dict[str, Any]) -> bytes:
    """Generate high-quality PDF report using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1e293b')
    )
    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#2563eb'),
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )

    story = []
    
    # Title & Metadata
    story.append(Paragraph(f"Minutes of Meeting: {mom.get('meeting_title', 'Meeting')}", title_style))
    story.append(Spacer(1, 8))
    meta_text = f"<b>Date & Time:</b> {mom.get('date_time', '')} &nbsp;|&nbsp; <b>Duration:</b> {mom.get('duration', '')}<br/><b>Participants:</b> {', '.join(mom.get('participants', []))}<br/><b>Agenda:</b> {mom.get('agenda', '')}"
    story.append(Paragraph(meta_text, body_style))
    story.append(Spacer(1, 14))

    # Executive Summary
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(mom.get("executive_summary", ""), body_style))
    story.append(Spacer(1, 14))

    # Action Items Table
    story.append(Paragraph("Action Items & Commitments", h2_style))
    table_data = [["Task", "Owner", "Deadline", "Priority", "Status"]]
    for item in mom.get("action_items", []):
        table_data.append([
            Paragraph(item.get("task", ""), body_style),
            Paragraph(f"<b>{item.get('owner', '')}</b>", body_style),
            Paragraph(item.get("deadline", ""), body_style),
            Paragraph(item.get("priority", ""), body_style),
            Paragraph(item.get("status", ""), body_style)
        ])

    col_widths = [190, 80, 80, 60, 70]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # Decisions Taken
    story.append(Paragraph("Decisions Taken", h2_style))
    decisions = mom.get("decisions_taken", [])
    if decisions:
        for d in decisions:
            story.append(Paragraph(f"• <b>[{d.get('topic', 'General')}]:</b> {d.get('decision', '')}", body_style))
    else:
        story.append(Paragraph("No final decisions recorded.", body_style))
    story.append(Spacer(1, 10))

    # Conflicts & Risks
    conflicts = mom.get("conflicts_and_risks", [])
    if conflicts:
        story.append(Paragraph("Identified Conflicts & Risks", h2_style))
        for c in conflicts:
            story.append(Paragraph(f"• <b>{c.get('topic', 'Conflict')}:</b> {c.get('conflict', '')} <i>(Status: {c.get('status', '')})</i>", body_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()
