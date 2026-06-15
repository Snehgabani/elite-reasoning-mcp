import concurrent.futures
import time
import os
from autonomous_loop import EliteLooper

def run_single_loop(loop_idx):
    brain_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "brain"))
    looper = EliteLooper(brain_dir)
    print(f"--- Starting Autonomous Loop Instance {loop_idx} ({looper.goal_id}) ---")
    
    start_time = time.time()
    success = looper.execute_loop(max_iterations=10)
    duration = time.time() - start_time
    
    return loop_idx, success, duration

def stress_test(num_concurrent=5):
    print(f"🚀 Starting Elite Looping Stress Test with {num_concurrent} concurrent autonomous agents...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        futures = [executor.submit(run_single_loop, i) for i in range(num_concurrent)]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                idx, success, duration = future.result()
                results.append((idx, success, duration))
            except Exception as exc:
                print(f"Instance generated an exception: {exc}")
                results.append((None, False, 0))

    print("\n" + "="*50)
    print("🎯 STRESS TEST COMPLETE")
    print("="*50)
    success_count = sum(1 for r in results if r[1])
    print(f"Total Agents: {num_concurrent}")
    print(f"Successful Exits: {success_count}")
    print(f"Failures (Max Iterations): {num_concurrent - success_count}")
    for idx, success, duration in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  Instance {idx}: {status} (Took {duration:.2f}s)")

if __name__ == "__main__":
    stress_test(num_concurrent=5)
