from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# Find all .py files in headroom_ee to cythonize
extensions = []
for root, dirs, files in os.walk('headroom_ee'):
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
    # We still want to package any __init__.py files as normal Python code
    # to maintain module structure, but logic files will be .so
    packages=['headroom_ee', 'headroom_ee.billing', 'headroom_ee.audit'],
)
