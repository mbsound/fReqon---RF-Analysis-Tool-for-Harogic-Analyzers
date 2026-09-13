import zipfile
with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
    with z.open('facility.dat') as f:
        headers = f.readline().decode('utf-8').strip().split('|')
        for line in f:
            parts = line.decode('utf-8', errors='ignore').split('|')
            if parts[headers.index('facility_status')] == 'LICENSED':
                print(parts[headers.index('callsign')], parts[headers.index('facility_id')], parts[headers.index('license_filing_id')])
                break
