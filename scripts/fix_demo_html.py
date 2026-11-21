"""
Fix all encoding artifacts and bug fixes in seek_demo.html.
Run from trace-main directory: python scripts/fix_demo_html.py
"""
import re

path = "backend/app/static/seek_demo.html"
content = open(path, "r", encoding="utf-8").read()
original_len = len(content)

# Fix 1: "assemble lower hinge" answer - replace the bad em-dash (—) artifact
# The artifact is \u2014 (em dash) appearing as replacement char in the answer field
# Find the assemble lower hinge block and fix it
old_answer = (
    'answer: "The retrieved procedural interval [E1] shows a lower hinge assembly step recorded in the IndEgo dataset. '
    'The annotation label for this interval is \u2018assemble\u2019 [E2]. Specific torque values and part names are not '
    'available from offline placeholder data \ufffd run via http://localhost:8000/demo/seek with Docker up for grounded live results."'
)
new_answer = (
    'answer: "The retrieved procedural interval [E1] shows a lower hinge assembly step recorded in the IndEgo dataset. '
    'The annotation label for this interval is \'assemble\' [E2]. Specific torque values and part names are not '
    'available from offline placeholder data - run via http://localhost:8000/demo/seek with Docker up for grounded live results."'
)

# More robust: replace any replacement chars (U+FFFD) throughout DEMO_RESPONSES
# U+FFFD is the Unicode replacement character shown as ?/diamond-question
content_fixed = content.replace('\ufffd', '-')

# Also fix curly quotes in DEMO_RESPONSES to straight quotes for clean JS strings
# \u2018 = left single quote, \u2019 = right single quote
content_fixed = content_fixed.replace('\u2018', "'").replace('\u2019', "'")

# Also fix em-dashes that appear as replacement chars in asset_title fields
# (the — in asset titles should stay as proper em dash, not replacement char)
# Those are already U+2014 in the file (the well-encoded ones) - we only fixed U+FFFD above

changes = len(content) - len(content_fixed) + content_fixed.count('\ufffd')  # just check
print(f"Original length: {original_len}")
print(f"Fixed length: {len(content_fixed)}")
replacement_chars = content.count('\ufffd')
print(f"Replacement chars fixed: {replacement_chars}")
curly_single = content.count('\u2018') + content.count('\u2019')
print(f"Curly single quotes fixed: {curly_single}")

open(path, "w", encoding="utf-8").write(content_fixed)
print("Done. File written.")
