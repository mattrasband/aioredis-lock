from pathlib import Path
from setuptools import find_packages, setup


__version__ = "0.0.1"


with open(Path(__file__).parent / "README.md") as f:
    long_description = f.read()


setup(
    author="Matt Rasband",
    author_email="matt.rasband@gmail.com",
    description="Wrapper to provide distributed locks in aioredis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=["aioredis"],
    name="aioredis-lock",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.7",
    url="https://github.com/mrasband/aioredis-lock",
    version=__version__,
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    keywords=["aioredis", "redis", "locking", "distributed", "asyncio"],
)
