import os

skip_dirs = {'.git', '.venv', '.pytest_cache', '__pycache__', 'node_modules', '.mypy_cache', '.ruff_cache', 'dist', 'build', 'target'}
valid_exts = {'.rs', '.c', '.json', '.go', '.java', '.yaml', '.yml', '.mdx', '.hcl', '.sh', '.ts'}

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for file in files:
        if any(file.endswith(ext) for ext in valid_exts):
            path = os.path.join(root, file)
            try:
                with open(path, encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                continue

            new_content = content.replace('cutctx', 'cutctx')
            new_content = new_content.replace('Cutctx', 'Cutctx')
            new_content = new_content.replace('CUTCTX', 'CUTCTX')
            new_content = new_content.replace('CutCtx', 'Cutctx')

            if new_content != content:
                print(f"Updating {path}")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
