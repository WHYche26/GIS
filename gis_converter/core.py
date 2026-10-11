# -*- coding: utf-8 -*-
"""GIS 常见数据格式转换核心逻辑。

支持的格式与转换：
- Shapefile（.shp/.dbf） <-> GeoJSON（.geojson）
- GeoJSON -> CSV（点要素转表格，含坐标列）
- CSV（含经纬度列） -> GeoJSON（点要素）
- GeoJSON <-> KML（.kml）
- GeoJSON <-> WKT（文本格式，支持 Point/LineString/Polygon/Multi*）
- GeoJSON 坐标系批量转换（WGS84 / GCJ02 / BD09）

依赖说明：核心模块仅依赖标准库；Shapefile 读写需要第三方库 pyshp。
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Callable, Iterable

try:
    import shapefile as _pyshp  # type: ignore
except ImportError:  # pragma: no cover
    _pyshp = None

from .coords import COORD_TRANSFORMS

# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
_GEOJSON_TYPES = {
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon", "GeometryCollection",
}


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _load_geojson(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        return data
    if isinstance(data, dict) and data.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [data]}
    if isinstance(data, dict) and data.get("type") in _GEOJSON_TYPES:
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": data, "properties": {}}]}
    raise ValueError("无法识别的 GeoJSON 文件，请确认文件是 FeatureCollection / Feature / Geometry 类型")


def _iter_coordinates(geometry: dict[str, Any]) -> Iterable[tuple[float, float]]:
    """深度遍历 geometry 中的所有 (lng, lat) 坐标对。"""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Point":
        yield coords[0], coords[1]
    elif gtype == "MultiPoint":
        for c in coords:
            yield c[0], c[1]
    elif gtype == "LineString":
        for c in coords:
            yield c[0], c[1]
    elif gtype == "MultiLineString":
        for line in coords:
            for c in line:
                yield c[0], c[1]
    elif gtype == "Polygon":
        for ring in coords:
            for c in ring:
                yield c[0], c[1]
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for c in ring:
                    yield c[0], c[1]
    elif gtype == "GeometryCollection":
        for g in geometry.get("geometries", []):
            yield from _iter_coordinates(g)
    else:
        raise ValueError(f"不支持的几何类型: {gtype}")


def _apply_to_coordinates(geometry: dict[str, Any], func: Callable[[float, float], tuple[float, float]]) -> dict[str, Any]:
    """对 geometry 的每个坐标执行 func(lng, lat)，返回新 geometry。"""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")

    def _t(c):
        lng, lat = func(float(c[0]), float(c[1]))
        if len(c) > 2:  # 保留高程等附加维度
            return [lng, lat] + list(c[2:])
        return [lng, lat]

    if gtype == "Point":
        new_coords = _t(coords)
    elif gtype == "MultiPoint":
        new_coords = [_t(c) for c in coords]
    elif gtype == "LineString":
        new_coords = [_t(c) for c in coords]
    elif gtype == "MultiLineString":
        new_coords = [[_t(c) for c in line] for line in coords]
    elif gtype == "Polygon":
        new_coords = [[_t(c) for c in ring] for ring in coords]
    elif gtype == "MultiPolygon":
        new_coords = [[[_t(c) for c in ring] for ring in poly] for poly in coords]
    elif gtype == "GeometryCollection":
        new_coords = None
        new_geoms = [_apply_to_coordinates(g, func) for g in geometry.get("geometries", [])]
        out = {"type": "GeometryCollection", "geometries": new_geoms}
        return out
    else:
        raise ValueError(f"不支持的几何类型: {gtype}")
    return {"type": gtype, "coordinates": new_coords}


def transform_geojson_coords(data: dict[str, Any], func: Callable[[float, float], tuple[float, float]]) -> dict[str, Any]:
    """对整个 FeatureCollection 做坐标转换，返回新的 dict。"""
    out = {"type": "FeatureCollection"}
    out["features"] = []
    for feat in data.get("features", []):
        new_feat = dict(feat)
        geom = feat.get("geometry")
        if geom:
            new_feat["geometry"] = _apply_to_coordinates(geom, func)
        out["features"].append(new_feat)
    return out


# ---------------------------------------------------------------------------
# Shapefile <-> GeoJSON
# ---------------------------------------------------------------------------
_SHP_TO_GEOJSON_TYPE = {
    0: "Null", 1: "Point", 3: "LineString", 5: "Polygon", 8: "MultiPoint",
    11: "Point", 13: "LineString", 15: "Polygon", 18: "MultiPoint",
    21: "Point", 23: "LineString", 25: "Polygon", 28: "MultiPoint",
}


def _shape_record_to_geojson(shape_type: int, shape: Any, properties: dict[str, Any]) -> dict[str, Any]:
    if shape is None:
        return {"type": "Feature", "geometry": None, "properties": properties}

    base = _SHP_TO_GEOJSON_TYPE.get(int(shape_type), "Null")

    if shape_type in (1, 11, 21):  # Point
        coords = [shape.points[0][0], shape.points[0][1]]
        geometry = {"type": "Point", "coordinates": coords}
    elif shape_type in (8, 18, 28):  # MultiPoint
        geometry = {"type": "MultiPoint", "coordinates": [[p[0], p[1]] for p in shape.points]}
    elif shape_type in (3, 13, 23):  # PolyLine
        parts = list(shape.parts) + [len(shape.points)]
        lines = [shape.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
        coords = [[[p[0], p[1]] for p in line] for line in lines]
        geometry = {
            "type": "MultiLineString" if len(coords) > 1 else "LineString",
            "coordinates": coords if len(coords) > 1 else coords[0],
        }
    elif shape_type in (5, 15, 25):  # Polygon
        parts = list(shape.parts) + [len(shape.points)]
        rings = [shape.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
        rings = [[[p[0], p[1]] for p in ring] for ring in rings]
        if len(rings) == 1:
            geometry = {"type": "Polygon", "coordinates": rings}
        else:
            # 简单启发式：按环面积正负判断内外环
            def _signed_area(ring):
                s = 0.0
                for i in range(len(ring) - 1):
                    s += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
                return s / 2.0

            outer = [r for r in rings if _signed_area(r) > 0] or [rings[0]]
            inner = [r for r in rings if _signed_area(r) <= 0]
            geometry = {"type": "Polygon", "coordinates": [outer[0]] + inner}
    else:
        geometry = None

    return {"type": "Feature", "geometry": geometry, "properties": properties}


def shapefile_to_geojson(shp_path: str, geojson_path: str) -> dict[str, Any]:
    """将 Shapefile 转换为 GeoJSON 并写入文件，同时返回 FeatureCollection。"""
    if _pyshp is None:
        raise RuntimeError("需要安装 pyshp：pip install pyshp")

    sf = _pyshp.Reader(shp_path)
    fields = sf.fields[1:]  # 去掉 DeletionFlag
    field_names = [f[0] for f in fields]

    features: list[dict[str, Any]] = []
    for rec in sf.iterShapeRecords():
        props = {name: rec.record[i] for i, name in enumerate(field_names)}
        features.append(_shape_record_to_geojson(sf.shapeType, rec.shape, props))

    fc = {"type": "FeatureCollection", "features": features}
    _ensure_parent(geojson_path)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    return fc


def geojson_to_shapefile(geojson_path: str, shp_path: str, properties_order: list[str] | None = None) -> str:
    """将 GeoJSON 转换为 Shapefile（.shp/.dbf/.shx 三件套），返回 shp 主文件路径。"""
    if _pyshp is None:
        raise RuntimeError("需要安装 pyshp：pip install pyshp")

    fc = _load_geojson(geojson_path)
    features = fc.get("features", [])

    # 收集属性字段（保持顺序稳定）
    if properties_order is None:
        properties_order = []
        for feat in features:
            for key in feat.get("properties", {}).keys():
                if key not in properties_order:
                    properties_order.append(key)

    w = _pyshp.Writer(shp_path, encoding="utf-8")
    for key in properties_order:
        w.field(key, "C", size=254)

    for feat in features:
        geom = feat.get("geometry")
        props = feat.get("properties") or {}
        row = [props.get(key, "") for key in properties_order]
        gtype = geom.get("type") if geom else None

        if gtype == "Point":
            x, y = geom["coordinates"][0], geom["coordinates"][1]
            w.point(x, y)
        elif gtype == "MultiPoint":
            w.multipoint([[c[0], c[1]] for c in geom["coordinates"]])
        elif gtype == "LineString":
            w.line([[c[0], c[1]] for c in geom["coordinates"]])
        elif gtype == "MultiLineString":
            w.line([[c[0], c[1]] for c in part] for part in geom["coordinates"])
        elif gtype == "Polygon":
            w.poly([[[c[0], c[1]] for c in ring] for ring in geom["coordinates"]])
        elif gtype == "MultiPolygon":
            w.poly([[[c[0], c[1]] for c in ring] for poly in geom["coordinates"] for ring in poly])
        elif gtype is None:
            w.null()
        else:
            raise ValueError(f"GeoJSON 几何类型 {gtype} 无法写入 Shapefile")
        w.record(*row)

    _ensure_parent(shp_path)
    w.close()  # pyshp 3.x：构造时已指定目标路径，close() 完成落盘
    return shp_path


# ---------------------------------------------------------------------------
# GeoJSON <-> CSV
# ---------------------------------------------------------------------------
def geojson_to_csv(geojson_path: str, csv_path: str,
                   lng_col: str = "lon", lat_col: str = "lat",
                   index_col: str | None = None) -> str:
    """GeoJSON -> CSV。仅转换 Point / MultiPoint 要素；其他几何类型会抛出提示。"""
    fc = _load_geojson(geojson_path)
    features = fc.get("features", [])

    rows: list[dict[str, Any]] = []
    for feat in features:
        geom = feat.get("geometry")
        props = dict(feat.get("properties") or {})
        if geom is None:
            continue
        gtype = geom.get("type")
        if gtype == "Point":
            pts = [geom["coordinates"]]
        elif gtype == "MultiPoint":
            pts = geom["coordinates"]
        else:
            raise ValueError(
                f"CSV 转换仅支持点要素，遇到 {gtype}。"
                f"如需处理线/面，请先转换为点（如质心）或改用其他工具。"
            )
        for p in pts:
            row = dict(props)
            row[lng_col] = p[0]
            row[lat_col] = p[1]
            if index_col is not None:
                row[index_col] = f"{props.get(index_col, '')}"
            rows.append(row)

    if not rows:
        raise ValueError("没有可写入 CSV 的点要素")

    fieldnames: list[str] = []
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)

    _ensure_parent(csv_path)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def csv_to_geojson(csv_path: str, geojson_path: str,
                   lng_col: str = "lon", lat_col: str = "lat",
                   name_col: str | None = None) -> str:
    """CSV（含经纬度列） -> GeoJSON 点要素。"""
    features: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV 文件为空或没有表头")
        if lng_col not in reader.fieldnames or lat_col not in reader.fieldnames:
            raise ValueError(f"CSV 中找不到经纬度列：{lng_col} / {lat_col}，现有列：{reader.fieldnames}")
        for row in reader:
            try:
                lng = float(row[lng_col])
                lat = float(row[lat_col])
            except (TypeError, ValueError):
                raise ValueError(f"经纬度不是有效数字：{row.get(lng_col)}, {row.get(lat_col)}")
            props = {k: v for k, v in row.items() if k not in (lng_col, lat_col)}
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": props,
            })

    fc = {"type": "FeatureCollection", "features": features}
    _ensure_parent(geojson_path)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    return geojson_path


# ---------------------------------------------------------------------------
# GeoJSON <-> KML
# ---------------------------------------------------------------------------
def _coord_str(coord: list) -> str:
    return f"{coord[0]},{coord[1]}"


def _kml_geometry_to_element(geom: dict[str, Any]) -> ET.Element:
    gtype = geom.get("type")
    coords = geom.get("coordinates")

    if gtype == "Point":
        place = ET.Element("Point")
        coord_el = ET.SubElement(place, "coordinates")
        coord_el.text = _coord_str(coords)
        return place
    if gtype == "MultiPoint":
        multi = ET.Element("MultiGeometry")
        for c in coords:
            place = ET.SubElement(multi, "Point")
            coord_el = ET.SubElement(place, "coordinates")
            coord_el.text = _coord_str(c)
        return multi
    if gtype == "LineString":
        ls = ET.Element("LineString")
        coord_el = ET.SubElement(ls, "coordinates")
        coord_el.text = " ".join(_coord_str(c) for c in coords)
        return ls
    if gtype == "MultiLineString":
        multi = ET.Element("MultiGeometry")
        for line in coords:
            ls = ET.SubElement(multi, "LineString")
            coord_el = ET.SubElement(ls, "coordinates")
            coord_el.text = " ".join(_coord_str(c) for c in line)
        return multi
    if gtype == "Polygon":
        poly = ET.Element("Polygon")
        outer = ET.SubElement(poly, "outerBoundaryIs")
        ring = ET.SubElement(outer, "LinearRing")
        coord_el = ET.SubElement(ring, "coordinates")
        coord_el.text = " ".join(_coord_str(c) for c in coords[0])
        for inner_ring in coords[1:]:
            inner = ET.SubElement(poly, "innerBoundaryIs")
            ring2 = ET.SubElement(inner, "LinearRing")
            coord_el2 = ET.SubElement(ring2, "coordinates")
            coord_el2.text = " ".join(_coord_str(c) for c in inner_ring)
        return poly
    if gtype == "MultiPolygon":
        multi = ET.Element("MultiGeometry")
        for poly_coords in coords:
            poly = ET.SubElement(multi, "Polygon")
            outer = ET.SubElement(poly, "outerBoundaryIs")
            ring = ET.SubElement(outer, "LinearRing")
            coord_el = ET.SubElement(ring, "coordinates")
            coord_el.text = " ".join(_coord_str(c) for c in poly_coords[0])
            for inner_ring in poly_coords[1:]:
                inner = ET.SubElement(poly, "innerBoundaryIs")
                ring2 = ET.SubElement(inner, "LinearRing")
                coord_el2 = ET.SubElement(ring2, "coordinates")
                coord_el2.text = " ".join(_coord_str(c) for c in inner_ring)
        return multi
    raise ValueError(f"KML 输出不支持几何类型: {gtype}")


def geojson_to_kml(geojson_path: str, kml_path: str, name_col: str | None = None) -> str:
    """GeoJSON -> KML（KML 2.2，坐标自动转 WGS84 语义，直接按文件坐标写入）。"""
    fc = _load_geojson(geojson_path)

    kml = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, "Document")
    ET.SubElement(doc, "name").text = os.path.splitext(os.path.basename(kml_path))[0]

    for feat in fc.get("features", []):
        geom = feat.get("geometry")
        if geom is None:
            continue
        placemark = ET.SubElement(doc, "Placemark")
        props = feat.get("properties") or {}
        name = ""
        if name_col and name_col in props:
            name = str(props[name_col])
        else:
            for key in ("name", "Name", "title"):
                if key in props:
                    name = str(props[key])
                    break
        if name:
            ET.SubElement(placemark, "name").text = name
        if props:
            desc_el = ET.SubElement(placemark, "description")
            desc_el.text = "<![CDATA[" + "<br/>".join(
                f"<b>{k}</b>: {v}" for k, v in props.items()
            ) + "]]>"
        placemark.append(_kml_geometry_to_element(geom))

    _ensure_parent(kml_path)
    tree = ET.ElementTree(kml)
    ET.indent(tree, space="  ")
    tree.write(kml_path, encoding="utf-8", xml_declaration=True)
    return kml_path


def _parse_coord_tuple(text: str) -> tuple[float, float]:
    parts = text.strip().split(",")
    return float(parts[0]), float(parts[1])


def _kml_element_to_geometry(el: ET.Element) -> dict[str, Any]:
    tag = el.tag.split("}")[-1]
    if tag == "Point":
        coords = el.findtext("./{*}coordinates", "").strip()
        return {"type": "Point", "coordinates": list(_parse_coord_tuple(coords))}
    if tag == "LineString":
        coords = el.findtext("./{*}coordinates", "").strip()
        pts = [_parse_coord_tuple(c) for c in coords.split()]
        return {"type": "LineString", "coordinates": [list(p) for p in pts]}
    if tag == "LinearRing":
        coords = el.findtext("./{*}coordinates", "").strip()
        pts = [_parse_coord_tuple(c) for c in coords.split()]
        return {"type": "LinearRing", "coordinates": [list(p) for p in pts]}
    if tag == "Polygon":
        rings = []
        for bound in el.findall("./{*}outerBoundaryIs"):
            ring_el = bound.find("./{*}LinearRing")
            if ring_el is not None:
                rings.append(_kml_element_to_geometry(ring_el)["coordinates"])
        for bound in el.findall("./{*}innerBoundaryIs"):
            ring_el = bound.find("./{*}LinearRing")
            if ring_el is not None:
                rings.append(_kml_element_to_geometry(ring_el)["coordinates"])
        return {"type": "Polygon", "coordinates": rings}
    if tag == "MultiGeometry":
        geoms = [_kml_element_to_geometry(child) for child in el]
        # 归并同类
        kinds = {g["type"] for g in geoms}
        if len(kinds) == 1 and kinds == {"Point"}:
            return {"type": "MultiPoint", "coordinates": [g["coordinates"] for g in geoms]}
        if len(kinds) == 1 and kinds == {"LineString"}:
            return {"type": "MultiLineString", "coordinates": [g["coordinates"] for g in geoms]}
        if len(kinds) == 1 and kinds == {"Polygon"}:
            return {"type": "MultiPolygon", "coordinates": [g["coordinates"] for g in geoms]}
        return {"type": "GeometryCollection", "geometries": geoms}
    raise ValueError(f"KML 解析不支持的元素: {tag}")


def kml_to_geojson(kml_path: str, geojson_path: str) -> str:
    """KML -> GeoJSON。"""
    tree = ET.parse(kml_path)
    root = tree.getroot()

    features: list[dict[str, Any]] = []

    def _walk(parent: ET.Element) -> None:
        for el in parent:
            tag = el.tag.split("}")[-1]
            if tag == "Placemark":
                props: dict[str, Any] = {}
                name = el.findtext("./{*}name")
                desc = el.findtext("./{*}description")
                if name:
                    props["name"] = name
                if desc:
                    props["description"] = desc
                geometry_el = None
                for child in el:
                    if child.tag.split("}")[-1] in (
                        "Point", "LineString", "Polygon", "MultiGeometry"
                    ):
                        geometry_el = child
                        break
                if geometry_el is not None:
                    geometry = _kml_element_to_geometry(geometry_el)
                    features.append({
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": props,
                    })
            elif tag in ("Document", "Folder"):
                _walk(el)

    _walk(root)
    fc = {"type": "FeatureCollection", "features": features}
    _ensure_parent(geojson_path)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    return geojson_path


# ---------------------------------------------------------------------------
# GeoJSON <-> WKT
# ---------------------------------------------------------------------------
_WKT_RE = re.compile(
    r"^\s*(?P<type>POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON)"
    r"\s*(?P<body>.*?)\s*$",
    re.IGNORECASE,
)


def geometry_to_wkt(geom: dict[str, Any]) -> str:
    """GeoJSON geometry -> WKT 字符串。"""
    gtype = geom.get("type")
    coords = geom.get("coordinates")

    def _pt(c) -> str:
        return f"{c[0]} {c[1]}"

    if gtype == "Point":
        return f"POINT ({_pt(coords)})"
    if gtype == "LineString":
        return "LINESTRING (" + ", ".join(_pt(c) for c in coords) + ")"
    if gtype == "Polygon":
        rings = ["(" + ", ".join(_pt(c) for c in ring) + ")" for ring in coords]
        return "POLYGON (" + ", ".join(rings) + ")"
    if gtype == "MultiPoint":
        return "MULTIPOINT (" + ", ".join(_pt(c) for c in coords) + ")"
    if gtype == "MultiLineString":
        parts = ["(" + ", ".join(_pt(c) for c in line) + ")" for line in coords]
        return "MULTILINESTRING (" + ", ".join(parts) + ")"
    if gtype == "MultiPolygon":
        polys = []
        for poly in coords:
            rings = ["(" + ", ".join(_pt(c) for c in ring) + ")" for ring in poly]
            polys.append("(" + ", ".join(rings) + ")")
        return "MULTIPOLYGON (" + ", ".join(polys) + ")"
    raise ValueError(f"WKT 输出不支持几何类型: {gtype}")


def wkt_to_geometry(wkt: str) -> dict[str, Any]:
    """WKT 字符串 -> GeoJSON geometry。"""
    m = _WKT_RE.match(wkt)
    if not m:
        raise ValueError(f"无法解析 WKT: {wkt!r}")
    gtype = m.group("type").upper()
    body = m.group("body").strip()

    def _pairs(text: str) -> list[list[float]]:
        nums = re.findall(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", text)
        pts = []
        for i in range(0, len(nums) - 1, 2):
            pts.append([float(nums[i]), float(nums[i + 1])])
        return pts

    if gtype == "POINT":
        return {"type": "Point", "coordinates": _pairs(body)[0]}
    if gtype == "LINESTRING":
        return {"type": "LineString", "coordinates": _pairs(body)}
    if gtype == "MULTIPOINT":
        return {"type": "MultiPoint", "coordinates": _pairs(body)}
    if gtype == "POLYGON":
        rings = [ring.strip() for ring in _split_ring(body)]
        return {"type": "Polygon", "coordinates": [_pairs(r) for r in rings]}
    if gtype == "MULTILINESTRING":
        lines = [ln.strip() for ln in _split_ring(body)]
        return {"type": "MultiLineString", "coordinates": [_pairs(l) for l in lines]}
    if gtype == "MULTIPOLYGON":
        polys = [_split_ring(p.strip()) for p in _split_poly(body)]
        return {"type": "MultiPolygon", "coordinates": [[_pairs(r) for r in poly] for poly in polys]}
    raise ValueError(f"不支持的 WKT 类型: {gtype}")


def _split_ring(text: str) -> list[str]:
    """把 '((...),(...))' 的外层括号内容按 '),(' 拆成多个子串。"""
    return re.findall(r"\((.*?)\)", text)


def _split_poly(text: str) -> list[str]:
    """把 MULTIPOLYGON 体按 ')),((' 拆分。"""
    return re.findall(r"\(\(.*?\)\)", text)


def geojson_to_wkt(geojson_path: str, wkt_path: str, sep: str = "\n") -> str:
    """GeoJSON -> WKT 文本文件（每要素一行）。"""
    fc = _load_geojson(geojson_path)
    lines = []
    for feat in fc.get("features", []):
        geom = feat.get("geometry")
        if geom is None:
            continue
        lines.append(geometry_to_wkt(geom))
    _ensure_parent(wkt_path)
    with open(wkt_path, "w", encoding="utf-8") as f:
        f.write(sep.join(lines))
    return wkt_path


def wkt_to_geojson(wkt_path: str, geojson_path: str) -> str:
    """WKT 文本文件 -> GeoJSON。"""
    features = []
    with open(wkt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            features.append({
                "type": "Feature",
                "geometry": wkt_to_geometry(line),
                "properties": {},
            })
    fc = {"type": "FeatureCollection", "features": features}
    _ensure_parent(geojson_path)
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    return geojson_path


# ---------------------------------------------------------------------------
# 坐标系批量转换
# ---------------------------------------------------------------------------
def convert_geojson_crs(geojson_path: str, out_path: str, transform_name: str) -> str:
    """对 GeoJSON 文件批量执行坐标系转换。

    transform_name 取值见 coords.COORD_TRANSFORMS 的键。
    """
    if transform_name not in COORD_TRANSFORMS:
        raise ValueError(f"未知的坐标系转换: {transform_name}，可选: {sorted(COORD_TRANSFORMS)}")
    func = COORD_TRANSFORMS[transform_name]
    fc = _load_geojson(geojson_path)
    out = transform_geojson_coords(fc, func)
    _ensure_parent(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out_path


# ---------------------------------------------------------------------------
# 便捷入口
# ---------------------------------------------------------------------------
FORMAT_HELP = {
    "shapefile": "Shapefile（.shp/.dbf/.shx），需要 pyshp",
    "geojson": "GeoJSON（.geojson / .json）",
    "csv": "CSV 表格（点要素，含经纬度列）",
    "kml": "KML 2.2（Google Earth 等）",
    "wkt": "WKT 文本（每行一个几何）",
}
