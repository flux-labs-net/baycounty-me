import sys, pdfplumber
with pdfplumber.open(sys.argv[1]) as pdf:
    for pg in pdf.pages:
        print(pg.extract_text())
        for t in pg.extract_tables(): 
            for r in t: print(r)
