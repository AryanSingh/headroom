import os


def replace_in_file(filepath):
    with open(filepath) as f:
        content = f.read()

    new_content = content.replace('cutctx', 'cutctx').replace('Cutctx', 'CutCtx').replace('CUTCTX', 'CUTCTX')

    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, _, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            replace_in_file(os.path.join(root, file))
