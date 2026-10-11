# GIS 常见数据转换工具

一个开箱即用的 GIS 数据格式转换工具，覆盖测绘与地理信息工作流中最常用的格式互转与坐标系转换。

- **格式互转**：Shapefile ↔ GeoJSON ↔ CSV ↔ KML ↔ WKT
- **坐标系转换**：WGS84（GPS）↔ GCJ02（高德/腾讯，火星坐标）↔ BD09（百度）
- **两种使用方式**：命令行（CLI）与图形界面（GUI）
- **零配置**：核心功能仅依赖 Python 标准库；仅 Shapefile 读写需安装 `pyshp`

## 功能总览

| 转换 | 命令 | 说明 |
| --- | --- | --- |
| Shapefile → GeoJSON | `shp2geojson` | 支持点/线/面、属性表、内外环 |
| GeoJSON → Shapefile | `geojson2shp` | 输出 .shp/.dbf/.shx 三件套 |
| GeoJSON → CSV | `geojson2csv` | 点要素转表格（含 lon/lat 列） |
| CSV → GeoJSON | `csv2geojson` | 指定经纬度列生成点要素 |
| GeoJSON → KML | `geojson2kml` | 输出 KML 2.2，可用于 Google Earth |
| KML → GeoJSON | `kml2geojson` | 解析 Placemark / 线 / 面 / 多点 |
| GeoJSON → WKT | `geojson2wkt` | 每要素一行 |
| WKT → GeoJSON | `wkt2geojson` | 支持 POINT/LINESTRING/POLYGON/MULTI* |
| 坐标系转换 | `crs` | WGS84 / GCJ02 / BD09 任意互转 |

## 安装

要求 Python 3.9+。

```bash
# 1. 安装依赖（仅 Shapefile 功能需要 pyshp，其余零依赖）
pip install -r requirements.txt

# 2. 可选：安装为命令（setup.py）
pip install .
# 之后可直接使用 gisconv 命令
```

## 命令行用法

```bash
# 格式转换
python -m gis_converter shp2geojson  input.shp       output.geojson
python -m gis_converter geojson2shp  input.geojson   output.shp
python -m gis_converter geojson2csv  input.geojson   output.csv
python -m gis_converter csv2geojson  input.csv       output.geojson --lng lon --lat lat
python -m gis_converter geojson2kml  input.geojson   output.kml
python -m gis_converter kml2geojson  input.kml       output.geojson
python -m gis_converter geojson2wkt  input.geojson   output.wkt
python -m gis_converter wkt2geojson  input.wkt       output.geojson

# 坐标系转换（wgs84 / gcj02 / bd09 任意互转）
python -m gis_converter crs input.geojson output.geojson --from wgs84 --to gcj02
python -m gis_converter crs input.geojson output.geojson --from gcj02 --to bd09

# 查看帮助
python -m gis_converter --help
python -m gis_converter list
```

## 图形界面

```bash
python -m gis_converter.gui
```

界面选择「转换类型 → 输入文件 → 输出文件 → 开始转换」即可，适合不熟悉命令行的场景。

## Python API 调用

```python
from gis_converter import (
    shapefile_to_geojson, geojson_to_shapefile,
    geojson_to_csv, csv_to_geojson,
    geojson_to_kml, kml_to_geojson,
    geojson_to_wkt, wkt_to_geojson,
    convert_geojson_crs,
    wgs84_to_gcj02, gcj02_to_wgs84, wgs84_to_bd09, bd09_to_wgs84,
)

# 单点坐标转换
lng, lat = 116.3912757, 39.9072175   # 北京天安门（WGS84）
gcj = wgs84_to_gcj02(lng, lat)       # -> (116.3976..., 39.9087...)
bd  = wgs84_to_bd09(lng, lat)        # -> 百度坐标

# 批量文件转换
shapefile_to_geojson("input.shp", "output.geojson")
convert_geojson_crs("input.geojson", "output.geojson", "wgs84_to_gcj02")
```

## 坐标系说明

| 坐标系 | 全称 | 使用方 |
| --- | --- | --- |
| WGS84 | 世界大地坐标系 | GPS 设备、Google Earth、国际标准数据 |
| GCJ02 | 国测局加密坐标（火星坐标） | 高德地图、腾讯地图 |
| BD09 | 百度坐标系 | 百度地图 |

> 注意：国内各互联网地图叠加分析时，务必先统一坐标系，否则会出现几十米到数百米的偏移。GCJ02 加密仅作用于中国境内，境外坐标不偏移。

## 示例数据与演示

仓库内置 3 份示例数据（点/线/面）与一键演示脚本：

```bash
python examples/demo.py
```

演示会依次执行全部 6 类转换，结果输出到 `examples/output/`。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖：坐标系转换精度与往返还原、GeoJSON↔CSV/KML/WKT 往返、坐标系批量转换、Shapefile 往返（需 pyshp）。

## 目录结构

```
GIS/
├── gis_converter/
│   ├── __init__.py   # 包入口与公开 API
│   ├── coords.py     # WGS84 / GCJ02 / BD09 坐标系转换
│   ├── core.py       # 各格式互转核心逻辑
│   ├── cli.py        # 命令行入口（python -m gis_converter）
│   └── gui.py        # 图形界面入口（python -m gis_converter.gui）
├── examples/         # 示例数据与演示脚本
├── tests/            # 单元测试
├── requirements.txt
└── setup.py
```

## License

MIT
