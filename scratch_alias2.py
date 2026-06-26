with open('cutctx/exceptions.py') as f:
    lines = f.read().splitlines()

new_lines = []
for line in lines:
    if 'CutCtxConfigError = CutctxConfigError' in line:
        new_lines.append('CutCtxConfigurationError = CutctxConfigurationError')
    else:
        new_lines.append(line)

with open('cutctx/exceptions.py', 'w') as f:
    f.write('\n'.join(new_lines) + '\n')

with open('cutctx/integrations/mcp/__init__.py', 'a') as f:
    f.write('\nCutCtxMCPCompressor = CutctxMCPCompressor\n')
    f.write('CutCtxMCPClientWrapperBase = CutctxMCPClientWrapperBase\n')
