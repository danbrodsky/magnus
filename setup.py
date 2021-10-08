#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import shutil

from glob import glob
from setuptools import setup

def datafilelist(installbase, sourcebase):
    datafileList = []
    for root, subFolders, files in os.walk(sourcebase):
        fileList = []
        for f in files:
            fileList.append(os.path.join(root, f))
        datafileList.append((root.replace(sourcebase, installbase), fileList))
    return datafileList


data_files = [
    ("{prefix}/share/man/man1".format(prefix=sys.prefix), glob("data/*.1")),
    (
        "{prefix}/share/applications".format(prefix=sys.prefix),
        [
            "data/mirrus.desktop",
        ],
    ),
    (
        "{prefix}/etc/xdg/autostart".format(prefix=sys.prefix),
        [
            "data/mirrus-autostart.desktop",
        ],
    ),
]

version = (
    next(l for l in open("pyproject.toml").read().splitlines() if "version = " in l)
    .split('version = "')[1]
    .split('"')[0]
)

setup(
    name="Mirrus",
    version=version,
    description="Screen-sharing for large displays",
    license="MIT",
    author="Daniel Brodsky",
    data_files=data_files,
    install_requires=[
        "setuptools",
    ],
    python_requires=">=3.6.*",
    scripts=["mirrus/mirrus"],
)
