import sys, pdfplumber
with pdfplumber.open(sys.argv[1]) as p:
    for i,pg in enumerate(p.pages):
        print(f"=== PAGE {i+1} ===")
        print(pg.extract_text() or "")
