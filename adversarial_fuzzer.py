import os
import json
import traceback
from headroom.compress import compress

def iter_source_files(base_dir):
    for root, dirs, files in os.walk(base_dir):
        # exclude hidden, venv, tests
        if '.venv' in root or '.git' in root or '__pycache__' in root or 'tests' in root:
            continue
        for file in files:
            if file.endswith(('.py', '.json', '.js', '.ts', '.md', '.txt')):
                yield os.path.join(root, file)

def run_fuzzer():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'headroom'))
    files = list(iter_source_files(base_dir))
    
    print(f"Found {len(files)} source files to fuzz...")
    
    total_savings = []
    crashes = 0
    
    for fpath in files:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        ext = os.path.splitext(fpath)[1].lstrip('.')
        # Wrap content to help content router
        if ext in ('py', 'js', 'ts'):
            content = f"```{ext}\\n{content}\\n```"
        elif ext == 'json':
            content = f"```json\\n{content}\\n```"
            
        messages = [{"role": "user", "content": content}]
        raw_len = len(messages[0]["content"])
        
        # Only fuzz files large enough to trigger compression defaults
        if raw_len < 1000:
            continue
            
        try:
            # Force target_ratio low to ensure compression tries to act aggressively
            result = compress(messages, compress_user_messages=True, target_ratio=0.1, protect_recent=0, protect_analysis_context=False)
            comp_len = len(result.messages[0]["content"])
            savings = 0.0 if raw_len == 0 else 100 - (comp_len / raw_len * 100)
            total_savings.append(savings)
            
            # Don't print everything, just high savings or specific files
            if savings > 50:
                print(f"✅ {os.path.basename(fpath)}: {savings:.2f}% savings (router: {result.transforms_applied})")
                
        except Exception as e:
            crashes += 1
            print(f"❌ CRASH on {os.path.basename(fpath)}: {e}")
            traceback.print_exc()
            
    print("\\n--- Fuzzing Summary ---")
    print(f"Total files fuzzed: {len(total_savings)}")
    print(f"Total crashes: {crashes}")
    if total_savings:
        print(f"Average Savings: {sum(total_savings)/len(total_savings):.2f}%")
        print(f"Max Savings: {max(total_savings):.2f}%")
        
if __name__ == "__main__":
    os.environ["HEADROOM_TELEMETRY_DISABLED"] = "1"
    os.environ["CUTCTX_TELEMETRY_DISABLED"] = "1"
    run_fuzzer()
