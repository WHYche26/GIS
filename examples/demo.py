# -*- coding: utf-8 -*-
"""演示脚本：跑通所有支持的转换，并在 examples/output 下生成结果。

运行方式（在项目根目录）：
    python examples/demo.py
"""

from __future__ import annotations

import json
import os
import sys

# 允许直接以脚本方式运行（python examples/demo.py）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gis_converter import (  # noqa: E402
    convert_geojson_crs,
    csv_to_geojson,
    geojson_to_csv,
    geojson_to_kml,
    geojson_to_shapefile,
    geojson_to_wkt,
    kml_to_geojson,
    shapefile_to_geojson,
    wkt_to_geojson,
    wgs84_to_gcj02,
    wgs84_to_bd09,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
POINTS = os.path.join(HERE, "sample_points.geojson")
LINES = os.path.join(HERE, "sample_lines.geojson")
POLYGONS = os.path.join(HERE, "sample_polygons.geojson")


def _step(title: str) -> None:
    print(f"\n===== {title} =====")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)

    # 1. GeoJSON -> CSV -> GeoJSON（点要素往返）
    _step("GeoJSON -> CSV -> GeoJSON（点要素往返）")
    csv_path = os.path.join(OUT, "points.csv")
    geojson_to_csv(POINTS, csv_path)
    print(f"  CSV: {csv_path}")
    back = os.path.join(OUT, "points_from_csv.geojson")
    csv_to_geojson(csv_path, back)
    print(f"  回转: {back}")

    # 2. GeoJSON -> KML -> GeoJSON
    _step("GeoJSON -> KML -> GeoJSON")
    kml_path = os.path.join(OUT, "points.kml")
    geojson_to_kml(POINTS, kml_path)
    print(f"  KML: {kml_path}")
    back2 = os.path.join(OUT, "points_from_kml.geojson")
    kml_to_geojson(kml_path, back2)
    print(f"  回转: {back2}")

    # 3. GeoJSON -> WKT -> GeoJSON
    _step("GeoJSON -> WKT -> GeoJSON")
    wkt_path = os.path.join(OUT, "lines.wkt")
    geojson_to_wkt(LINES, wkt_path)
    print(f"  WKT: {wkt_path}")
    back3 = os.path.join(OUT, "lines_from_wkt.geojson")
    wkt_to_geojson(wkt_path, back3)
    print(f"  回转: {back3}")

    # 4. GeoJSON -> Shapefile -> GeoJSON（需要 pyshp）
    _step("GeoJSON -> Shapefile -> GeoJSON（需要 pyshp）")
    try:
        shp_path = os.path.join(OUT, "polygons")
        geojson_to_shapefile(POLYGONS, shp_path)
        print(f"  Shapefile: {shp_path}.shp / .dbf / .shx")
        back4 = os.path.join(OUT, "polygons_from_shp.geojson")
        fc = shapefile_to_geojson(shp_path + ".shp", back4)
        print(f"  回转要素数: {len(fc['features'])}")
    except RuntimeError as exc:
        print(f"  跳过（{exc}）")

    # 5. 坐标系转换示例
    _step("坐标系转换（WGS84 -> GCJ02 -> BD09）")
    gcj = os.path.join(OUT, "points_gcj02.geojson")
    bd = os.path.join(OUT, "points_bd09.geojson")
    convert_geojson_crs(POINTS, gcj, "wgs84_to_gcj02")
    convert_geojson_crs(POINTS, bd, "wgs84_to_bd09")
    with open(POINTS, encoding="utf-8") as f:
        src = json.load(f)
    with open(gcj, encoding="utf-8") as f:
        gcj_data = json.load(f)
    with open(bd, encoding="utf-8") as f:
        bd_data = json.load(f)

    for i, feat in enumerate(src["features"]):
        name = feat["properties"]["name"]
        w = feat["geometry"]["coordinates"]
        g = gcj_data["features"][i]["geometry"]["coordinates"]
        b = bd_data["features"][i]["geometry"]["coordinates"]
        print(f"  {name}: WGS84({w[0]:.6f},{w[1]:.6f}) -> GCJ02({g[0]:.6f},{g[1]:.6f}) -> BD09({b[0]:.6f},{b[1]:.6f})")

    # 6. 单点函数示例
    _step("单点坐标转换函数")
    lng, lat = 116.3912757, 39.9072175
    g = wgs84_to_gcj02(lng, lat)
    b = wgs84_to_bd09(lng, lat)
    print(f"  天安门 WGS84({lng}, {lat})")
    print(f"  GCJ02: ({g[0]:.6f}, {g[1]:.6f})")
    print(f"  BD09:  ({b[0]:.6f}, {b[1]:.6f})")

    print(f"\n全部完成，结果输出目录: {OUT}")


if __name__ == "__main__":
    main()
