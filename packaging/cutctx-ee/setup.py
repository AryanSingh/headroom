import os

from Cython.Build import cythonize
from setuptools import Extension, find_packages, setup

# Find all .py files in cutctx_ee to cythonize
extensions = []
for root, _dirs, files in os.walk("cutctx_ee"):
    # Skip tests directory — not needed in production wheel
    if "tests" in root:
        continue
    for file in files:
        if file.endswith(".py") and file != "__init__.py" and not file.endswith("api.py"):
            filepath = os.path.join(root, file)
            # e.g. cutctx_ee/billing/license_db.py -> cutctx_ee.billing.license_db
            module_name = filepath.replace(os.path.sep, ".")[:-3]
            extensions.append(Extension(module_name, [filepath]))

setup(
    ext_modules=cythonize(
        extensions, compiler_directives={"language_level": "3"}, build_dir="build/cython"
    ),
    # Include all subpackages (memory_service, ledger, policy, etc.)
    packages=find_packages(where=".", include=["cutctx_ee", "cutctx_ee.*"]),
    include_package_data=True,
    package_data={
        "cutctx_ee": ["MANIFEST.sha256.json", "LICENSE", "*.py"],
        "cutctx_ee.audit": ["*.py"],
        "cutctx_ee.billing": ["*.py"],
        "cutctx_ee.ledger": ["*.py"],
        "cutctx_ee.memory_service": ["*.py"],
        "cutctx_ee.policy": ["*.py"],
    },
)
