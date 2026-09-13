import zipfile
import traceback

try:
    with zipfile.ZipFile('fcc_temp.zip', 'r') as z:
        print("facility.dat headers:")
        with z.open('facility.dat') as f:
            print(f.readline().decode('utf-8').strip())
            print(f.readline().decode('utf-8').strip())
            
        print("\napp_location.dat headers:")
        with z.open('app_location.dat') as f:
            print(f.readline().decode('utf-8').strip())
            print(f.readline().decode('utf-8').strip())
            
        print("\napplication.dat headers:")
        with z.open('application.dat') as f:
            print(f.readline().decode('utf-8').strip())
            print(f.readline().decode('utf-8').strip())
except Exception as e:
    traceback.print_exc()
