# -*- coding: utf-8 -*-
"""GIS 数据转换工具 —— 图形界面入口（基于 tkinter，Windows/Linux/macOS 均可运行）。

启动方式：
    python -m gis_converter.gui

功能：选择输入文件 -> 选择转换类型 -> 点击「开始转换」。
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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

# (显示名, 输入格式提示, 输出格式提示, 处理函数)
_OPERATIONS: list[tuple[str, str, str, callable]] = [
    ("Shapefile → GeoJSON", ".shp", ".geojson", lambda a, b: shapefile_to_geojson(a, b)),
    ("GeoJSON → Shapefile", ".geojson", ".shp", lambda a, b: geojson_to_shapefile(a, b)),
    ("GeoJSON → CSV", ".geojson", ".csv", lambda a, b: geojson_to_csv(a, b)),
    ("CSV → GeoJSON", ".csv", ".geojson", lambda a, b: csv_to_geojson(a, b)),
    ("GeoJSON → KML", ".geojson", ".kml", lambda a, b: geojson_to_kml(a, b)),
    ("KML → GeoJSON", ".kml", ".geojson", lambda a, b: kml_to_geojson(a, b)),
    ("GeoJSON → WKT", ".geojson", ".wkt", lambda a, b: geojson_to_wkt(a, b)),
    ("WKT → GeoJSON", ".wkt", ".geojson", lambda a, b: wkt_to_geojson(a, b)),
    ("坐标转换 (WGS84→GCJ02)", ".geojson", ".geojson", lambda a, b: convert_geojson_crs(a, b, "wgs84_to_gcj02")),
    ("坐标转换 (GCJ02→WGS84)", ".geojson", ".geojson", lambda a, b: convert_geojson_crs(a, b, "gcj02_to_wgs84")),
    ("坐标转换 (WGS84→BD09)", ".geojson", ".geojson", lambda a, b: convert_geojson_crs(a, b, "wgs84_to_bd09")),
    ("坐标转换 (BD09→WGS84)", ".geojson", ".geojson", lambda a, b: convert_geojson_crs(a, b, "bd09_to_wgs84")),
    ("坐标转换 (GCJ02→BD09)", ".geojson", ".geojson", lambda a, b: convert_geojson_crs(a, b, "gcj02_to_bd09")),
    ("坐标转换 (BD09→GCJ02)", ".geojson", ".geojson", lambda a, b: convert_geojson_crs(a, b, "bd09_to_gcj02")),
]


class ConverterApp:
    """简单的文件转换图形界面。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("GIS 数据转换工具")
        root.geometry("640x420")
        root.resizable(False, False)

        # 操作选择
        ttk.Label(root, text="转换类型:").pack(anchor="w", padx=12, pady=(12, 4))
        self.op_var = tk.StringVar(value=_OPERATIONS[0][0])
        op_box = ttk.Combobox(root, textvariable=self.op_var, state="readonly",
                              values=[op[0] for op in _OPERATIONS], width=40)
        op_box.pack(anchor="w", padx=12)
        op_box.bind("<<ComboboxSelected>>", lambda _e: self._update_hints())

        # 输入文件
        ttk.Label(root, text="输入文件:").pack(anchor="w", padx=12, pady=(12, 4))
        row = ttk.Frame(root)
        row.pack(anchor="w", padx=12, fill="x")
        self.in_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.in_var, width=46).pack(side="left")
        ttk.Button(row, text="浏览…", command=self._choose_input).pack(side="left", padx=(6, 0))

        # 输出文件
        ttk.Label(root, text="输出文件:").pack(anchor="w", padx=12, pady=(12, 4))
        row2 = ttk.Frame(root)
        row2.pack(anchor="w", padx=12, fill="x")
        self.out_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.out_var, width=46).pack(side="left")
        ttk.Button(row2, text="浏览…", command=self._choose_output).pack(side="left", padx=(6, 0))

        # 转换按钮
        ttk.Button(root, text="开始转换", command=self._convert).pack(pady=18)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(root, textvariable=self.status_var, foreground="#555").pack()

    def _current_op(self) -> tuple[str, str, str, callable]:
        idx = [op[0] for op in _OPERATIONS].index(self.op_var.get())
        return _OPERATIONS[idx]

    def _update_hints(self) -> None:
        _, in_hint, out_hint, _ = self._current_op()
        self.in_var.set("")
        self.out_var.set("")
        self.status_var.set(f"输入格式: {in_hint}    输出格式: {out_hint}")

    def _choose_input(self) -> None:
        _, in_hint, _, _ = self._current_op()
        path = filedialog.askopenfilename(title="选择输入文件", filetypes=[(f"{in_hint} 文件", f"*{in_hint}"), ("所有文件", "*.*")])
        if path:
            self.in_var.set(path)
            self._suggest_output()

    def _choose_output(self) -> None:
        _, _, out_hint, _ = self._current_op()
        path = filedialog.asksaveasfilename(title="保存为", defaultextension=out_hint,
                                            filetypes=[(f"{out_hint} 文件", f"*{out_hint}")])
        if path:
            self.out_var.set(path)

    def _suggest_output(self) -> None:
        inp = self.in_var.get()
        if not inp:
            return
        _, _, out_hint, _ = self._current_op()
        base = os.path.splitext(inp)[0]
        self.out_var.set(base + out_hint)

    def _convert(self) -> None:
        inp = self.in_var.get().strip()
        out = self.out_var.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror("错误", "请选择有效的输入文件")
            return
        if not out:
            messagebox.showerror("错误", "请指定输出文件路径")
            return
        _, _, _, func = self._current_op()
        try:
            self.status_var.set("正在转换…")
            self.root.update_idletasks()
            func(inp, out)
            self.status_var.set("转换完成 ✓")
            messagebox.showinfo("完成", f"转换成功！\n{out}")
        except Exception as exc:  # noqa: BLE001 - GUI 层统一捕获
            self.status_var.set("转换失败")
            messagebox.showerror("错误", f"转换失败：\n{exc}")


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
