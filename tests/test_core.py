# -*- coding: utf-8 -*-
"""核心功能单元测试（使用标准库 unittest）。

运行方式（在项目根目录）：
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gis_converter.coords import (  # noqa: E402
    bd09_to_gcj02,
    bd09_to_wgs84,
    gcj02_to_bd09,
    gcj02_to_wgs84,
    gcj02_to_wgs84_exact,
    wgs84_to_bd09,
    wgs84_to_gcj02,
)
from gis_converter.core import (  # noqa: E402
    convert_geojson_crs,
    csv_to_geojson,
    geojson_to_csv,
    geojson_to_kml,
    geojson_to_shapefile,
    geojson_to_wkt,
    kml_to_geojson,
    shapefile_to_geojson,
    wkt_to_geometry,
)

# 北京天安门（公开已知坐标）
TIANANMEN_WGS84 = (116.3912757, 39.9072175)


class CoordTransformTests(unittest.TestCase):
    def test_out_of_china_no_change(self):
        """境外坐标不应偏移。"""
        lng, lat = -74.0060, 40.7128  # 纽约
        self.assertEqual(wgs84_to_gcj02(lng, lat), (lng, lat))
        self.assertEqual(wgs84_to_bd09(lng, lat), (lng, lat))

    def test_wgs84_to_gcj02_offset(self):
        """境内坐标应发生数百米量级偏移（约 0.001~0.01 度）。"""
        g_lng, g_lat = wgs84_to_gcj02(*TIANANMEN_WGS84)
        d_lng = abs(g_lng - TIANANMEN_WGS84[0])
        d_lat = abs(g_lat - TIANANMEN_WGS84[1])
        self.assertGreater(d_lng, 0.001)
        self.assertGreater(d_lat, 0.001)
        self.assertLess(d_lng, 0.01)
        self.assertLess(d_lat, 0.01)

    def test_gcj02_wgs84_roundtrip_exact(self):
        """GCJ02 -> WGS84 迭代后应基本还原。"""
        g = wgs84_to_gcj02(*TIANANMEN_WGS84)
        back = gcj02_to_wgs84_exact(*g)
        self.assertAlmostEqual(back[0], TIANANMEN_WGS84[0], places=6)
        self.assertAlmostEqual(back[1], TIANANMEN_WGS84[1], places=6)

    def test_gcj02_bd09_roundtrip(self):
        """GCJ02 -> BD09 -> GCJ02 应还原（1e-6 精度）。"""
        g = (116.397637, 39.908740)
        b = gcj02_to_bd09(*g)
        back = bd09_to_gcj02(*b)
        self.assertAlmostEqual(back[0], g[0], places=5)
        self.assertAlmostEqual(back[1], g[1], places=5)

    def test_wgs84_bd09_roundtrip(self):
        """WGS84 -> BD09 -> WGS84 应还原。"""
        b = wgs84_to_bd09(*TIANANMEN_WGS84)
        back = bd09_to_wgs84(*b)
        self.assertAlmostEqual(back[0], TIANANMEN_WGS84[0], places=5)
        self.assertAlmostEqual(back[1], TIANANMEN_WGS84[1], places=5)


class GeoJsonRoundTripTests(unittest.TestCase):
    POINT_FC = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "A", "rank": 1},
                "geometry": {"type": "Point", "coordinates": [116.39, 39.90]},
            },
            {
                "type": "Feature",
                "properties": {"name": "B", "rank": 2},
                "geometry": {"type": "Point", "coordinates": [121.49, 31.23]},
            },
        ],
    }
    LINE_FC = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "L"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[103.7, 36.0], [103.8, 36.1], [103.9, 36.0]],
                },
            }
        ],
    }
    POLY_FC = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "P"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
                        [[0.2, 0.2], [0.2, 0.4], [0.4, 0.4], [0.4, 0.2], [0.2, 0.2]],
                    ],
                },
            }
        ],
    }

    def _tmp(self, suffix: str) -> str:
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        os.remove(path)
        return path

    def _write_fc(self, fc: dict) -> str:
        path = self._tmp(".geojson")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False)
        return path

    def test_geojson_csv_roundtrip(self):
        src = self._write_fc(self.POINT_FC)
        csv_path = self._tmp(".csv")
        geojson_to_csv(src, csv_path)
        back = self._tmp(".geojson")
        csv_to_geojson(csv_path, back)
        with open(back, encoding="utf-8") as f:
            fc = json.load(f)
        self.assertEqual(len(fc["features"]), 2)
        self.assertEqual(fc["features"][0]["properties"]["name"], "A")
        self.assertEqual(fc["features"][0]["geometry"]["coordinates"][0], 116.39)

    def test_geojson_kml_roundtrip(self):
        src = self._write_fc(self.LINE_FC)
        kml_path = self._tmp(".kml")
        geojson_to_kml(src, kml_path)
        back = self._tmp(".geojson")
        kml_to_geojson(kml_path, back)
        with open(back, encoding="utf-8") as f:
            fc = json.load(f)
        self.assertEqual(len(fc["features"]), 1)
        geom = fc["features"][0]["geometry"]
        self.assertEqual(geom["type"], "LineString")
        self.assertEqual(len(geom["coordinates"]), 3)

    def test_wkt_roundtrip(self):
        for geom, wkt in [
            ({"type": "Point", "coordinates": [1.5, 2.5]}, "POINT (1.5 2.5)"),
            (
                {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "POLYGON ((0 0, 1 0, 1 1, 0 0))",
            ),
        ]:
            parsed = wkt_to_geometry(wkt)
            self.assertEqual(parsed, geom)

    def test_geojson_wkt_roundtrip(self):
        src = self._write_fc(self.LINE_FC)
        wkt_path = self._tmp(".wkt")
        geojson_to_wkt(src, wkt_path)
        back = self._tmp(".geojson")
        from gis_converter.core import wkt_to_geojson

        wkt_to_geojson(wkt_path, back)
        with open(back, encoding="utf-8") as f:
            fc = json.load(f)
        self.assertEqual(fc["features"][0]["geometry"]["type"], "LineString")

    def test_crs_transform_geojson(self):
        src = self._write_fc(self.POINT_FC)
        out = self._tmp(".geojson")
        convert_geojson_crs(src, out, "wgs84_to_gcj02")
        with open(out, encoding="utf-8") as f:
            fc = json.load(f)
        c = fc["features"][0]["geometry"]["coordinates"]
        self.assertNotAlmostEqual(c[0], 116.39, places=2)

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("shapefile") is not None,
        "需要安装 pyshp 才能测试 Shapefile 转换",
    )
    def test_shapefile_roundtrip(self):
        src = self._write_fc(self.POLY_FC)
        shp_base = self._tmp(".shp")[:-4]  # 去掉 .shp 后缀
        geojson_to_shapefile(src, shp_base)
        back = self._tmp(".geojson")
        fc = shapefile_to_geojson(shp_base + ".shp", back)
        self.assertEqual(len(fc["features"]), 1)
        self.assertEqual(fc["features"][0]["geometry"]["type"], "Polygon")


if __name__ == "__main__":
    unittest.main()
