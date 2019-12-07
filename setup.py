# -*- coding: utf-8 -*-
import os.path

from setuptools import setup, find_packages

base_dir = os.path.dirname(__file__)


requirements = []
with open(os.path.join(base_dir, "requirements.txt")) as f:
    for req in f.read().splitlines():
        if '==' in req:
            requirements.append(req)

with open(os.path.join(base_dir, "VERSION")) as f:
    version = f.read()

with open(os.path.join(base_dir, "README.md")) as f:
    long_description = f.read()

assets_path = os.path.join('zbuilder', 'assets')
assets_files = [(d, [os.path.join(d, f) for f in files]) for d, folders, files in os.walk(assets_path)]

setup(
    name='zbuilder',
    version=version.rstrip(),
    description='Create VMs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Chasiotis Nikos',
    author_email='hasiotis@gmail.com',
    url='https://github.com/hasiotis/zbuilder',
    license="GPLv3+",
    install_requires=requirements,
    packages=find_packages(exclude=('tests', 'docs')),
    entry_points={
        'console_scripts': ['zbuilder=zbuilder.cli:cli'],
    },
    data_files=assets_files
)
