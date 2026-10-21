def rows(p):
    if p.endswith('.xls'):
        import xlrd
        b=xlrd.open_workbook(p)
        for s in b.sheets():
            for r in range(s.nrows): yield s.name, [s.cell_value(r,c) for c in range(s.ncols)]
    else:
        import openpyxl
        b=openpyxl.load_workbook(p,read_only=True,data_only=True)
        for s in b.worksheets:
            for r in s.iter_rows(values_only=True): yield s.title, list(r)
p=sys.argv[1]; pat=sys.argv[2].lower() if len(sys.argv)>2 else None; n=int(sys.argv[3]) if len(sys.argv)>3 else 12
