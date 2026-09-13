import multiprocessing, queue, ctypes, time
from device_controller import hardware_process
cmd = multiprocessing.Queue()
data = multiprocessing.Queue()
p = multiprocessing.Process(target=hardware_process, args=(cmd, data, 1e9, 2e9, False, None))
p.start()
cmd.put("start")
start = time.time()
counts = 0
while time.time() - start < 3.0:
    try:
        msg, content = data.get(timeout=0.1)
        if msg == "data":
            x, y = content
            print(f"X range: {x[0]} to {x[-1]}, length {len(x)}")
            counts += 1
            if counts > 2: break
    except queue.Empty: pass
p.terminate()
