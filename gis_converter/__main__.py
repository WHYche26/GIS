# -*- coding: utf-8 -*-
"""支持 `python -m gis_converter` 方式启动命令行工具。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
