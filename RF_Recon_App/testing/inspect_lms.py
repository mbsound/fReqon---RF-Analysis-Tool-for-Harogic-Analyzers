import urllib.request
import zipfile
import os

url = "https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/Current_LMS_Dump.zip"
zip_path = "temp_lms.zip"

if not os.path.exists(zip_path):
    print("Downloading...")
    urllib.request.urlretrieve(url, zip_path)

with zipfile.ZipFile(zip_path, 'r') as z:
    print("Files in ZIP:", z.namelist())
    if 'facility.dat' in z.namelist():
        with z.open('facility.dat') as f:
            headers = f.readline().decode('utf-8').strip().split('|')
            print("\nfacility.dat headers:")
            for i, h in enumerate(headers):
                print(f"[{i}] {h}")

os.remove(zip_path)
