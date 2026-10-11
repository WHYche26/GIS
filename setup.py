# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

setup(
    name="gis-converter",
    version="1.0.0",
    description="GIS 常见数据格式转换工具：Shapefile / GeoJSON / CSV / KML / WKT 互转，支持 WGS84 / GCJ02 / BD09 坐标系转换",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="WHYche26",
    url="https://github.com/WHYche26/GIS",
    packages=find_packages(),
    install_requires=["pyshp>=2.3.0"],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "gisconv=gis_converter.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: GIS",
    ],
)
