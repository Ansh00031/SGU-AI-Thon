"""Script to locate existing PPTX templates and generate a complete presentation matching the hackathon format."""

import glob
import os
import sys
from pathlib import Path

# Search common user locations for any existing PPTX files
search_dirs = [
    Path.home() / "Downloads",
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path(r"C:\Users\ansh6\.gemini\antigravity\scratch"),
]

found_pptx = []
for d in search_dirs:
    if d.exists():
        for p in d.glob("*.pptx"):
            found_pptx.append(p)
        for p in d.glob("*bharat*.ppt*"):
            found_pptx.append(p)
        for p in d.glob("*hackathon*.ppt*"):
            found_pptx.append(p)

print("Found PPTX files:", found_pptx)
