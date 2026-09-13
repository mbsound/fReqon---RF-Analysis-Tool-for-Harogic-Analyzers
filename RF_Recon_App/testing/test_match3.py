import zipfile
stats = set()
with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
    with z.open('facility.dat') as f:
        headers = f.readline().decode('utf-8').strip().split('|')
        for line in f:
            parts = line.decode('utf-8', errors='ignore').split('|')
            if len(parts) > headers.index('facility_status'):
                stats.add(parts[headers.index('facility_status')])
print(stats)
