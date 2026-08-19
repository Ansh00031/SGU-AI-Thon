"""Generate a professional, publication-quality PDF report for the Autonomous OS Debugging Agent.

Sections covered:
1. Explanation of Project
2. How It Works (Technical Architecture & Pipeline)
3. Why It Is Important (Impact, Security & Enterprise ROI)
4. Offline Servicing Mode & WinRE Disaster Recovery
"""

import os
import subprocess
import sys
from pathlib import Path

# Ensure reportlab is installed
try:
    import reportlab
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
    )
    from reportlab.pdfgen import canvas
except ImportError:
    print("[*] Installing reportlab...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
    import reportlab
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
    )
    from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page numbers and running footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#718096"))

        # Top Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "Autonomous OS Debugging Agent — Technical Project Report")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.75)
            self.line(54, 742, 558, 742)

        # Bottom Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_text)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — BUILD WITH BHARAT 2.0")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(54, 48, 558, 48)
        self.restoreState()


def build_pdf(filename="OS_Debugger.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY = colors.HexColor("#1A365D")   # Deep Navy
    SECONDARY = colors.HexColor("#DD6B20") # Vibrant Orange Accent
    DARK_TEXT = colors.HexColor("#2D3748") # Charcoal
    MUTED_TEXT = colors.HexColor("#4A5568")
    BG_LIGHT = colors.HexColor("#F7FAFC")
    BORDER_COLOR = colors.HexColor("#CBD5E0")
    GREEN_ACCENT = colors.HexColor("#2F855A")

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=PRIMARY,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceAfter=15,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14.5,
        textColor=DARK_TEXT,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    callout_style = ParagraphStyle(
        "Callout_Custom",
        parent=body_style,
        fontName="Helvetica-Oblique",
        fontSize=9.5,
        leading=13.5,
        textColor=PRIMARY,
    )

    code_style = ParagraphStyle(
        "Code_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1A202C"),
    )

    story = []

    # ==========================================
    # COVER / HEADER
    # ==========================================
    story.append(Paragraph("Autonomous OS Debugging Agent", title_style))
    story.append(Paragraph("AI-Powered Real-Time Operating System Diagnostics, Remediation & Disaster Recovery", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=SECONDARY, spaceBefore=0, spaceAfter=12))

    meta_table_data = [
        [
            Paragraph("<b>Project:</b> Autonomous OS Debugging Agent", body_style),
            Paragraph("<b>Hackathon:</b> Build With Bharat 2.0", body_style),
        ],
        [
            Paragraph("<b>Author / Team:</b> KernelHealers (Ansh & Team)", body_style),
            Paragraph("<b>Core Stack:</b> Python, Typer, Rich, PowerShell, OpenAI/Ollama", body_style),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[250, 250])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 1: EXPLANATION OF PROJECT
    # ==========================================
    story.append(Paragraph("1. Explanation of the Project", h1_style))
    story.append(Paragraph(
        "The <b>Autonomous OS Debugging Agent</b> is an intelligent, terminal-based local systems engineering agent "
        "designed to diagnose, troubleshoot, and safely remediate complex operating system errors (such as Windows Update "
        "access denials <code>0x80070005</code>, service startup faults, and corrupted component stores) without requiring "
        "manual research or dangerous trial-and-error commands.",
        body_style
    ))
    story.append(Paragraph(
        "Unlike generic LLM chatbots that produce blind advice without machine context, our agent acts as an autonomous "
        "Tier-3 Systems Administrator. It directly interfaces with kernel-level APIs and system loggers, executes non-destructive "
        "verification probes, generates production-grade PowerShell remediation scripts, and executes fixes under strict human supervision.",
        body_style
    ))

    # Key Highlights Box
    box_1 = [
        [Paragraph(
            "<b>Key Core Objective:</b> Eliminate the friction and risks of OS troubleshooting by replacing cryptic error codes, "
            "unverified forum copy-pasting, and lengthy IT support tickets with an automated, self-healing diagnostic loop.",
            callout_style
        )]
    ]
    t_box1 = Table(box_1, colWidths=[500])
    t_box1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EBF8FF")),
        ('LINELEFT', (0, 0), (-1, -1), 3.5, colors.HexColor("#3182CE")),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(t_box1)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 2: HOW IT WORKS
    # ==========================================
    story.append(Paragraph("2. How It Works (Technical Architecture & Pipeline)", h1_style))
    story.append(Paragraph(
        "The agent operates through a rigorous <b>5-step closed-loop reasoning pipeline</b>, ensuring that no modifying actions "
        "occur without prior telemetry verification and human consent:",
        body_style
    ))

    steps_data = [
        ("Step 1: Privilege Verification & Environment Scaffolding",
         "On launch, the agent verifies elevation (Administrator via <code>ctypes.windll.shell32.IsUserAnAdmin</code> or POSIX root). "
         "It loads LLM configurations and dynamic system paths to ensure core Windows utilities (<code>System32</code>, PowerShell) are accessible."),

        ("Step 2: Live Log Ingestion & Telemetry Gathering",
         "The agent queries the Windows Event Viewer using PowerShell and WMI to extract the last 50 Critical (Level 1) and Error (Level 2) "
         "events across <code>System</code>, <code>Application</code>, and <code>WindowsUpdateClient</code> channels, packaging them into structured JSON."),

        ("Step 3: AI Diagnostic Engine & Safe Read-Only Probing",
         "An LLM reasoning loop formulates an initial hypothesis and outputs a suite of strictly read-only diagnostic commands (e.g. "
         "<code>icacls</code>, <code>Get-Service</code>, <code>Get-ItemProperty</code>). An execution sandbox validates commands against a destructive "
         "regex blacklist, executes them, and feeds stdout/stderr back to the LLM to confirm the true root cause."),

        ("Step 4: Fix Proposal & Human-in-the-Loop Approval",
         "Once the root cause is proven, the AI synthesizes a targeted PowerShell remediation script. The script is rendered in the terminal "
         "with Monokai syntax highlighting and requires an affirmative <code>[Y/n]</code> confirmation before execution."),

        ("Step 5: Sandboxed Execution, Verification & Snapshot Rollback",
         "Before executing, a pre-fix snapshot and inverse rollback script are saved to <code>.backups/&lt;session_id&gt;/</code>. The fix runs via "
         "an isolated temporary file with guaranteed cleanup in <code>finally:</code> blocks. A final post-fix check confirms service restoration."),
    ]

    for title, desc in steps_data:
        story.append(Paragraph(f"• <b>{title}:</b> {desc}", bullet_style))

    story.append(Spacer(1, 10))

    # Architecture Table
    arch_data = [
        [Paragraph("<b>Pipeline Stage</b>", body_style), Paragraph("<b>Key Technologies / APIs</b>", body_style), Paragraph("<b>Safety Mechanism</b>", body_style)],
        [Paragraph("Telemetry Ingestion", body_style), Paragraph("Get-WinEvent, WMI, platform", body_style), Paragraph("Read-only memory extraction", body_style)],
        [Paragraph("Hypothesis & Probing", body_style), Paragraph("OpenAI GPT-4o / Ollama Llama 3.1", body_style), Paragraph("Strict Regex Command Blacklist", body_style)],
        [Paragraph("Human Approval Gate", body_style), Paragraph("Typer Prompt, Rich Syntax Box", body_style), Paragraph("Mandatory explicit [Y/n] confirmation", body_style)],
        [Paragraph("Remediation & Rollback", body_style), Paragraph("Subprocess, WinReg, .backups/", body_style), Paragraph("1-Click instant state reversal", body_style)],
    ]
    t_arch = Table(arch_data, colWidths=[130, 180, 190])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    for row in range(len(arch_data)):
        if row == 0:
            for col in range(len(arch_data[0])):
                arch_data[row][col].style.textColor = colors.white
    story.append(t_arch)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 3: WHY IT IS IMPORTANT
    # ==========================================
    story.append(Paragraph("3. Why Is It Important? (Value & Enterprise Impact)", h1_style))
    story.append(Paragraph(
        "Operating system errors are among the most expensive and time-consuming problems in both consumer computing "
        "and enterprise DevOps infrastructure. The Autonomous OS Debugging Agent provides three transformative advantages:",
        body_style
    ))

    reasons = [
        ("Drastic Reduction in Downtime (Hours to Seconds)",
         "Traditional OS troubleshooting averages 45–90 minutes per incident involving manual log extraction, forum searches, "
         "and reboot cycles. The agent diagnoses and verifies solutions in under 15 seconds."),

        ("Zero-Hallucination Grounding",
         "Generic LLMs often hallucinate outdated or harmful registry commands because they lack real-time visibility into the machine. "
         "Our agent verifies actual filesystem ACLs and service statuses through live read-only probes before ever proposing a fix."),

        ("Enterprise Security & Air-Gapped Compliance",
         "The agent supports 100% offline execution via local Ollama models (e.g. Llama 3.1, Mistral). Defense, healthcare, "
         "and banking workstations with strict compliance policies can debug mission-critical machines without data leaving the subnet."),

        ("Deterministic Rollback (Zero-Risk Experimentation)",
         "Every remediation automatically generates a pre-fix snapshot and an inverse rollback script. If a fix produces unintended side effects, "
         "running <code>python agent.py rollback</code> restores baseline system configurations in less than one second."),
    ]

    for title, desc in reasons:
        story.append(Paragraph(f"<b>✓ {title}:</b> {desc}", bullet_style))

    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 4: OFFLINE MODE & WINRE
    # ==========================================
    story.append(Paragraph("4. Offline Mode & Windows Recovery Environment (WinRE)", h1_style))
    story.append(Paragraph(
        "A critical challenge in systems engineering is: <i>What happens if a computer cannot even boot into the Windows desktop "
        "(e.g., stuck in an automatic reboot loop or blue screen on startup)?</i>",
        body_style
    ))
    story.append(Paragraph(
        "To solve catastrophic boot failures, the agent includes an <b>Offline Servicing Architecture</b> that runs inside "
        "the <b>Windows Recovery Environment (WinRE) Command Prompt</b> or from a <b>Bootable AI Rescue USB</b>.",
        body_style
    ))

    story.append(Paragraph("A. How to Trigger WinRE During a Boot Loop", h2_style))
    winre_steps = [
        ("The 3-Time Power Cut Safety Trigger:", "Power on the machine; as soon as the manufacturer logo appears, press and hold Power for 8 seconds to force shut off. Repeat this 2–3 times. Windows automatically redirects into 'Preparing Automatic Repair'."),
        ("Manufacturer Hardware Hotkeys:", "Press brand-specific recovery keys during power-on: HP (<code>F11</code>), Dell (<code>F12/F8</code>), Lenovo (<code>F11 / Novo button</code>), Asus (<code>F9</code>), Acer (<code>Alt + F10</code>)."),
        ("Accessing the Command Prompt:", "Inside the blue WinRE screen, navigate to: <b>Troubleshoot ➔ Advanced options ➔ Command Prompt</b> (which opens <code>X:\\windows\\system32&gt;cmd.exe</code>)."),
    ]
    for title, desc in winre_steps:
        story.append(Paragraph(f"• <b>{title}</b> {desc}", bullet_style))

    story.append(Spacer(1, 6))
    story.append(Paragraph("B. Autonomous Offline Servicing Capabilities", h2_style))
    story.append(Paragraph(
        "When launched from WinRE targeting the internal offline drive (<code>python agent.py diagnose --offline-drive C:</code>), the agent performs:",
        body_style
    ))

    offline_caps = [
        ("Offline Event Log & Minidump Parsing:", "Directly parses <code>C:\\Windows\\System32\\winevt\\Logs\\System.evtx</code> and memory dumps (<code>C:\\Windows\\Minidump\\*.dmp</code>) to identify the crashing driver or faulting service."),
        ("Reverting Pending Update Actions:", "Executes <code>dism.exe /Image:C:\\ /Cleanup-Image /RevertPendingActions</code> to safely roll back corrupted Windows Updates that caused the crash."),
        ("Offline System Binary Verification:", "Executes <code>sfc.exe /scannow /offbootdir=C:\\ /offwindir=C:\\Windows</code> to reconstruct missing system files."),
        ("Disabling Faulting Drivers Offline:", "Loads and edits the offline registry hive (<code>C:\\Windows\\System32\\config\\SYSTEM</code>) to disable malfunctioning third-party driver services before the next boot."),
    ]
    for title, desc in offline_caps:
        story.append(Paragraph(f"• <b>{title}</b> {desc}", bullet_style))

    story.append(Spacer(1, 10))

    # Summary Callout Box
    box_winre = [
        [Paragraph(
            "<b>Emergency Disaster Recovery Summary:</b> The agent is not restricted to healthy operating systems. "
            "Through WinRE and offline DISM servicing, it revives non-booting machines and prevents unnecessary hard drive reformatting.",
            callout_style
        )]
    ]
    t_winre = Table(box_winre, colWidths=[500])
    t_winre.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FFF4")),
        ('LINELEFT', (0, 0), (-1, -1), 3.5, GREEN_ACCENT),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(t_winre)

    # Build PDF with two-pass canvas for page numbering
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Successfully built PDF report: {filename}")


if __name__ == "__main__":
    out_name = sys.argv[1] if len(sys.argv) > 1 else "OS_Debugger.pdf"
    build_pdf(out_name)
