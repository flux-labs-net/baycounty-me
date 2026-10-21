import json,sys
d=json.load(open(sys.argv[1]))
B='https://edr.state.fl.us/content/local-government/data/revenues-expenditures/'
GOV=[('bay_county','Bay County (county government)','baycounty','cntyfiscal'),
 ('panama_city','City of Panama City','panamacity','munifiscal'),
 ('panama_city_beach','City of Panama City Beach','panamacitybeach','munifiscal'),
 ('lynn_haven','City of Lynn Haven','lynnhaven','munifiscal'),
 ('callaway','City of Callaway','callaway','munifiscal'),
 ('springfield','City of Springfield','springfield','munifiscal'),
 ('parker','City of Parker','parker','munifiscal'),
 ('mexico_beach','City of Mexico Beach','mexicobeach','munifiscal')]
INCL=['General','Special Revenue','Debt Service','Capital Projects','Permanent','Enterprise']
GOVF=['General','Special Revenue','Debt Service','Capital Projects','Permanent']
EXCL=['Internal Service','Custodial','Pension','Trust','Private Purpose','Component Units']
RB=['Property taxes','Sales & other local taxes','Permits, fees & special assessments','State & federal money','Charges for services (incl. utilities)','Fines','Interest & other','Debt proceeds & transfers (not revenue)']
EB=['General government','Courts (county court-related)','Public safety','Physical environment','Transportation','Economic environment','Human services','Culture & recreation','Debt service','Transfers & other']
def rb(c):
    i=int(c)
    if i==311: return 'Property taxes',None
    if 312<=i<=319: return 'Sales & other local taxes',None
    if 320<=i<=329: return 'Permits, fees & special assessments',None
    if 330<=i<=339:
        s='Federal grants & payments (331, 333)' if i in (331,333) else 'State grants (334)' if i==334 else 'State shared revenues (335)' if i==335 else 'Other state assistance (332)' if i==332 else 'Other local governments (337-339)'
        return 'State & federal money',s
    if 340<=i<=349: return 'Charges for services (incl. utilities)',None
    if 350<=i<=359: return 'Fines',None
    if 360<=i<=369: return 'Interest & other',None
    if 380<=i<=389:
        s='Transfers in (381)' if i==381 else 'Debt & lease proceeds (383-384)' if i in (383,384) else 'Other (382, 385-389)'
        return 'Debt proceeds & transfers (not revenue)',s
    raise Exception(c)
def eb(c):
    i=int(c)
    if i==517 or i==591: return 'Debt service'
    if 511<=i<=519: return 'General government'
    if 520<=i<=529: return 'Public safety'
    if 530<=i<=539: return 'Physical environment'
    if 540<=i<=549: return 'Transportation'
    if 550<=i<=559: return 'Economic environment'
    if 560<=i<=569: return 'Human services'
    if 570<=i<=579: return 'Culture & recreation'
    if 580<=i<=599: return 'Transfers & other'
    if 600<=i<=799: return 'Courts (county court-related)'
    raise Exception(c)
def s(r,fs): return sum((r['funds'].get(f) or 0) for f in fs)
out={'governments':[]}; checks=[]
for gid,name,fn,folder in GOV:
    R=d.get(fn+'revenues.xlsx',{}); E=d.get(fn+'expenditures.xlsx',{})
    g={'id':gid,'name':name,'years':[]}
    for y in ['2021','2022','2023','2024','2025']:
        r=R.get(y); e=E.get(y)
        if not r and not e: continue
        yo={'fy':'FY'+y,'fiscal_year_end':(r or e)['fye'].replace('Local Fiscal Year Ended ',''),'population':(r or e)['pop']}
        if r:
            rev={k:0 for k in RB}; det={}; gov=0; excl={k:0 for k in EXCL}; alltot=0
            for row in r['rows']:
                b,sb=rb(row['code']); v=s(row,INCL); rev[b]+=v
                if sb: det.setdefault(b,{}); det[b][sb]=det[b].get(sb,0)+v
                if b!=RB[-1]: gov+=s(row,GOVF)
                for k in EXCL: excl[k]+=(row['funds'].get(k) or 0)
                alltot+=s(row,INCL+EXCL)
            yo['revenues']=rev; yo['revenue_detail']=det
            yo['revenue_total']=sum(rev[k] for k in RB[:-1])
            yo['revenue_total_incl_other_sources']=sum(rev.values())
            yo['revenue_total_governmental_funds_only']=gov
            yo['revenue_excluded_funds']=excl
            yo['revenue_all_funds_as_published']=alltot
            yo['revenue_source_title']=r['title']+' - '+r['fye']; yo['revenue_source_url']=B+folder+'/'+fn+'revenues.xlsx'
        else:
            yo['revenues']=None; yo['revenue_total']=None
        if e:
            ex={k:0 for k in EB}; gov=0; excl={k:0 for k in EXCL}; alltot=0
            for row in e['rows']:
                b=eb(row['code']); ex[b]+=s(row,INCL)
                gov+=s(row,GOVF)
                for k in EXCL: excl[k]+=(row['funds'].get(k) or 0)
                alltot+=s(row,INCL+EXCL)
            if gid!='bay_county': ex.pop('Courts (county court-related)')
            yo['expenditures']=ex
            yo['expenditure_total']=sum(ex.values())
            yo['expenditure_total_excl_transfers']=yo['expenditure_total']-ex['Transfers & other']
            yo['expenditure_total_governmental_funds_only']=gov
            yo['expenditure_excluded_funds']=excl
            yo['expenditure_all_funds_as_published']=alltot
            yo['expenditure_source_title']=e['title']+' - '+e['fye']; yo['expenditure_source_url']=B+folder+'/'+fn+'expenditures.xlsx'
        else:
            yo['expenditures']=None; yo['expenditure_total']=None
        yo['source_title']='EDR, Expenditures and Revenues Reported by Florida\'s Local Governments (compiled from DFS Annual Financial Reports), sheet '+y
        yo['source_url']=B+('cntyfiscal.cfm' if folder=='cntyfiscal' else 'munifiscal.cfm')
        g['years'].append(yo)
    out['governments'].append(g)
json.dump(out,open(sys.argv[2],'w'),indent=1)
for g in out['governments']:
    for y in g['years']:
        print(g['id'],y['fy'],y['population'],'rev',y['revenue_total'],'exp',y['expenditure_total'])
