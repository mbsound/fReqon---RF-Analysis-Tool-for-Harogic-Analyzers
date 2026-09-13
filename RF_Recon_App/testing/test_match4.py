import zipfile

fac_app_ids = set()
with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
    with z.open('facility.dat') as f:
        headers = f.readline().decode('utf-8').strip().split('|')
        app_idx = headers.index('license_filing_id')
        stat_idx = headers.index('facility_status')
        for line in f:
            parts = line.decode('utf-8', errors='ignore').split('|')
            if len(parts) > app_idx and parts[stat_idx] == 'LICEN':
                app_id = parts[app_idx].strip()
                if app_id:
                    fac_app_ids.add(app_id)

matched = 0
with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
    with z.open('app_location.dat') as f:
        headers = f.readline().decode('utf-8').strip().split('|')
        app_idx = headers.index('aloc_aapp_application_id')
        for line in f:
            parts = line.decode('utf-8', errors='ignore').split('|')
            if len(parts) > app_idx:
                if parts[app_idx].strip() in fac_app_ids:
                    matched += 1

print(f"Total LICEN facility_ids with license_filing_id: {len(fac_app_ids)}")
print(f"Matched in app_location: {matched}")
