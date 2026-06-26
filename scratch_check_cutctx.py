import os

count = 0
for root, _, files in os.walk('cutctx'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path) as f:
                try:
                    content = f.read()
                except UnicodeDecodeError:
                    continue
                if 'cutctx' in content or 'Cutctx' in content or 'CUTCTX' in content:
                    print(f"Found in {path}")
                    count += 1
print(f"Total files with cutctx: {count}")
