"""
setup_data.py  –  One-time helper to copy the PDF books into data/raw/.

Run this once from the project root before building the index:
    python setup_data.py

It will look for the PDFs in common locations (project folder, parent folder,
current directory) and copy them to data/raw/.
"""

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
RAW_DIR      = PROJECT_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PDF_NAMES = [
    "Kliegman_Pediatric Decision-Making Strategies_2015.pdf",
    "A Case-Based Educational Guide-American Academy of Pediatrics (2022).pdf",
]

# Search these directories in order
SEARCH_DIRS = [
    PROJECT_ROOT,
    PROJECT_ROOT.parent,
    Path.home() / "Downloads",
    Path.home() / "Desktop",
]

found = []
for pdf_name in PDF_NAMES:
    dest = RAW_DIR / pdf_name
    if dest.exists():
        print(f"✓ Already in data/raw/: {pdf_name}")
        found.append(pdf_name)
        continue

    located = False
    for search_dir in SEARCH_DIRS:
        src = search_dir / pdf_name
        if src.exists():
            shutil.copy2(src, dest)
            print(f"✓ Copied: {src} → data/raw/")
            found.append(pdf_name)
            located = True
            break

    if not located:
        print(f"✗ NOT FOUND: {pdf_name}")
        print(f"  → Please copy it manually to: {RAW_DIR}")

print()
if len(found) == len(PDF_NAMES):
    print("All PDFs ready. Run: python src/build_index.py")
else:
    print(f"{len(found)}/{len(PDF_NAMES)} PDFs found. Copy the missing ones to data/raw/ manually.")
