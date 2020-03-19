# -*- coding: utf-8 -*-
import os.path

from setuptools import setup, find_packages
from zbuilder import __version__


base_dir = os.path.dirname(__file__)


requirements = []
with open(os.path.join(base_dir, "requirements.txt")) as f:
    for req in f.read().splitlines():
        if '==' in req:
            requirements.append(req)

with open(os.path.join(base_dir, "README.md")) as f:
    long_description = f.read()

setup(
    name='zbuilder',
    version=__version__,
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
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: PyPy',
    ]
)
