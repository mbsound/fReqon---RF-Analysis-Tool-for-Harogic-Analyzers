import os
files = [
    "066_5230500d00220016_rfacal.txt",
    "066_5230500d00220016_ifacal.txt",
    "066_5230500d00220016_config.txt",
    "066_ampcomp.txt",
    "DL0752_ampcomp.txt"
]
model = 66
uid = int("5230500d00220016", 16)
print(f"UID is {uid}")

model_str = f"{model:03d}"
uid_str = f"{uid:016x}"
print(f"Expected RFACAL: {model_str}_{uid_str}_rfacal.txt")

for f in files:
    name = os.path.basename(f).lower()
    if f"{model_str}_{uid_str}_rfacal.txt" in name:
        print("rfacal found")
    elif f"{model_str}_{uid_str}_ifacal.txt" in name:
        print("ifacal found")
    elif f"{model_str}_{uid_str}_config.txt" in name:
        print("config found")
    elif f"{model_str}_ampcomp.txt" in name:
        print("base ampcomp found")
    elif "ampcomp.txt" in name and not name.startswith(model_str):
        print(f"module ampcomp found: {name}")
