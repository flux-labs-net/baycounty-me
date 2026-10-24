"""Counties the Sunbiz pipeline knows about. Add a county here (key, FIPS, name, ZIPs) to filter and match it.

ZIPs that cross a county line are listed under `shared_zips`: records there are kept, then checked by city.
"""
COUNTIES = {
    'bay': {
        'fips': '12005', 'name': 'Bay County', 'state': 'FL',
        'zips': {'32401', '32402', '32403', '32404', '32405', '32406', '32407', '32408', '32409', '32410', '32411',
                 '32412', '32413', '32417', '32438', '32444', '32466'},
        'shared_zips': {'32438', '32466'},  # Fountain, Youngstown: partly in Washington / Calhoun counties
        'cities': {'PANAMA CITY', 'PANAMA CITY BEACH', 'LYNN HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO BEACH',
                   'SOUTHPORT', 'YOUNGSTOWN', 'FOUNTAIN', 'TYNDALL AFB', 'PCB', 'PC', 'BAYOU GEORGE', 'HILAND PARK'},
    },
}


def county(key):
    return COUNTIES[key]
