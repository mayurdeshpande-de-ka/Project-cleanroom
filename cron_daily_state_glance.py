import os
import subprocess
import time

def run_nightly_aggregation():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Nightly State Glance Aggregation...")
    
    scripts = [
        # 1. Base Data (LGD, Joshua, Ejal, etc.)
        ("scratch_build_state_data.py", "Building Base Data"),
        
        # 2. Form 20 Heavy Aggregation (~40 mins)
        ("scratch_patch_form20.py", "Aggregating Form 20 Data"),
        
        # 3. True Booth Counts
        ("scratch_fix_booths.py", "Updating True Booth Counts"),
        
        # 4. True Zone Populations
        ("scratch_patch_true_zones.py", "Mapping True Zone Populations"),
        
        # 5. By-Polls and Quality Remarks
        ("scratch_master_patch.py", "Finalizing By-Polls & Remarks")
    ]
    
    for script, description in scripts:
        print(f"\n---> {description} ({script})")
        start_t = time.time()
        
        try:
            # We use python to run the script
            result = subprocess.run(
                ["python", script], 
                cwd=os.path.dirname(os.path.abspath(__file__)),
                check=True
            )
            print(f"[OK] Completed in {round(time.time() - start_t, 2)}s")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Script {script} failed with exit code {e.returncode}")
            # If Form 20 fails, we might still want to run the patches on what exists,
            # but generally we should log the error.

    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Nightly Aggregation Complete!")

if __name__ == "__main__":
    run_nightly_aggregation()
