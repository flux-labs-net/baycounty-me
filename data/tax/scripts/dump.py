import sys
exec(open('/home/claude/tax/scripts/xlrows.py').read().split("p=sys.argv[1]")[0])
p=sys.argv[1]; sheets=sys.argv[2].split(',') if len(sys.argv)>2 and sys.argv[2] else None
key=sys.argv[3] if len(sys.argv)>3 else 'Bay'
hdr={}
for sh,r in rows(p):
    if sheets and sh not in sheets: continue
    hdr.setdefault(sh,0)
    line=' | '.join('' if v is None else str(v) for v in r)
    if not line.strip(' |'): continue
    first=str(r[0]).strip() if r and r[0] is not None else ''
    if hdr[sh]<6 or first.lower()==key.lower():
        print(sh,'>',line[:900]); hdr[sh]+=1
