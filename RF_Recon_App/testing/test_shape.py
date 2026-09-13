import numpy as np
power_np = np.zeros(20000)
temp_spec = np.zeros(4048)
i = 4 # last hop
start_idx = i * 4048
end_idx = (i + 1) * 4048
power_np[start_idx:end_idx] = temp_spec
