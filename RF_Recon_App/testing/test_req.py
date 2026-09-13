import requests
url = "https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/Current_LMS_Dump.zip"
headers = {'User-Agent': 'python-urllib/3.10'}
r = requests.get(url, headers=headers, stream=True)
print(r.status_code)
for i, chunk in enumerate(r.iter_content(chunk_size=1024)):
    print(f"Chunk {i} size {len(chunk)}")
    if i > 2:
        break
