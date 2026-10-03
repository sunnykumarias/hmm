import subprocess
import sys
import time
import os

NUM_WORKERS = 2
WORKER_SCRIPT = "insta_worker.py"

def start_workers():
    print(f"[*] Starting {NUM_WORKERS} workers in parallel...")
    processes = []
    
    for i in range(1, NUM_WORKERS + 1):
        # Set unique WORKER_ID for each process
        env = os.environ.copy()
        env["WORKER_ID"] = f"W{i}"
        
        # Start the worker script as a subprocess
        p = subprocess.Popen(
            [sys.executable, WORKER_SCRIPT],
            env=env
        )
        processes.append(p)
        print(f"[+] Worker {i} started with PID {p.pid}")
        # Thoda delay taaki ek sath load na pade
        time.sleep(2)
        
    try:
        # Wait for all processes to finish (infinite loop since workers restart themselves)
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        print("\n[*] Stopping all workers...")
        for p in processes:
            p.terminate()
        print("[*] All workers stopped.")

if __name__ == "__main__":
    start_workers()
