import re,json,sys,glob,html
D=sys.argv[1]
def money(s): return round(float(s.replace('$','').replace(',','')),2)
out={}
for f in sorted(glob.glob(D+'/cand_*.html')):
    ca=re.search(r'cand_(\d+)',f).group(1)
    t=open(f,encoding='utf-8',errors='replace').read()
    avail=re.findall(r'ReportPeriodName">([^<]*)</span>\s*<span class="ReportPeriodDate">([^<]*)<',t)
    rows=[]
    for m in re.finditer(r'<tr role="row">(.*?)</tr>',t,re.S):
        b=m.group(1)
        a=re.search(r'dhc=(\d+)[^>]*>([^<]*)<br>\(([^)]*)\)\s*([^<]*)</a>',b)
        if not a: continue
        vals=re.findall(r'class="Value">\s*(\$[-\d,.]+)\s*<',b)
        p1,p2=[x.strip() for x in a.group(3).split('-')]
        rows.append(dict(rpt=a.group(1),code=a.group(2).strip(),start=p1,end=p2,amended='Amended' in a.group(4),mon=money(vals[0]),ik=money(vals[1]),exp=money(vals[2])))
    out[ca]=dict(avail=avail,reports=rows)
json.dump(out,open(D+'/pages.json','w'),indent=1)
for k,v in out.items(): print(k,len(v['avail']),len(v['reports']),round(sum(r['mon'] for r in v['reports']),2),v['reports'][-1] if v['reports'] else None)
