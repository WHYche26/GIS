# -*- coding: utf-8 -*-
"""GIS 数据转换工具 —— 命令行入口。

用法示例：
    # Shapefile -> GeoJSON
    python -m gis_converter shp2geojson input.shp output.geojson

    # GeoJSON -> Shapefile
    python -m gis_converter geojson2shp input.geojson output.shp

    # GeoJSON -> CSV（点要素）
    python -m gis_converter geojson2csv input.geojson output.csv

    # CSV -> GeoJSON（点要素，默认使用 lon/lat 列）
    python -m gis_converter csv2geojson input.csv output.geojson --lng lon --lat lat

    # GeoJSON <-> KML
    python -m gis_converter geojson2kml input.geojson output.kml
    python -m gis_converter kml2geojson input.kml output.geojson

    # GeoJSON <-> WKT
    python -m gis_converter geojson2wkt input.geojson output.wkt
    python -m gis_converter wkt2geojson input.wkt output.geojson

    # 坐标系转换（WGS84 / GCJ02 / BD09）
    python -m gis_converter crs input.geojson output.geojson --from wgs84 --to gcj02
"""

from __future__ import annotations

import argparse
import sys

from .core import (
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
from .coords import COORD_TRANSFORMS

_CRS_ALIAS = {
    "wgs84": "wgs84", "wgs": "wgs84", "gps": "wgs84",
    "gcj02": "gcj02", "gcj": "gcj02", "火星": "gcj02",
    "bd09": "bd09", "bd": "bd09", "百度": "bd09",
}


def _normalize_crs(name: str) -> str:
    key = name.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in _CRS_ALIAS:
        raise ValueError(f"不支持的坐标系: {name}，可选: {sorted(set(_CRS_ALIAS.values()))}")
    return _CRS_ALIAS[key]


def _pair(name_from: str, name_to: str) -> str:
    return f"{_normalize_crs(name_from)}_to_{_normalize_crs(name_to)}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gis_converter",
        description="GIS 常见数据格式转换工具：Shapefile / GeoJSON / CSV / KML / WKT 互转，支持 WGS84 / GCJ02 / BD09 坐标系转换。",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="命令")

    def _add(src, dst, help_text, with_lnglat=False, with_crs=False):
        p = sub.add_parser(src, help=help_text)
        p.add_argument("input", help="输入文件路径")
        p.add_argument("output", help="输出文件路径")
        if with_lnglat:
            p.add_argument("--lng", default="lon", help="经度列名（默认 lon）")
            p.add_argument("--lat", default="lat", help="纬度列名（默认 lat）")
        if with_crs:
            p.add_argument("--from", dest="from_crs", required=True, help="源坐标系: wgs84 / gcj02 / bd09")
            p.add_argument("--to", dest="to_crs", required=True, help="目标坐标系: wgs84 / gcj02 / bd09")
        return p

    _add("shp2geojson", "output", "Shapefile -> GeoJSON")
    _add("geojson2shp", "output", "GeoJSON -> Shapefile")
    _add("geojson2csv", "output", "GeoJSON -> CSV（点要素）", with_lnglat=True)
    _add("csv2geojson", "output", "CSV（含经纬度列） -> GeoJSON 点要素", with_lnglat=True)
    _add("geojson2kml", "output", "GeoJSON -> KML")
    _add("kml2geojson", "output", "KML -> GeoJSON")
    _add("geojson2wkt", "output", "GeoJSON -> WKT 文本")
    _add("wkt2geojson", "output", "WKT 文本 -> GeoJSON")
    _add("crs", "output", "GeoJSON 坐标系转换（WGS84 / GCJ02 / BD09）", with_crs=True)

    sub.add_parser("list", help="列出支持的坐标系转换")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "shp2geojson":
            out = shapefile_to_geojson(args.input, args.output)
            print(f"[OK] {args.input} -> {args.output} (GeoJSON)")
        elif args.command == "geojson2shp":
            out = geojson_to_shapefile(args.input, args.output)
            print(f"[OK] {args.input} -> {out} (.shp/.dbf/.shx)")
        elif args.command == "geojson2csv":
            out = geojson_to_csv(args.input, args.output, lng_col=args.lng, lat_col=args.lat)
            print(f"[OK] {args.input} -> {out} (CSV, 坐标列 {args.lng}/{args.lat})")
        elif args.command == "csv2geojson":
            out = csv_to_geojson(args.input, args.output, lng_col=args.lng, lat_col=args.lat)
            print(f"[OK] {args.input} -> {out} (GeoJSON 点要素)")
        elif args.command == "geojson2kml":
            out = geojson_to_kml(args.input, args.output)
            print(f"[OK] {args.input} -> {out} (KML)")
        elif args.command == "kml2geojson":
            out = kml_to_geojson(args.input, args.output)
            print(f"[OK] {args.input} -> {out} (GeoJSON)")
        elif args.command == "geojson2wkt":
            out = geojson_to_wkt(args.input, args.output)
            print(f"[OK] {args.input} -> {out} (WKT)")
        elif args.command == "wkt2geojson":
            out = wkt_to_geojson(args.input, args.output)
            print(f"[OK] {args.input} -> {out} (GeoJSON)")
        elif args.command == "crs":
            tname = _pair(args.from_crs, args.to_crs)
            out = convert_geojson_crs(args.input, args.output, tname)
            print(f"[OK] {args.input} -> {out} (坐标系: {args.from_crs} -> {args.to_crs})")
        elif args.command == "list":
            for name in sorted(COORD_TRANSFORMS):
                print(name)
        else:  # pragma: no cover
            build_parser().print_help()
            return 2
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI 层统一捕获并友好提示
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
