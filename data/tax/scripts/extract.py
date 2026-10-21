import sys, os, json, openpyxl, re
D=sys.argv[1]; out=sys.argv[2]
FUNDS=None
res={}
for f in sorted(os.listdir(D)):
    if not f.endswith('.xlsx'): continue
    wb=openpyxl.load_workbook(os.path.join(D,f))
    for yr in ['2021','2022','2023','2024','2025']:
        if yr not in wb.sheetnames: continue
        ws=wb[yr]
        rows=list(ws.iter_rows(values_only=True))
        hdr=[c for c in rows[3]]
        title=rows[0][0]; fye=rows[1][0]
        funds=hdr[3:15]
        det=[]; pop=None
        for r in rows[4:]:
            if r[1] is not None and isinstance(r[1],(int,float)):
                det.append({'code':r[1],'name':r[2],'funds':dict(zip(funds,r[3:15]))})
            if r[0] and str(r[0]).startswith('Total - All'):
                tot_row=True
        # population: numeric in col Q (index 16) after total row
        for r in rows:
            if r[0] is None and r[1] is None and isinstance(r[16] if len(r)>16 else None,(int,float)):
                pop=r[16]
        res.setdefault(f,{})[yr]={'title':title,'fye':fye,'funds':funds,'pop':pop,'rows':det}
json.dump(res,open(out,'w'),indent=0,default=str)
for f in res:
    print(f, {y:(len(v['rows']),v['pop'],v['fye']) for y,v in res[f].items()})
    print('  funds', set(tuple(v['funds']) for v in res[f].values()))
