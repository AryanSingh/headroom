import os

skip_dirs = {'.git', '.venv', '.pytest_cache', '__pycache__', 'node_modules', '.mypy_cache', '.ruff_cache', 'dist', 'build'}

for root, dirs, files in os.walk('.'):
    # Modifying dirs in-place will prune the search
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for file in files:
        if file.endswith('.py') or file.endswith('.md') or file.endswith('.txt') or file.endswith('.toml'):
            path = os.path.join(root, file)
            if 'scratch_' in path:
                continue

            try:
                with open(path, encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                continue

            new_content = content.replace('cutctx', 'cutctx')
            new_content = new_content.replace('Cutctx', 'Cutctx')
            new_content = new_content.replace('CUTCTX', 'CUTCTX')
            new_content = new_content.replace('CutCtx', 'Cutctx')

            # Keep aliases valid
            new_content = new_content.replace('CutctxError = CutctxError', 'CutctxError = CutctxError')
            new_content = new_content.replace('CutctxConfigurationError = ConfigurationError', 'CutctxConfigurationError = ConfigurationError')
            new_content = new_content.replace('CutctxContribution = CutctxContribution', 'CutctxContribution = CutctxContribution')
            new_content = new_content.replace('CutctxMCPClientWrapper = CutctxMCPClientWrapper', 'CutctxMCPClientWrapper = CutctxMCPClientWrapper')
            new_content = new_content.replace('CutctxMCPCompressor = CutctxMCPCompressor', 'CutctxMCPCompressor = CutctxMCPCompressor')

            if new_content != content:
                print(f"Updating {path}")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

