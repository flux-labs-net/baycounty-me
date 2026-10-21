import sys
exec(open('/home/claude/tax/scripts/xlrows.py').read().split("p=sys.argv[1]")[0])
p=sys.argv[1]; sheet=sys.argv[2]; pat=(sys.argv[3] if len(sys.argv)>3 else '').lower()
for sh,r in rows(p):
    if sh!=sheet: continue
    line=' | '.join('' if v is None else str(v) for v in r)
    if line.strip(' |') and (not pat or pat in line.lower() or 'county' in line.lower()[:30]): print(line[:900])
