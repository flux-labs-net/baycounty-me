import re,sys
lines=open(sys.argv[1]).read().split("\n")
start=[i for i,l in enumerate(lines) if "Fund 001 - General Fund" in l][0]
end=[i for i,l in enumerate(lines) if "Fund 101 - Transportation" in l][0]
dept=None; out=[]
for l in lines[start:end]:
    m=re.match(r'^(\d{4})\s*-\s*(.+)$',l.strip())
    if m: dept=m.group(1)+" "+m.group(2); continue
    if l.startswith("$") or l.startswith("($"):
        vals=re.findall(r'\(?\$[\d,]+\)?',l)
        if len(vals)>=4 and dept:
            v=int(vals[3].strip('()$').replace(',',''))
            out.append((dept,v)); dept=None
for d,v in out: print(f"{v:>12,} {d}")
print(sum(v for d,v in out))
