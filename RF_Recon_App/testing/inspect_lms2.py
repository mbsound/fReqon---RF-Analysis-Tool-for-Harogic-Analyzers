import urllib.request
import zipfile
import os

url = "https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/Current_LMS_Dump.zip"
zip_path = "temp_lms.zip"

if not os.path.exists(zip_path):
    urllib.request.urlretrieve(url, zip_path)

with zipfile.ZipFile(zip_path, 'r') as z:
    with z.open('application.dat') as f:
        headers = f.readline().decode('utf-8').strip().split('|')
        print("application.dat headers:")
        for i, h in enumerate(headers):
            print(f"[{i}] {h}")
