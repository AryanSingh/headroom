from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize
import os

# Find all .py files in headroom_ee to cythonize
extensions = []
for root, dirs, files in os.walk('headroom_ee'):
    # Skip tests directory — not needed in production wheel
    if 'tests' in root:
        continue
    for file in files:
        if file.endswith('.py') and file != '__init__.py' and not file.endswith('api.py'):
            filepath = os.path.join(root, file)
            # e.g. headroom_ee/billing/license_db.py -> headroom_ee.billing.license_db
            module_name = filepath.replace(os.path.sep, '.')[:-3]
            extensions.append(Extension(module_name, [filepath]))

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={'language_level': "3"},
        build_dir="build/cython"
    ),
    # Include all subpackages (memory_service, ledger, policy, etc.)
    packages=find_packages(where='.', include=['headroom_ee', 'headroom_ee.*']),
    include_package_data=True,
    package_data={
        'headroom_ee': ['MANIFEST.sha256.json', 'LICENSE', '*.py'],
        'headroom_ee.audit': ['*.py'],
        'headroom_ee.billing': ['*.py'],
        'headroom_ee.ledger': ['*.py'],
        'headroom_ee.memory_service': ['*.py'],
        'headroom_ee.policy': ['*.py'],
    },
)
