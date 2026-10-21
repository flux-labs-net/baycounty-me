import sys, openpyxl
for f in sys.argv[1:]:
    wb=openpyxl.load_workbook(f)
    print('FILE',f.split('/')[-1],[ws.title for ws in wb.worksheets])
    ws=wb.worksheets[0]
    for r in ws.iter_rows(min_row=3,max_row=5,values_only=True): print(r)
    for r in ws.iter_rows(min_row=ws.max_row-12,max_row=ws.max_row,values_only=True):
        if any(c is not None for c in r): print([c for c in r][:4], [c for c in r][14:18])
