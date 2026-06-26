import os

spdx_header = """# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""

for root, _, files in os.walk("cutctx_ee"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path) as f:
                content = f.read()
            if "SPDX-License-Identifier" not in content:
                with open(path, "w") as f:
                    f.write(spdx_header + content)
                print(f"Added to {path}")
