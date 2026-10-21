import sys
sys.argv.append('')
p,sheet,pat=sys.argv[1],sys.argv[2],sys.argv[3].lower()
exec(open('/home/claude/tax/scripts/xlrows.py').read())
for sh,r in rows(p):
    if sh!=sheet: continue
    line=' | '.join('' if v is None else str(v) for v in r)
    if line.strip(' |'): 
        if not pat or pat in line.lower(): print(line[:800])
