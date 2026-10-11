# -*- coding: utf-8 -*-
"""中国常用坐标系转换模块（WGS84 / GCJ02 / BD09）。

坐标系说明：
- WGS84：国际通用 GPS 坐标系（Google Earth、GPS 设备原始输出）
- GCJ02：国测局加密坐标，也称“火星坐标”（高德、腾讯地图使用）
- BD09：百度坐标系（百度地图使用）

公式为公开的测绘算法实现，适用于民用导航精度（米级）需求。
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_X_PI = 3.14159265358979324 * 3000.0 / 180.0
_PI = math.pi
_A = 6378245.0               # 长半轴（米）
_EE = 0.00669342162296594323  # 第一偏心率平方
_INF = float("inf")


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------
def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
    ret += 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * _PI) + 20.0 * math.sin(2.0 * x * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * _PI) + 40.0 * math.sin(y / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * _PI) + 320.0 * math.sin(y * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * _PI) + 20.0 * math.sin(2.0 * x * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * _PI) + 40.0 * math.sin(x / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * _PI) + 300.0 * math.sin(x / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def _out_of_china(lng: float, lat: float) -> bool:
    """粗略判断坐标是否在中国境外（GCJ 偏移仅对境内有意义）。"""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


# ---------------------------------------------------------------------------
# 公开转换函数（全部返回 (lng, lat) 元组）
# ---------------------------------------------------------------------------
def wgs84_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    """WGS84 -> GCJ02（火星坐标）。"""
    if _out_of_china(lng, lat):
        return lng, lat
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * _PI
    magic = math.sin(rad_lat)
    magic = 1.0 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1.0 - _EE)) / (magic * sqrt_magic) * _PI)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * _PI)
    return lng + d_lng, lat + d_lat


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """GCJ02 -> WGS84（一次逼近，精度约米级）。"""
    if _out_of_china(lng, lat):
        return lng, lat
    lng2, lat2 = wgs84_to_gcj02(lng, lat)
    return lng * 2.0 - lng2, lat * 2.0 - lat2


def gcj02_to_wgs84_exact(lng: float, lat: float, max_iter: int = 6) -> tuple[float, float]:
    """GCJ02 -> WGS84（迭代逼近，精度优于 1e-6 度，约 0.1 米）。"""
    if _out_of_china(lng, lat):
        return lng, lat
    g_lng, g_lat = lng, lat
    w_lng, w_lat = lng, lat
    for _ in range(max_iter):
        g_lng, g_lat = wgs84_to_gcj02(w_lng, w_lat)
        d_lng, d_lat = g_lng - lng, g_lat - lat
        if abs(d_lng) < 1e-9 and abs(d_lat) < 1e-9:
            break
        w_lng -= d_lng
        w_lat -= d_lat
    return w_lng, w_lat


def gcj02_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    """GCJ02 -> BD09（百度坐标）。"""
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * _X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * _X_PI)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def bd09_to_gcj02(lng: float, lat: float) -> tuple[float, float]:
    """BD09 -> GCJ02。"""
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def wgs84_to_bd09(lng: float, lat: float) -> tuple[float, float]:
    """WGS84 -> BD09（先转 GCJ02 再转 BD09）。"""
    if _out_of_china(lng, lat):
        return lng, lat
    lng, lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(lng, lat)


def bd09_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """BD09 -> WGS84。"""
    if _out_of_china(lng, lat):
        return lng, lat
    lng, lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84_exact(lng, lat)


# ---------------------------------------------------------------------------
# 转换注册表：供 CLI 与 GUI 统一使用
# ---------------------------------------------------------------------------
COORD_TRANSFORMS: dict[str, callable] = {
    "wgs84_to_gcj02": wgs84_to_gcj02,
    "gcj02_to_wgs84": gcj02_to_wgs84,
    "wgs84_to_bd09": wgs84_to_bd09,
    "bd09_to_wgs84": bd09_to_wgs84,
    "gcj02_to_bd09": gcj02_to_bd09,
    "bd09_to_gcj02": bd09_to_gcj02,
}
