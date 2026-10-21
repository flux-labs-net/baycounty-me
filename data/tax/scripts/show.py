import json,sys
d=json.load(open(sys.argv[1]))
for g in d['governments']:
    if g['id'] not in sys.argv[2].split(','): continue
    for y in g['years']:
        print(g['id'],y['fy']); print(' REV',y.get('revenues')); print(' DET',y.get('revenue_detail')); print(' EXP',y.get('expenditures'))
        print(' excl',y.get('revenue_excluded_funds'),y.get('expenditure_excluded_funds'))
