#!/usr/bin/env python3
# coding=utf-8
import sys

import download_wrapper
from setuptools import setup, find_packages


cmdclass = {}
try:
    from sphinx.setup_command import BuildDoc
    cmdclass = {'build_sphinx': BuildDoc}
except ImportError:
    pass

name = download_wrapper.__NAME__
version = download_wrapper.__VERSION__
release = download_wrapper.__RELEASE__

setup(
    name=name,
    cmdclass=cmdclass,
    version=version,
    keywords=download_wrapper.__KEYWORDS__,
    description=download_wrapper.__DESC__,
    license=download_wrapper.__LICENSE__,
    author=download_wrapper.__AUTHOR__,
    author_email=download_wrapper.__AUTHOR_EMAIL__,
    url=download_wrapper.__URL__,
    packages=find_packages(),
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ),
    command_options={
        'build_sphinx': {
            'project': ('setup.py', name),
            'version': ('setup.py', version),
            'release': ('setup.py', release),
        },
    },
)
