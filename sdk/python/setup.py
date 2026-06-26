from setuptools import find_packages, setup

setup(
    name="cutctx-sdk",
    version="0.1.0",
    description="Python SDK for Cutctx — AI context compression proxy",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Cutctx Labs",
    author_email="hello@cutctx.dev",
    url="https://github.com/cutctx/cutctx",
    license="Apache-2.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],
    extras_require={
        "dev": ["pytest>=7.0"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries",
    ],
)
