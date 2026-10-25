import sys, os, json, openpyxl, re
D=sys.argv[1]; out=sys.argv[2]
FUNDS=None
res={}
for f in sorted(os.listdir(D)):
    if not f.endswith('.xlsx'): continue
    wb=openpyxl.load_workbook(os.path.join(D,f))
    for yr in [str(y) for y in range(2015, 2026)]:
        if yr not in wb.sheetnames: continue
        ws=wb[yr]
        rows=list(ws.iter_rows(values_only=True))
        hdr=[c for c in rows[3]]
        title=rows[0][0]; fye=rows[1][0]
        nf=next((i for i,c in enumerate(hdr) if c=='Account Total'),15)  # older sheets have fewer fund columns
        funds=hdr[3:nf]
        det=[]; pop=None
        for r in rows[4:]:
            if r[1] is not None and isinstance(r[1],(int,float)):
                det.append({'code':r[1],'name':r[2],'funds':dict(zip(funds,r[3:nf]))})
            if r[0] and str(r[0]).startswith('Total - All'):
                tot_row=True
        # population: numeric in col Q (index 16) after total row
        for r in rows:
            if r[0] is None and r[1] is None and isinstance(r[16] if len(r)>16 else None,(int,float)):
                pop=r[16]
            vals=[c for c in r if c is not None]  # older sheets: '2015 Municipal Population:', 19287
            if pop is None and len(vals)>=2 and isinstance(vals[0],str) and 'Population' in vals[0] and isinstance(vals[1],(int,float)):
                pop=vals[1]
        res.setdefault(f,{})[yr]={'title':title,'fye':fye,'funds':funds,'pop':pop,'rows':det}
json.dump(res,open(out,'w'),indent=0,default=str)
for f in res:
    print(f, {y:(len(v['rows']),v['pop'],v['fye']) for y,v in res[f].items()})
    print('  funds', set(tuple(v['funds']) for v in res[f].values()))
