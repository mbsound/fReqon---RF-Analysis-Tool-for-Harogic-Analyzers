import zipfile
with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
    with z.open('application_facility.dat') as f:
        headers = f.readline().decode('utf-8').strip().split('|')
        for i, h in enumerate(headers):
            print(f"[{i}] {h}")
