import sys,pdfplumber
for f in sys.argv[1:]:
  with pdfplumber.open(f) as p:
    pg=p.pages[0]; ws=pg.extract_words()
    for w in ws:
      if w['text'] in ('1','2','3','4','5','6','7','8','9','10') and 140<w['top']<200: print('hdr',w['text'],round(w['x0']),round(w['x1']))
    bay=[w for w in ws if w['text']=='Bay']
    for b in bay:
      print(f[-40:],[(w['text'],round(w['x0']),round(w['x1'])) for w in ws if abs(w['top']-b['top'])<2])
