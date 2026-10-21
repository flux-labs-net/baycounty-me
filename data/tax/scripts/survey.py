import json,sys
d=json.load(open(sys.argv[1]))
codes={}
for f,ys in d.items():
    kind='exp' if 'expend' in f else 'rev'
    for y,v in ys.items():
        cu=sum((r['funds'].get('Custodial') or 0) for r in v['rows'])
        cp=sum((r['funds'].get('Component Units') or 0) for r in v['rows'])
        pen=sum((r['funds'].get('Pension') or 0) for r in v['rows'])
        if cu or cp or pen: print(f,y,'custodial',cu,'component',cp,'pension',pen)
        for r in v['rows']:
            codes.setdefault(kind,{})[str(r['code'])]=r['name']
for k in codes:
    print('==',k)
    for c in sorted(codes[k],key=float): print(c,codes[k][c])
