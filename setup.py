#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = ["Click>=6.0", "tensorflow>=1.13.1"]

setup_requirements = ["pytest-runner"]

test_requirements = ["pytest"]

setup(
    author="Matej Urbas",
    author_email="matej.urbas@gmail.com",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    description="Deep release notes helps you manage release notes for your project.",
    entry_points={
        "console_scripts": ["deep-release-notes=deep_release_notes.cli:main"]
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="deep_release_notes",
    name="deep_release_notes",
    packages=find_packages(include=["deep_release_notes"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/urbas/deep_release_notes",
    version="0.0.1",
    zip_safe=False,
)
