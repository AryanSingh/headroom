import os

for root, _, files in os.walk('cutctx'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path) as f:
                try:
                    content = f.read()
                except UnicodeDecodeError:
                    continue

            new_content = content.replace('cutctx', 'cutctx')
            new_content = new_content.replace('Cutctx', 'CutCtx')
            new_content = new_content.replace('CUTCTX', 'CUTCTX')

            # Special case for aliases we added:
            new_content = new_content.replace('CutCtxError = CutCtxError', 'CutctxError = CutCtxError')
            new_content = new_content.replace('CutCtxConfigurationError = ConfigurationError', 'CutctxConfigurationError = ConfigurationError')
            new_content = new_content.replace('CutCtxContribution = CutCtxContribution', 'CutctxContribution = CutCtxContribution')
            new_content = new_content.replace('CutCtxMCPClientWrapper = CutCtxMCPClientWrapper', 'CutctxMCPClientWrapper = CutCtxMCPClientWrapper')
            new_content = new_content.replace('CutCtxMCPCompressor = CutCtxMCPCompressor', 'CutctxMCPCompressor = CutCtxMCPCompressor')

            if new_content != content:
                with open(path, 'w') as f:
                    f.write(new_content)

