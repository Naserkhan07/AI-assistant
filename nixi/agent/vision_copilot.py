"""
Nixi Multi-Modal Vision Co-Pilot (Live Screen Awareness)
Pillar 7:
1. Real-Time Visual Debugging:
   - Inspects active IDE (VS Code, Cursor, PyCharm), terminal tracebacks, browser DevTools.
   - Diagnoses syntax errors, type errors, CSS bugs, and provides clean code patches.
2. Video & Screen Summarization:
   - Extracts tabular data, charts, infographics, and structured data into Markdown and Desktop CSV files.
"""
from __future__ import annotations

import os
import re
from typing import Any, Tuple


class VisionCopilot:
    def __init__(self, llm_client: Any, screen_reader: Any):
        self.llm = llm_client
        self.screen_reader = screen_reader

    def debug_active_screen(self, query: str = "") -> str:
        """Captures active screen, locates errors/bugs in IDE/DevTools/terminal, and outputs diagnosis + fix."""
        img_bytes = self.screen_reader.capture_screen()
        if not img_bytes:
            return "Unable to capture screen for visual debugging."

        prompt = (
            "You are an expert AI Visual Debugging Co-Pilot. Look carefully at this screen capture.\n"
            "Task: Identify any code errors, compiler warnings, terminal tracebacks, DevTools console errors, "
            "or visual UI/CSS flaws visible on the screen.\n"
            f"User Context: {query or 'Find and explain any error or bug on my screen.'}\n\n"
            "Respond in this concise structured format:\n"
            "🔍 **Observed Error**: [File/line and exact error message seen]\n"
            "💡 **Root Cause**: [1-2 sentences explaining why this occurred]\n"
            "🛠️ **Recommended Fix**:\n"
            "```[language]\n[corrected code or terminal command]\n```"
        )

        return self.llm.analyze_screen(img_bytes, prompt=prompt)

    def extract_screen_table_or_data(self, query: str = "") -> Tuple[str, str]:
        """Captures screen, extracts structured table/infographic data, and saves to Desktop as CSV/Markdown."""
        img_bytes = self.screen_reader.capture_screen()
        if not img_bytes:
            return "Unable to capture screen for extraction.", ""

        prompt = (
            "You are an expert OCR and data extraction agent. Look at this screen capture.\n"
            "Task: Extract all structured tabular, chart, or infographic data visible into a clean GitHub Markdown table.\n"
            "Do not include conversational preamble. Return only the markdown table or list of structured data."
        )

        markdown_table = self.llm.analyze_screen(img_bytes, prompt=prompt)

        # Attempt to save a CSV copy to Desktop
        saved_file = ""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            out_path = os.path.join(desktop, "extracted_screen_data.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"# Extracted Screen Data\n\n{markdown_table}\n")
            saved_file = out_path
        except Exception:
            pass

        return markdown_table, saved_file
