with open('cutctx/exceptions.py') as f:
    content = f.read()

content = content.replace('CutCtxConfigurationError = CutctxConfigurationError', 'CutCtxConfigurationError = ConfigurationError')

with open('cutctx/exceptions.py', 'w') as f:
    f.write(content)
