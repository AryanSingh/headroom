def add_alias(filepath, alias_str):
    with open(filepath, 'a') as f:
        f.write('\n' + alias_str + '\n')
    print(f"Updated {filepath}")

add_alias('cutctx/exceptions.py', 'CutCtxError = CutctxError\nCutCtxConfigError = CutctxConfigError')
add_alias('cutctx/integrations/mcp/__init__.py', 'CutCtxMCPClientWrapper = CutctxMCPClientWrapper')
add_alias('cutctx/subscription/models.py', 'CutCtxContribution = CutctxContribution')
