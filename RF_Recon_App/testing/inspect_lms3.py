import zipfile
with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
    with z.open('facility.dat') as f:
        print("facility.dat:")
        print(f.readline().decode('utf-8').strip())
    with z.open('application.dat') as f:
        print("\napplication.dat:")
        print(f.readline().decode('utf-8').strip())
    with z.open('application_facility.dat') as f:
        print("\napplication_facility.dat:")
        print(f.readline().decode('utf-8').strip())
    with z.open('app_location.dat') as f:
        print("\napp_location.dat:")
        print(f.readline().decode('utf-8').strip())
