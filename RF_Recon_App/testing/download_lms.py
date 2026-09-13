import requests
import os
url = "https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/Current_LMS_Dump.zip"
zip_path = "fcc_temp.zip"
if not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1.6e9:
    print("Downloading FCC Dump...")
    headers = {'User-Agent': 'python-urllib/3.10'}
    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                f.write(chunk)
    print("Downloaded!")
else:
    print("Already downloaded.")
