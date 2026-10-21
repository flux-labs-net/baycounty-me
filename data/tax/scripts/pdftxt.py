import sys, pdfplumber
for p in sys.argv[1:]:
    print("=====",p)
    with pdfplumber.open(p) as pdf:
        for pg in pdf.pages:
            print(pg.extract_text(layout=True))
