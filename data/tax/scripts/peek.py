import sys, openpyxl
wb=openpyxl.load_workbook(sys.argv[1],data_only=False)
for ws in wb.worksheets:
    print('SHEET',ws.title,ws.max_row,ws.max_column)
    for r in ws.iter_rows(min_row=1,max_row=int(sys.argv[2]),values_only=True):
        print([c for c in r if c is not None])
