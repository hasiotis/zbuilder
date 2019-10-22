# -*- coding: utf-8 -*-
import os.path

from setuptools import setup, find_packages


with open('LICENSE') as f:
    license = f.read()

requirements = []
with open('requirements.txt') as f:
    for req in f.read().splitlines():
        if '==' in req:
            requirements.append(req)

with open('VERSION') as f:
    version = f.read()

assets_path = os.path.join('zbuilder', 'assets')
assets_files = [(d, [os.path.join(d, f) for f in files]) for d, folders, files in os.walk(assets_path)]

setup(
    name='zbuilder',
    version=version.rstrip(),
    description='Create VMs',
    author='Chasiotis Nikos',
    author_email='hasiotis@gmail.com',
    url='https://github.com/hasiotis/zbuilder',
    license=license,
    install_requires=requirements,
    entry_points={
        'console_scripts': ['zbuilder=zbuilder.cli:cli'],
    },
    packages=find_packages(exclude=('tests', 'docs')),
    include_package_data=True,
    package_data={'zbuilder': ['assets/*']}
)
