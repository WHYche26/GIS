# -*- coding: utf-8 -*-
"""GIS 常见数据转换工具。

支持的格式：Shapefile / GeoJSON / CSV / KML / WKT
支持的坐标系：WGS84 / GCJ02（火星坐标）/ BD09（百度坐标）

命令行用法：python -m gis_converter --help
图形界面用法：python -m gis_converter.gui
"""

__version__ = "1.0.0"

from .coords import (  # noqa: F401
    bd09_to_gcj02,
    bd09_to_wgs84,
    gcj02_to_bd09,
    gcj02_to_wgs84,
    wgs84_to_bd09,
    wgs84_to_gcj02,
)
from .core import (  # noqa: F401
    convert_geojson_crs,
    csv_to_geojson,
    geojson_to_csv,
    geojson_to_kml,
    geojson_to_shapefile,
    geojson_to_wkt,
    kml_to_geojson,
    shapefile_to_geojson,
    wkt_to_geojson,
)

__all__ = [
    "shapefile_to_geojson",
    "geojson_to_shapefile",
    "geojson_to_csv",
    "csv_to_geojson",
    "geojson_to_kml",
    "kml_to_geojson",
    "geojson_to_wkt",
    "wkt_to_geojson",
    "convert_geojson_crs",
    "wgs84_to_gcj02",
    "gcj02_to_wgs84",
    "wgs84_to_bd09",
    "bd09_to_wgs84",
    "gcj02_to_bd09",
    "bd09_to_gcj02",
    "__version__",
]
