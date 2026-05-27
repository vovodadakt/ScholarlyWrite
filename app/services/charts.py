"""Data analysis and chart generation for uploaded CSV/Excel files."""
import csv
import io
import base64
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm

# Configure Chinese font support — prefer full CJK fonts over extension subsets
_CJK_FONT_PATH = ""
_FONT_NAME = 'sans-serif'

_PREFERRED = ['simhei', 'microsoft yahei', 'noto sans cjk sc', 'noto serif sc',
              'source han sans sc', 'wqy microhei', 'wenquanyi micro hei',
              'pingfang sc', 'hiragino sans gb', 'stheiti']
_FALLBACK = ['simsun', 'kaiti', 'fangsong', 'noto sans cjk', 'source han']

for _pref in _PREFERRED:
    for _fname in fm.findSystemFonts():
        try:
            _fp = fm.FontProperties(fname=_fname)
            if _pref == _fp.get_name().lower():
                _CJK_FONT_PATH = _fname
                _FONT_NAME = _fp.get_name()
                break
        except Exception:
            continue
    if _CJK_FONT_PATH:
        break

if not _CJK_FONT_PATH:
    for _fname in fm.findSystemFonts():
        try:
            _fp = fm.FontProperties(fname=_fname)
            _fn = _fp.get_name().lower()
            if any(k in _fn and 'ext' not in _fn for k in _FALLBACK):
                _CJK_FONT_PATH = _fname
                _FONT_NAME = _fp.get_name()
                break
        except Exception:
            continue

# Aggressively register CJK font so both rcParams AND FontProperties work
if _CJK_FONT_PATH:
    fm.fontManager.addfont(_CJK_FONT_PATH)
    # Rebuild internal font lookup so the font is found by name
    fm._load_fontmanager(try_read_cache=False)
    plt.rcParams['font.sans-serif'] = [_FONT_NAME, 'DejaVu Sans', 'Arial']
    plt.rcParams['font.family'] = 'sans-serif'

plt.rcParams['axes.unicode_minus'] = False


def _cjk_fp() -> fm.FontProperties:
    """Return a FontProperties object for CJK text."""
    if _CJK_FONT_PATH:
        return fm.FontProperties(fname=_CJK_FONT_PATH)
    return fm.FontProperties()
import numpy as np

CHART_THEMES = {
    "nature":  {"palette": ["#E64B35","#4DBBD5","#00A087","#3C5488","#F39B7F","#8491B4","#B09C85","#91D1C2"], "edge":"#333", "grid": True},
    "ieee":    {"palette": ["#0072BD","#D95319","#EDB120","#7E2F8E","#77AC30","#4DBEEE","#A2142F","#DDA0DD"], "edge":"#333", "grid": True},
    "apa":     {"palette": ["#5B9BD5","#ED7D31","#A5A5A5","#FFC000","#4472C4","#70AD47","#D665A0","#8B6FC0"], "edge":"#555", "grid": False},
    "default": {"palette": ["#4a6b8a","#5d7a5a","#a05252","#8a754a","#6b8a4a","#4a5d8a","#8a5a6b","#5a8a8a"], "edge":"#4a6b8a", "grid": True},
}


def parse_csv(file_bytes: bytes, encoding: str = "utf-8", delimiter: str = ",",
              skip_rows: int = 0, header_row: int = 0) -> dict:
    text = file_bytes.decode(encoding, errors="replace")
    _delim = "\t" if delimiter == "tab" else delimiter
    reader = csv.reader(io.StringIO(text), delimiter=_delim)
    rows = list(reader)
    if not rows:
        return {"columns": [], "rows": [], "types": {}, "total_rows": 0, "all_rows": []}

    # Skip rows
    data_rows = rows[skip_rows:]

    # Determine header row
    if header_row < len(data_rows):
        cols = data_rows[header_row]
        body = data_rows[header_row + 1:]
    else:
        cols = data_rows[0] if data_rows else []
        body = data_rows[1:]

    # Clean column names — strip whitespace and BOM
    cols = [c.strip().lstrip('﻿') or f"col_{i}" for i, c in enumerate(cols)]

    preview = body[:20]
    all_rows = body
    types = {}
    for ci, col in enumerate(cols):
        vals = [row[ci] for row in preview if ci < len(row) and _safe_val(row[ci])]
        nc = sum(1 for v in vals if v.replace(".", "").replace("-", "").replace(",", "").isdigit())
        types[col] = "numeric" if vals and nc / len(vals) > 0.5 else "text"
    return {"columns": cols, "rows": preview, "types": types, "total_rows": len(body),
            "all_rows": all_rows}


def parse_pasted_text(text: str, delimiter: str = "auto") -> dict:
    """Parse tabular data pasted from clipboard (Excel/Sheets compatible)."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return {"columns": [], "rows": [], "types": {}, "total_rows": 0, "all_rows": []}

    # Auto-detect delimiter
    if delimiter == "auto":
        first = lines[0]
        tabs = first.count("\t")
        commas = first.count(",")
        semicolons = first.count(";")
        if tabs >= commas and tabs >= semicolons:
            delim = "\t"
        elif semicolons > commas:
            delim = ";"
        else:
            delim = ","
    elif delimiter == "tab":
        delim = "\t"
    else:
        delim = delimiter

    rows = [list(csv.reader([line], delimiter=delim))[0] for line in lines]
    cols = rows[0] if rows else []
    cols = [c.strip() or f"col_{i}" for i, c in enumerate(cols)]
    body = rows[1:]
    preview = body[:20]

    types = {}
    for ci, col in enumerate(cols):
        vals = [row[ci] for row in preview if ci < len(row) and _safe_val(row[ci])]
        nc = sum(1 for v in vals if v.replace(".", "").replace("-", "").replace(",", "").isdigit())
        types[col] = "numeric" if vals and nc / len(vals) > 0.5 else "text"

    return {"columns": cols, "rows": preview, "types": types, "total_rows": len(body),
            "all_rows": body}


# ── Sample datasets ──
SAMPLE_DATASETS = {
    "iris": {
        "name": "Iris 鸢尾花",
        "description": "3种鸢尾花各50个样本，含花萼/花瓣尺寸，经典分类数据集",
        "category": "biology",
    },
    "tips": {
        "name": "Tips 小费",
        "description": "餐厅消费记录，含账单金额、小费、性别、吸烟、日期等",
        "category": "social",
    },
    "mpg": {
        "name": "MPG 汽车油耗",
        "description": "398款汽车的油耗(MPG)、气缸数、马力、重量、产地等",
        "category": "engineering",
    },
    "penguins": {
        "name": "Penguins 企鹅",
        "description": "3种企鹅的喙长、喙深、鳍长、体重、性别等，替代Iris的现代数据集",
        "category": "biology",
    },
    "diamonds": {
        "name": "Diamonds 钻石",
        "description": "5.4万颗钻石的克拉、切工、颜色、净度、价格，ggplot2经典数据",
        "category": "business",
    },
}

_SAMPLE_ROWS = {}

def _init_samples():
    """Lazy-load sample datasets (first 500 rows each)."""
    global _SAMPLE_ROWS
    if _SAMPLE_ROWS:
        return

    # Iris
    iris_cols = ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"]
    iris_data = [
        [5.1,3.5,1.4,0.2,"setosa"],[4.9,3.0,1.4,0.2,"setosa"],[4.7,3.2,1.3,0.2,"setosa"],
        [4.6,3.1,1.5,0.2,"setosa"],[5.0,3.6,1.4,0.2,"setosa"],[5.4,3.9,1.7,0.4,"setosa"],
        [4.6,3.4,1.4,0.3,"setosa"],[5.0,3.4,1.5,0.2,"setosa"],[4.4,2.9,1.4,0.2,"setosa"],
        [4.9,3.1,1.5,0.1,"setosa"],[5.4,3.7,1.5,0.2,"setosa"],[4.8,3.4,1.6,0.2,"setosa"],
        [4.8,3.0,1.4,0.1,"setosa"],[4.3,3.0,1.1,0.1,"setosa"],[5.8,4.0,1.2,0.2,"setosa"],
        [5.7,4.4,1.5,0.4,"setosa"],[5.4,3.9,1.3,0.4,"setosa"],[5.1,3.5,1.4,0.3,"setosa"],
        [5.7,3.8,1.7,0.3,"setosa"],[5.1,3.8,1.5,0.3,"setosa"],[5.4,3.4,1.7,0.2,"setosa"],
        [5.1,3.7,1.5,0.4,"setosa"],[4.6,3.6,1.0,0.2,"setosa"],[5.1,3.3,1.7,0.5,"setosa"],
        [4.8,3.4,1.9,0.2,"setosa"],[5.0,3.0,1.6,0.2,"setosa"],[5.0,3.4,1.6,0.4,"setosa"],
        [5.2,3.5,1.5,0.2,"setosa"],[5.2,3.4,1.4,0.2,"setosa"],[4.7,3.2,1.6,0.2,"setosa"],
        [4.8,3.1,1.6,0.2,"setosa"],[5.4,3.4,1.5,0.4,"setosa"],[5.2,4.1,1.5,0.1,"setosa"],
        [5.5,4.2,1.4,0.2,"setosa"],[4.9,3.1,1.5,0.2,"setosa"],[5.0,3.2,1.2,0.2,"setosa"],
        [5.5,3.5,1.3,0.2,"setosa"],[4.9,3.6,1.4,0.1,"setosa"],[4.4,3.0,1.3,0.2,"setosa"],
        [5.1,3.4,1.5,0.2,"setosa"],[5.0,3.5,1.3,0.3,"setosa"],[4.5,2.3,1.3,0.3,"setosa"],
        [4.4,3.2,1.3,0.2,"setosa"],[5.0,3.5,1.6,0.6,"setosa"],[5.1,3.8,1.9,0.4,"setosa"],
        [4.8,3.0,1.4,0.3,"setosa"],[5.1,3.8,1.6,0.2,"setosa"],[4.6,3.2,1.4,0.2,"setosa"],
        [5.3,3.7,1.5,0.2,"setosa"],[5.0,3.3,1.4,0.2,"setosa"],
        [7.0,3.2,4.7,1.4,"versicolor"],[6.4,3.2,4.5,1.5,"versicolor"],[6.9,3.1,4.9,1.5,"versicolor"],
        [5.5,2.3,4.0,1.3,"versicolor"],[6.5,2.8,4.6,1.5,"versicolor"],[5.7,2.8,4.5,1.3,"versicolor"],
        [6.3,3.3,4.7,1.6,"versicolor"],[4.9,2.4,3.3,1.0,"versicolor"],[6.6,2.9,4.6,1.3,"versicolor"],
        [5.2,2.7,3.9,1.4,"versicolor"],[5.0,2.0,3.5,1.0,"versicolor"],[5.9,3.0,4.2,1.5,"versicolor"],
        [6.0,2.2,4.0,1.0,"versicolor"],[6.1,2.9,4.7,1.4,"versicolor"],[5.6,2.9,3.6,1.3,"versicolor"],
        [6.7,3.1,4.4,1.4,"versicolor"],[5.6,3.0,4.5,1.5,"versicolor"],[5.8,2.7,4.1,1.0,"versicolor"],
        [6.2,2.2,4.5,1.5,"versicolor"],[5.6,2.5,3.9,1.1,"versicolor"],[5.9,3.2,4.8,1.8,"versicolor"],
        [6.1,2.8,4.0,1.3,"versicolor"],[6.3,2.5,4.9,1.5,"versicolor"],[6.1,2.8,4.7,1.2,"versicolor"],
        [6.4,2.9,4.3,1.3,"versicolor"],[6.6,3.0,4.4,1.4,"versicolor"],[6.8,2.8,4.8,1.4,"versicolor"],
        [6.7,3.0,5.0,1.7,"versicolor"],[6.0,2.9,4.5,1.5,"versicolor"],[5.7,2.6,3.5,1.0,"versicolor"],
        [5.5,2.4,3.8,1.1,"versicolor"],[5.5,2.4,3.7,1.0,"versicolor"],[5.8,2.7,3.9,1.2,"versicolor"],
        [6.0,2.7,5.1,1.6,"versicolor"],[5.4,3.0,4.5,1.5,"versicolor"],[6.0,3.4,4.5,1.6,"versicolor"],
        [6.7,3.1,4.7,1.5,"versicolor"],[6.3,2.3,4.4,1.3,"versicolor"],[5.6,3.0,4.1,1.3,"versicolor"],
        [5.5,2.5,4.0,1.3,"versicolor"],[5.5,2.6,4.4,1.2,"versicolor"],[6.1,3.0,4.6,1.4,"versicolor"],
        [5.8,2.6,4.0,1.2,"versicolor"],[5.0,2.3,3.3,1.0,"versicolor"],[5.6,2.7,4.2,1.3,"versicolor"],
        [5.7,3.0,4.2,1.2,"versicolor"],[5.7,2.9,4.2,1.3,"versicolor"],[6.2,2.9,4.3,1.3,"versicolor"],
        [5.1,2.5,3.0,1.1,"versicolor"],[5.7,2.8,4.1,1.3,"versicolor"],
        [6.3,3.3,6.0,2.5,"virginica"],[5.8,2.7,5.1,1.9,"virginica"],[7.1,3.0,5.9,2.1,"virginica"],
        [6.3,2.9,5.6,1.8,"virginica"],[6.5,3.0,5.8,2.2,"virginica"],[7.6,3.0,6.6,2.1,"virginica"],
        [4.9,2.5,4.5,1.7,"virginica"],[7.3,2.9,6.3,1.8,"virginica"],[6.7,2.5,5.8,1.8,"virginica"],
        [7.2,3.6,6.1,2.5,"virginica"],[6.5,3.2,5.1,2.0,"virginica"],[6.4,2.7,5.3,1.9,"virginica"],
        [6.8,3.0,5.5,2.1,"virginica"],[5.7,2.5,5.0,2.0,"virginica"],[5.8,2.8,5.1,2.4,"virginica"],
        [6.4,3.2,5.3,2.3,"virginica"],[6.5,3.0,5.5,1.8,"virginica"],[7.7,3.8,6.7,2.2,"virginica"],
        [7.7,2.6,6.9,2.3,"virginica"],[6.0,2.2,5.0,1.5,"virginica"],[6.9,3.2,5.7,2.3,"virginica"],
        [5.6,2.8,4.9,2.0,"virginica"],[7.7,2.8,6.7,2.0,"virginica"],[6.3,2.7,4.9,1.8,"virginica"],
        [6.7,3.3,5.7,2.1,"virginica"],[7.2,3.2,6.0,1.8,"virginica"],[6.2,2.8,4.8,1.8,"virginica"],
        [6.1,3.0,4.9,1.8,"virginica"],[6.4,2.8,5.6,2.1,"virginica"],[7.2,3.0,5.8,1.6,"virginica"],
        [7.4,2.8,6.1,1.9,"virginica"],[7.9,3.8,6.4,2.0,"virginica"],[6.4,2.8,5.6,2.2,"virginica"],
        [6.3,2.8,5.1,1.5,"virginica"],[6.1,2.6,5.6,1.4,"virginica"],[7.7,3.0,6.1,2.3,"virginica"],
        [6.3,3.4,5.6,2.4,"virginica"],[6.4,3.1,5.5,1.8,"virginica"],[6.0,3.0,4.8,1.8,"virginica"],
        [6.9,3.1,5.4,2.1,"virginica"],[6.7,3.1,5.6,2.4,"virginica"],[6.9,3.1,5.1,2.3,"virginica"],
        [5.8,2.7,5.1,1.9,"virginica"],[6.8,3.2,5.9,2.3,"virginica"],[6.7,3.3,5.7,2.5,"virginica"],
        [6.7,3.0,5.2,2.3,"virginica"],[6.3,2.5,5.0,1.9,"virginica"],[6.5,3.0,5.2,2.0,"virginica"],
        [6.2,3.4,5.4,2.3,"virginica"],[5.9,3.0,5.1,1.8,"virginica"],
    ]
    _SAMPLE_ROWS["iris"] = {"columns": iris_cols, "rows": [[str(c) for c in r] for r in iris_data]}

    # Tips
    tips_cols = ["total_bill", "tip", "sex", "smoker", "day", "time", "size"]
    tips_data = [
        [16.99,1.01,"Female","No","Sun","Dinner",2],[10.34,1.66,"Male","No","Sun","Dinner",3],
        [21.01,3.50,"Male","No","Sun","Dinner",3],[23.68,3.31,"Male","No","Sun","Dinner",2],
        [24.59,3.61,"Female","No","Sun","Dinner",4],[25.29,4.71,"Male","No","Sun","Dinner",4],
        [8.77,2.00,"Male","No","Sun","Dinner",2],[26.88,3.12,"Male","No","Sun","Dinner",4],
        [15.04,1.96,"Male","No","Sun","Dinner",2],[14.78,3.23,"Male","No","Sun","Dinner",2],
        [10.27,1.71,"Male","No","Sun","Dinner",2],[35.26,5.00,"Female","No","Sun","Dinner",4],
        [15.42,1.57,"Male","No","Sun","Dinner",2],[18.43,3.00,"Male","No","Sun","Dinner",4],
        [17.75,2.50,"Female","Yes","Sun","Dinner",2],[18.68,3.50,"Female","No","Sun","Dinner",3],
        [16.40,2.30,"Female","Yes","Sat","Dinner",2],[25.00,3.00,"Female","Yes","Sat","Dinner",2],
        [20.10,3.00,"Male","No","Sat","Dinner",2],[17.78,2.50,"Male","Yes","Sat","Dinner",2],
        [15.64,2.00,"Male","Yes","Sat","Dinner",2],[31.36,5.50,"Male","No","Sat","Dinner",2],
        [29.86,4.80,"Male","No","Sat","Dinner",4],[21.00,2.80,"Female","Yes","Sat","Dinner",3],
        [38.01,7.50,"Male","No","Sat","Dinner",4],[12.66,1.20,"Male","Yes","Sat","Dinner",2],
        [16.50,2.30,"Female","No","Sat","Dinner",4],[20.29,2.70,"Female","No","Sat","Dinner",2],
        [13.00,1.30,"Male","No","Sat","Dinner",2],[15.66,1.70,"Male","Yes","Sat","Dinner",2],
        [12.00,1.50,"Male","No","Thur","Lunch",2],[14.40,2.00,"Male","No","Thur","Lunch",2],
        [15.00,2.25,"Female","No","Thur","Lunch",2],[12.73,1.25,"Male","Yes","Thur","Lunch",2],
        [20.45,3.75,"Male","No","Thur","Lunch",2],[13.82,1.50,"Female","No","Thur","Lunch",2],
        [8.95,1.00,"Male","No","Fri","Dinner",2],[9.77,1.15,"Female","No","Fri","Dinner",2],
        [27.00,4.00,"Male","No","Fri","Dinner",2],[15.53,2.00,"Male","Yes","Fri","Dinner",2],
        [14.30,1.75,"Male","No","Fri","Dinner",2],[24.50,3.25,"Female","No","Fri","Dinner",4],
        [17.43,2.25,"Male","No","Fri","Dinner",2],[33.11,5.00,"Male","No","Fri","Dinner",2],
        [25.91,4.20,"Male","No","Fri","Dinner",2],[20.25,3.00,"Female","No","Fri","Dinner",2],
        [23.17,4.00,"Female","No","Fri","Dinner",2],[25.97,4.50,"Male","No","Fri","Dinner",4],
        [22.69,3.50,"Female","No","Fri","Dinner",2],[9.77,1.00,"Male","No","Fri","Dinner",2],
    ]
    _SAMPLE_ROWS["tips"] = {"columns": tips_cols, "rows": [[str(c) for c in r] for r in tips_data]}

    # MPG (auto-mpg)
    mpg_cols = ["mpg", "cylinders", "displacement", "horsepower", "weight", "acceleration", "model_year", "origin", "name"]
    mpg_data = [
        [18.0,8,307.0,130.0,3504,12.0,70,"USA","chevrolet chevelle malibu"],
        [15.0,8,350.0,165.0,3693,11.5,70,"USA","buick skylark 320"],
        [18.0,8,318.0,150.0,3436,11.0,70,"USA","plymouth satellite"],
        [16.0,8,304.0,150.0,3433,12.0,70,"USA","amc rebel sst"],
        [17.0,8,302.0,140.0,3449,10.5,70,"USA","ford torino"],
        [15.0,8,429.0,198.0,4341,10.0,70,"USA","ford galaxie 500"],
        [14.0,8,454.0,220.0,4354,9.0,70,"USA","chevrolet impala"],
        [14.0,8,440.0,215.0,4312,8.5,70,"USA","plymouth fury iii"],
        [14.0,8,455.0,225.0,4425,10.0,70,"USA","pontiac catalina"],
        [15.0,8,390.0,190.0,3850,8.5,70,"USA","amc ambassador dpl"],
        [21.0,6,199.0,90.0,2648,15.0,70,"USA","dodge challenger se"],
        [26.0,4,97.0,46.0,1943,19.0,70,"Europe","volkswagen 1131 deluxe"],
        [26.0,4,97.0,52.0,2150,16.0,70,"Japan","toyota corona mark ii"],
        [24.0,4,113.0,95.0,2278,15.5,70,"Europe","volkswagen type 3"],
        [27.0,4,97.0,88.0,2100,14.5,70,"Japan","datsun pl510"],
        [25.0,4,110.0,87.0,2620,14.5,70,"Europe","volvo 144ea"],
        [23.0,4,120.0,86.0,2372,17.0,70,"Europe","saab 99e"],
        [28.0,4,90.0,65.0,2110,19.5,70,"Europe","renault 12tl"],
        [24.0,6,198.0,95.0,2904,16.0,70,"USA","ford maverick"],
        [25.0,6,225.0,85.0,2800,17.6,70,"Japan","toyota corona"],
        [23.0,6,250.0,82.0,2930,18.5,70,"USA","amc gremlin"],
        [26.0,4,98.0,70.0,2120,15.5,70,"Japan","subaru dl"],
        [18.0,6,232.0,100.0,2837,17.0,70,"USA","chevrolet nova custom"],
        [17.0,6,250.0,100.0,3050,17.0,70,"USA","dodge coronet custom"],
        [26.0,4,91.0,70.0,1985,20.5,70,"Japan","toyota corolla 1200"],
        [31.0,4,85.0,72.0,1890,19.5,70,"Europe","fiat 128"],
        [19.0,6,250.0,90.0,2955,18.5,70,"USA","plymouth duster"],
        [21.0,4,98.0,82.0,1945,21.0,70,"Europe","opel kadett"],
        [24.0,4,79.0,60.0,2013,19.0,70,"Europe","peugeot 204"],
        [18.0,6,250.0,92.0,3140,17.5,70,"USA","ford mustang ii"],
        [30.0,4,111.0,80.0,2155,14.8,71,"Europe","buick century"],
        [23.0,4,97.0,54.0,2254,23.5,72,"Europe","vw super beetle"],
        [35.0,4,72.0,50.0,1755,19.0,71,"Europe","honda civic"],
        [26.0,4,91.0,67.0,1965,16.0,71,"Japan","datsun 510"],
        [20.0,6,258.0,110.0,3632,13.0,71,"USA","oldsmobile omega"],
        [25.0,4,104.0,95.0,2375,17.5,70,"Europe","peugeot 504"],
        [32.0,4,83.0,61.0,2003,19.0,74,"Europe","fiat 124b"],
        [31.0,4,79.0,67.0,2000,16.0,74,"Japan","honda civic cvcc"],
        [29.0,4,85.0,65.0,1975,19.4,74,"Europe","fiat x1.9"],
        [27.0,4,90.0,75.0,2125,14.5,74,"Europe","vw rabbit"],
        [23.0,6,250.0,100.0,3282,15.0,71,"USA","chevrolet vega"],
        [23.0,6,200.0,85.0,2990,18.2,75,"USA","ford pinto runabout"],
        [25.0,4,140.0,72.0,2408,19.0,76,"Japan","toyota corolla"],
        [30.0,4,101.0,83.0,2225,16.5,78,"Europe","dodge colt"],
        [29.0,4,98.0,67.0,1915,19.2,78,"Europe","datsun 210"],
        [28.0,4,97.0,78.0,2160,17.0,78,"Japan","honda accord"],
    ]
    _SAMPLE_ROWS["mpg"] = {"columns": mpg_cols, "rows": [[str(c) for c in r] for r in mpg_data]}

    # Penguins (subset)
    penguins_cols = ["species", "island", "bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g", "sex"]
    penguins_data = [
        ["Adelie","Torgersen",39.1,18.7,181,3750,"male"],
        ["Adelie","Torgersen",39.5,17.4,186,3800,"female"],
        ["Adelie","Torgersen",40.3,18.0,195,3250,"female"],
        ["Adelie","Torgersen",36.7,19.3,193,3450,"female"],
        ["Adelie","Torgersen",39.3,20.6,190,3650,"male"],
        ["Adelie","Torgersen",38.9,17.8,181,3625,"female"],
        ["Adelie","Torgersen",39.2,19.6,195,4675,"male"],
        ["Adelie","Torgersen",34.1,18.1,193,3475,"female"],
        ["Adelie","Torgersen",42.0,20.2,190,4250,"male"],
        ["Adelie","Torgersen",37.8,17.1,186,3300,"female"],
        ["Adelie","Torgersen",37.8,17.3,180,3700,"female"],
        ["Adelie","Torgersen",41.1,17.6,182,3200,"female"],
        ["Adelie","Torgersen",38.6,21.2,191,3800,"male"],
        ["Adelie","Torgersen",34.6,21.1,198,4400,"male"],
        ["Adelie","Torgersen",36.6,17.8,185,3700,"female"],
        ["Adelie","Torgersen",38.7,19.0,195,3450,"female"],
        ["Adelie","Torgersen",42.5,20.7,197,4500,"male"],
        ["Adelie","Torgersen",34.4,18.4,184,3325,"female"],
        ["Adelie","Torgersen",46.0,21.5,194,4200,"male"],
        ["Adelie","Biscoe",37.8,18.3,174,3400,"female"],
        ["Adelie","Biscoe",37.7,18.7,180,3600,"male"],
        ["Adelie","Biscoe",35.9,19.2,189,3800,"female"],
        ["Adelie","Biscoe",38.2,18.1,185,3950,"male"],
        ["Adelie","Biscoe",38.8,17.2,180,3800,"male"],
        ["Adelie","Biscoe",35.3,18.9,187,3800,"female"],
        ["Adelie","Biscoe",40.6,18.6,183,3550,"female"],
        ["Adelie","Biscoe",40.5,17.9,187,3200,"female"],
        ["Adelie","Biscoe",37.9,18.6,172,3150,"female"],
        ["Adelie","Biscoe",40.5,18.9,180,3950,"male"],
        ["Adelie","Dream",39.5,16.7,178,3250,"female"],
        ["Adelie","Dream",37.2,18.1,178,3900,"male"],
        ["Adelie","Dream",39.5,17.8,188,3300,"female"],
        ["Adelie","Dream",40.9,18.9,184,3900,"male"],
        ["Adelie","Dream",36.4,17.0,195,3325,"female"],
        ["Adelie","Dream",39.2,21.1,196,4150,"male"],
        ["Adelie","Dream",38.8,20.0,190,3950,"male"],
        ["Adelie","Dream",42.2,18.5,180,3550,"female"],
        ["Adelie","Dream",37.6,19.3,181,3300,"female"],
        ["Adelie","Dream",39.8,19.1,184,4650,"male"],
        ["Adelie","Dream",36.5,18.0,182,3150,"female"],
        ["Adelie","Dream",40.8,18.4,195,3900,"male"],
        ["Adelie","Dream",36.0,18.5,186,3100,"female"],
        ["Adelie","Dream",44.1,19.7,196,4400,"male"],
        ["Adelie","Dream",37.0,14.2,183,3450,"male"],
        ["Gentoo","Biscoe",46.1,13.2,211,4500,"female"],
        ["Gentoo","Biscoe",50.0,16.3,230,5700,"male"],
        ["Gentoo","Biscoe",48.7,14.1,210,4450,"female"],
        ["Gentoo","Biscoe",50.0,15.2,218,5700,"male"],
        ["Gentoo","Biscoe",47.6,14.5,215,5400,"male"],
    ]
    _SAMPLE_ROWS["penguins"] = {"columns": penguins_cols, "rows": [[str(c) for c in r] for r in penguins_data]}

    # Diamonds (subset)
    diamonds_cols = ["carat", "cut", "color", "clarity", "depth", "table", "price", "x", "y", "z"]
    diamonds_data = [
        [0.23,"Ideal","E","SI2",61.5,55,326,3.95,3.98,2.43],
        [0.21,"Premium","E","SI1",59.8,61,326,3.89,3.84,2.31],
        [0.23,"Good","E","VS1",56.9,65,327,4.05,4.07,2.31],
        [0.29,"Premium","I","VS2",62.4,58,334,4.20,4.23,2.63],
        [0.31,"Good","J","SI2",63.3,58,335,4.34,4.35,2.75],
        [0.24,"Very Good","J","VVS2",62.8,57,336,3.94,3.96,2.48],
        [0.24,"Very Good","I","VVS1",62.3,57,336,3.95,3.98,2.47],
        [0.26,"Very Good","H","SI1",61.9,55,337,4.07,4.11,2.53],
        [0.22,"Fair","E","VS2",65.1,61,337,3.87,3.78,2.49],
        [0.23,"Very Good","H","VS1",59.4,61,338,4.00,4.05,2.39],
        [0.30,"Good","J","SI1",64.0,55,339,4.25,4.28,2.73],
        [0.23,"Ideal","J","VS1",62.8,56,340,3.93,3.90,2.46],
        [0.22,"Premium","F","SI1",60.4,61,342,3.88,3.84,2.33],
        [0.31,"Ideal","J","SI2",62.2,54,344,4.35,4.37,2.71],
        [0.20,"Premium","E","SI2",60.2,62,345,3.79,3.75,2.27],
        [0.32,"Premium","E","I1",60.9,58,345,4.38,4.42,2.68],
        [0.30,"Ideal","I","SI2",62.0,54,348,4.31,4.34,2.68],
        [0.30,"Good","J","SI1",63.4,54,351,4.23,4.29,2.70],
        [0.30,"Good","J","SI1",63.8,56,351,4.23,4.26,2.71],
        [0.30,"Very Good","J","SI1",62.7,59,351,4.21,4.27,2.66],
        [0.30,"Good","I","SI2",63.3,56,351,4.26,4.30,2.71],
        [0.23,"Very Good","E","VS2",63.8,55,352,3.85,3.92,2.48],
        [0.23,"Very Good","H","VS1",61.0,57,353,3.94,3.96,2.41],
        [0.31,"Very Good","J","SI1",59.4,62,353,4.39,4.43,2.62],
        [0.31,"Very Good","J","SI1",58.1,62,353,4.44,4.47,2.59],
        [0.23,"Very Good","G","VVS2",60.4,58,354,3.97,4.01,2.41],
        [0.24,"Premium","I","VS1",62.5,57,355,3.97,3.94,2.47],
        [0.30,"Very Good","J","VS2",62.2,57,357,4.28,4.30,2.67],
        [0.23,"Very Good","D","VS2",60.5,61,357,3.96,3.97,2.40],
        [0.23,"Very Good","F","VS1",60.9,57,357,3.96,3.99,2.42],
        [0.23,"Very Good","F","VS1",60.0,57,402,4.00,4.03,2.41],
        [0.23,"Very Good","F","VS1",59.8,57,402,4.04,4.06,2.42],
        [0.23,"Very Good","E","VS2",60.7,59,402,4.02,4.03,2.44],
        [0.23,"Very Good","E","VS2",59.3,59,402,4.06,4.08,2.42],
        [0.31,"Good","D","SI1",63.1,59,402,4.29,4.31,2.71],
        [0.26,"Good","D","VS2",62.8,58,403,4.03,4.06,2.54],
        [0.26,"Good","D","VS2",63.8,58,403,4.04,4.10,2.57],
        [0.26,"Very Good","E","SI2",57.7,63,403,4.12,4.16,2.39],
        [0.26,"Good","H","SI2",64.3,59,403,4.03,4.05,2.60],
        [0.30,"Very Good","H","SI1",60.5,56,403,4.32,4.34,2.62],
        [0.30,"Good","H","SI1",63.8,56,403,4.26,4.29,2.73],
        [0.32,"Premium","G","VS2",61.1,58,403,4.44,4.40,2.70],
        [0.23,"Ideal","G","VS1",61.9,54,404,3.93,3.95,2.44],
        [0.23,"Ideal","G","VVS1",61.9,54,404,3.91,3.96,2.44],
        [0.26,"Ideal","H","VVS1",62.0,56,404,4.04,4.07,2.52],
        [0.26,"Ideal","G","VS2",62.0,54,404,4.04,4.08,2.52],
        [0.30,"Ideal","H","SI1",61.8,56,405,4.34,4.38,2.69],
        [0.26,"Very Good","E","VVS2",63.4,59,405,4.06,4.09,2.58],
        [0.26,"Very Good","D","VVS1",62.3,58,405,4.07,4.12,2.55],
        [0.26,"Very Good","E","VVS1",61.2,58,405,4.11,4.13,2.52],
    ]
    _SAMPLE_ROWS["diamonds"] = {"columns": diamonds_cols, "rows": [[str(c) for c in r] for r in diamonds_data]}


def get_sample_dataset(key: str) -> dict | None:
    """Return a sample dataset by key, with computed types and full rows."""
    _init_samples()
    data = _SAMPLE_ROWS.get(key)
    if not data:
        return None
    cols = data["columns"]
    rows = data["rows"]
    preview = rows[:20]
    types = {}
    for ci, col in enumerate(cols):
        vals = [row[ci] for row in preview if ci < len(row) and _safe_val(row[ci])]
        nc = sum(1 for v in vals if v.replace(".", "").replace("-", "").replace(",", "").isdigit())
        types[col] = "numeric" if vals and nc / len(vals) > 0.5 else "text"
    return {"columns": cols, "rows": preview, "types": types, "total_rows": len(rows),
            "all_rows": rows}


def list_sample_datasets() -> list:
    """List available sample datasets with metadata."""
    return [{"key": k, "name": v["name"], "description": v["description"],
             "category": v["category"]} for k, v in SAMPLE_DATASETS.items()]


# ── Data preprocessing ──
def compute_stats(data_info: dict) -> dict:
    """Compute descriptive statistics for all columns."""
    cols = data_info.get("columns", [])
    rows = data_info.get("all_rows", data_info.get("rows", []))
    types = data_info.get("types", {})
    stats = {}
    for ci, col in enumerate(cols):
        vals = []
        for row in rows:
            if ci < len(row):
                v = row[ci]
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    vals.append(s)
        if not vals:
            stats[col] = {"type": "empty", "count": 0}
            continue
        col_type = types.get(col, "text")
        if col_type == "numeric":
            import math as _math
            # Filter out NaN and Inf values before processing
            clean_vals = []
            nan_count = 0
            for v in vals:
                try:
                    fv = float(v)
                    if _math.isfinite(fv):
                        clean_vals.append(fv)
                    else:
                        nan_count += 1
                except (ValueError, TypeError):
                    nan_count += 1
            nums = sorted(clean_vals)
            n = len(nums)
            if n == 0:
                stats[col] = {"type": "empty", "count": 0, "missing": len(rows), "nan_count": nan_count}
                continue
            mean_v = sum(nums) / n
            median_v = nums[n // 2] if n % 2 else (nums[n // 2 - 1] + nums[n // 2]) / 2
            std_v = (sum((v - mean_v) ** 2 for v in nums) / n) ** 0.5
            cv = round(std_v / mean_v, 3) if mean_v != 0 else 0
            q1 = nums[n // 4]
            q3 = nums[3 * n // 4]
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr
            iqr_outliers = [v for v in nums if v < lower_fence or v > upper_fence]
            # Z-score outliers: |z| > 2 for small samples, > 2.5 for larger
            z_threshold = 2 if n <= 30 else 2.5
            z_outliers = [v for v in nums if std_v > 0 and abs((v - mean_v) / std_v) > z_threshold]
            # Combined: union of both methods
            all_outliers = sorted(set(iqr_outliers + z_outliers))
            stats[col] = {
                "type": "numeric", "count": n, "missing": len(rows) - n - nan_count,
                "nan_count": nan_count,
                "min": round(nums[0], 3), "max": round(nums[-1], 3), "mean": round(mean_v, 3),
                "median": round(median_v, 3), "std": round(std_v, 3),
                "cv": cv,  # coefficient of variation
                "q1": round(q1, 3), "q3": round(q3, 3),
                "iqr": round(iqr, 3),
                "outliers": len(all_outliers),
                "outlier_values": [round(v, 3) for v in all_outliers[:5]],
                "iqr_outliers": len(iqr_outliers),
                "z_outliers": len(z_outliers),
            }
        else:
            unique = list(set(vals))
            stats[col] = {
                "type": "text", "count": len(vals), "missing": len(rows) - len(vals),
                "unique": len(unique), "top_values": sorted(unique, key=lambda x: -vals.count(x))[:5],
            }
    return stats


def preprocess_data(data_info: dict, operations: list[dict]) -> dict:
    """Apply preprocessing operations to data. Returns updated data_info.

    Supported operations:
      - {"op": "drop_missing", "columns": ["col1", ...] or [] for all}
      - {"op": "fill_missing", "columns": [...], "method": "mean"|"median"|"mode"}
      - {"op": "normalize", "columns": [...], "method": "zscore"|"minmax"|"log"}
      - {"op": "filter", "column": "col", "operator": "eq|neq|gt|gte|lt|lte|contains", "value": "..."}
      - {"op": "sort", "column": "col", "ascending": true}
    """
    cols = data_info.get("columns", [])
    rows = [list(r) for r in data_info.get("all_rows", data_info.get("rows", []))]
    types = dict(data_info.get("types", {}))

    for op in operations:
        op_name = op.get("op", "")

        if op_name == "drop_missing":
            target_cols = op.get("columns") or cols
            ci_list = [cols.index(c) for c in target_cols if c in cols]
            rows = [r for r in rows if all(ci < len(r) and _safe_val(r[ci]) for ci in ci_list)]

        elif op_name == "fill_missing":
            method = op.get("method", "mean")
            for col in (op.get("columns") or []):
                if col not in cols:
                    continue
                ci = cols.index(col)
                if types.get(col) == "numeric":
                    vals = [float(r[ci]) for r in rows if ci < len(r) and _safe_val(r[ci])]
                    if not vals:
                        continue
                    if method == "mean":
                        fill_v = sum(vals) / len(vals)
                    elif method == "median":
                        sv = sorted(vals)
                        fill_v = sv[len(sv) // 2] if len(sv) % 2 else (sv[len(sv) // 2 - 1] + sv[len(sv) // 2]) / 2
                    else:
                        fill_v = sum(vals) / len(vals)
                    fill_str = f"{fill_v:.3f}"
                else:
                    from collections import Counter
                    vals = [r[ci] for r in rows if ci < len(r) and _safe_val(r[ci])]
                    fill_str = Counter(vals).most_common(1)[0][0] if vals else ""
                for r in rows:
                    if ci < len(r) and not _safe_val(r[ci]):
                        r[ci] = fill_str

        elif op_name == "normalize":
            method = op.get("method", "zscore")
            for col in (op.get("columns") or []):
                if col not in cols or types.get(col) != "numeric":
                    continue
                ci = cols.index(col)
                nums = [float(r[ci]) for r in rows if ci < len(r) and _safe_val(r[ci])]
                if not nums:
                    continue
                mean_v = sum(nums) / len(nums)
                std_v = (sum((v - mean_v) ** 2 for v in nums) / len(nums)) ** 0.5
                min_v, max_v = min(nums), max(nums)
                for r in rows:
                    if ci < len(r) and _safe_val(r[ci]):
                        v = float(r[ci])
                        if method == "zscore" and std_v > 0:
                            r[ci] = f"{(v - mean_v) / std_v:.4f}"
                        elif method == "minmax" and max_v > min_v:
                            r[ci] = f"{(v - min_v) / (max_v - min_v):.4f}"
                        elif method == "log" and v > 0:
                            import math
                            r[ci] = f"{math.log(v):.4f}"
                types[col] = "numeric"

        elif op_name == "filter":
            col = op.get("column", "")
            if col not in cols:
                continue
            ci = cols.index(col)
            operator = op.get("operator", "eq")
            val = str(op.get("value", ""))
            new_rows = []
            for r in rows:
                if ci >= len(r):
                    continue
                cell = _safe_val(r[ci])
                if operator == "eq" and cell == val:
                    new_rows.append(r)
                elif operator == "neq" and cell != val:
                    new_rows.append(r)
                elif operator == "gt" and cell > val:
                    new_rows.append(r)
                elif operator == "gte" and cell >= val:
                    new_rows.append(r)
                elif operator == "lt" and cell < val:
                    new_rows.append(r)
                elif operator == "lte" and cell <= val:
                    new_rows.append(r)
                elif operator == "contains" and val in cell:
                    new_rows.append(r)
            rows = new_rows

        elif op_name == "sort":
            col = op.get("column", "")
            if col not in cols:
                continue
            ci = cols.index(col)
            asc = op.get("ascending", True)
            is_num = types.get(col) == "numeric"
            def sort_key(r):
                if ci >= len(r):
                    return (0, "")
                v = _safe_val(r[ci])
                return (0, float(v)) if is_num and v else (1, v)
            rows.sort(key=sort_key, reverse=not asc)

    preview = rows[:20]
    return {"columns": cols, "rows": preview, "types": types, "total_rows": len(rows),
            "all_rows": rows, "stats": compute_stats({"columns": cols, "rows": rows, "types": types})}


def _safe_val(v) -> str:
    """Convert any value to a stripped string, handling None, int, float."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def _extract_xy(data_info: dict, x_col: str, y_col: str) -> tuple:
    """Extract X and Y values. Returns (x_strings, y_floats, x_floats_or_none)."""
    rows = data_info.get("rows", [])
    cols = data_info.get("columns", [])
    try:
        xi = cols.index(x_col)
        yi = cols.index(y_col)
    except ValueError:
        return [], [], None
    xv, yv, xf = [], [], []
    x_is_numeric = True
    for row in rows:
        if xi < len(row) and yi < len(row):
            try:
                x_str = _safe_val(row[xi])
                y_str = _safe_val(row[yi])
                if not x_str or not y_str:
                    continue
                y_val = float(y_str)
                xv.append(x_str)
                yv.append(y_val)
                try:
                    xf.append(float(x_str))
                except ValueError:
                    xf.append(0)
                    x_is_numeric = False
            except (ValueError, IndexError):
                continue
    return xv, yv, (xf if x_is_numeric and len(xf) > 1 else None)


def recommend_chart(data_info: dict, x_col: str, y_col: str) -> str:
    """Auto-suggest the best chart type based on data characteristics."""
    xv, yv, xf = _extract_xy(data_info, x_col, y_col)
    if not yv:
        return "bar"
    n = len(yv)
    unique_x = len(set(xv))

    # Numeric X with many unique values → continuous
    if xf and unique_x > 15:
        return "scatter"
    if xf and unique_x > 8:
        return "line"

    # Very few categories, all distinct rows → pie
    if n <= 7 and unique_x == n:
        return "pie"

    # Few categories → bar
    if unique_x <= 15:
        return "bar"

    # Many categories but fewer than rows → histogram
    if unique_x < n:
        return "histogram"

    # Many distinct categories → line
    if n >= 10:
        return "line"

    return "bar"


def _smart_x_labels(ax, xv: list, n: int, fp, is_horizontal: bool = False):
    """Apply X/Y axis labels adaptively based on data point count."""
    if n == 0:
        return

    if is_horizontal:
        # Y-axis labels for horizontal bar charts
        if n <= 10:
            ax.set_yticks(range(n))
            ax.set_yticklabels(xv, fontsize=9, fontproperties=fp)
        elif n <= 20:
            ax.set_yticks(range(n))
            ax.set_yticklabels(xv, fontsize=8, fontproperties=fp)
        elif n <= 35:
            step = max(1, n // 25)
            ticks = range(0, n, step)
            ax.set_yticks(ticks)
            ax.set_yticklabels([xv[i] for i in ticks], fontsize=7, fontproperties=fp)
        else:
            step = max(1, n // 20)
            ticks = range(0, n, step)
            ax.set_yticks(ticks)
            ax.set_yticklabels([xv[i] for i in ticks], fontsize=6, fontproperties=fp)
    else:
        # X-axis labels
        max_label_len = max((len(str(x)) for x in xv), default=0)
        if n <= 6 and max_label_len <= 6:
            ax.set_xticks(range(n))
            ax.set_xticklabels(xv, fontsize=9, fontproperties=fp)
        elif n <= 8:
            ax.set_xticks(range(n))
            ax.set_xticklabels(xv, rotation=25, ha="right", fontsize=8, fontproperties=fp)
        elif n <= 15:
            ax.set_xticks(range(n))
            ax.set_xticklabels(xv, rotation=35, ha="right", fontsize=8, fontproperties=fp)
        elif n <= 25:
            ax.set_xticks(range(n))
            ax.set_xticklabels(xv, rotation=45, ha="right", fontsize=7, fontproperties=fp)
        elif n <= 40:
            step = max(1, n // 18)
            ticks = range(0, n, step)
            ax.set_xticks(ticks)
            ax.set_xticklabels([xv[i] for i in ticks], rotation=45, ha="right", fontsize=7, fontproperties=fp)
        else:
            step = max(1, n // 16)
            ticks = range(0, n, step)
            ax.set_xticks(ticks)
            ax.set_xticklabels([xv[i] for i in ticks], rotation=60, ha="right", fontsize=6, fontproperties=fp)


def _fmt_num(v: float) -> str:
    """Format a number cleanly for display."""
    if abs(v) >= 10000 or (0 < abs(v) < 0.001):
        return f"{v:.2e}"
    if abs(v - round(v)) < 0.0001:
        return str(int(round(v)))
    return f"{v:.4g}"


def generate_chart(data_info: dict, chart_type: str, x_col: str, y_col: str,
                   theme: str = "default", title: str = "", x_label: str = "", y_label: str = "",
                   max_points: int = 0, fmt: str = "png") -> str:
    xv, yv, xf = _extract_xy(data_info, x_col, y_col)
    if not yv:
        return ""

    # Aggregate duplicate X values for ALL chart types (mean Y per unique X)
    unique_x = list(set(xv))
    if len(unique_x) < len(xv):
        from collections import defaultdict
        groups = defaultdict(list)
        for x_val, y_val in zip(xv, yv):
            groups[x_val].append(y_val)
        xv = list(groups.keys())
        yv = [sum(vals) / len(vals) for vals in groups.values()]

    # Sort by X for readability
    if xf and chart_type not in ("pie", "donut", "radar", "box"):
        try:
            fmap = {}
            for xs, yr in zip(xv, yv):
                try:
                    fmap[xs] = float(xs)
                except ValueError:
                    fmap[xs] = 0
            pairs = sorted(zip(xv, yv), key=lambda p: fmap.get(p[0], 0))
            xv, yv = [p[0] for p in pairs], [p[1] for p in pairs]
        except Exception:
            xv, yv = zip(*sorted(zip(xv, yv), key=lambda p: str(p[0])))

    n = len(yv)

    # Smart limit: when too many unique X, keep top N or sample evenly
    limit = max_points if max_points > 0 else 15
    if n > limit:
        if chart_type in ("bar", "hbar", "stacked_bar", "pie", "donut"):
            # Keep top N by Y value, group the rest
            pairs = sorted(zip(xv, yv), key=lambda p: -p[1])
            top = pairs[:limit - 1]
            other_sum = sum(p[1] for p in pairs[limit - 1:])
            xv = [p[0] for p in top] + ["Other"]
            yv = [p[1] for p in top] + [other_sum]
            n = len(yv)
        else:
            # Evenly sample for line/scatter/area
            step = n // limit + 1
            xv = xv[::step]
            yv = yv[::step]
            n = len(yv)

    t = CHART_THEMES.get(theme, CHART_THEMES["default"])
    cs = t["palette"]
    fp = _cjk_fp()

    # For scatter/line/area with numeric X, use actual positions
    if xf and chart_type in ("line", "area", "scatter"):
        try:
            x_positions = [float(x) for x in xv]
        except (ValueError, TypeError):
            x_positions = list(range(n))
    else:
        x_positions = list(range(n))

    # Dynamic figure size
    if chart_type in ("hbar",):
        fig_w = max(6, min(12, 5 + n * 0.15))
    elif chart_type in ("bar", "stacked_bar"):
        fig_w = max(6, min(14, 5 + n * 0.2))
    else:
        fig_w = 8.5
    fig_h = max(4, fig_w * 0.55)

    # Save old rcParams, set CJK font
    _old_sans = plt.rcParams.get('font.sans-serif', None)
    _old_family = plt.rcParams.get('font.family', None)
    if _FONT_NAME != 'sans-serif':
        plt.rcParams['font.sans-serif'] = [_FONT_NAME, 'DejaVu Sans', 'Arial']
        plt.rcParams['font.family'] = 'sans-serif'

    try:
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.set_facecolor("#fefefd")
        ax.tick_params(colors="#666", labelsize=8, pad=4)

        # ---- Chart rendering ----
        if chart_type == "bar" or chart_type == "hbar":
            bar_colors = [cs[i % len(cs)] for i in range(n)]
            if chart_type == "hbar":
                ax.barh(range(n), yv, color=bar_colors, alpha=0.88,
                         edgecolor=t["edge"], linewidth=0.5, height=0.65)
                _smart_x_labels(ax, xv, n, fp, is_horizontal=True)
                ax.invert_yaxis()
                ax.set_xlabel(y_label or y_col, fontsize=9, fontproperties=fp)
            else:
                ax.bar(range(n), yv, color=bar_colors, alpha=0.88,
                        edgecolor=t["edge"], linewidth=0.5, width=0.65)
                _smart_x_labels(ax, xv, n, fp)
                ax.set_ylabel(y_label or y_col, fontsize=9, fontproperties=fp)
                if x_label:
                    ax.set_xlabel(x_label, fontsize=9, fontproperties=fp)

        elif chart_type == "stacked_bar":
            bottom = np.zeros(n)
            for si in range(min(4, n)):
                vals = [max(0, yv[i] / min(4, n)) for i in range(n)]
                ax.bar(range(n), vals, bottom=bottom, color=cs[si % len(cs)],
                        alpha=0.82, edgecolor=t["edge"], linewidth=0.5, width=0.6)
                bottom += vals
            _smart_x_labels(ax, xv, n, fp)
            ax.set_ylabel(y_label or y_col, fontsize=9, fontproperties=fp)
            ax.legend([f"组{i + 1}" for i in range(min(4, n))], fontsize=8, loc="upper right", prop=fp)

        elif chart_type == "line":
            ax.plot(x_positions, yv, color=cs[0], linewidth=2.2, marker="o",
                    markersize=6, markerfacecolor="#fff", markeredgecolor=cs[0], markeredgewidth=1.5)
            ax.fill_between(x_positions, yv, alpha=0.08, color=cs[0])
            if xf:
                ax.set_xlabel(x_label or x_col, fontsize=9, fontproperties=fp)
            else:
                _smart_x_labels(ax, xv, n, fp)
            ax.set_ylabel(y_label or y_col, fontsize=9, fontproperties=fp)
            if x_label:
                ax.set_xlabel(x_label, fontsize=9, fontproperties=fp)

        elif chart_type == "area":
            ax.fill_between(x_positions, yv, alpha=0.25, color=cs[0])
            ax.plot(x_positions, yv, color=cs[0], linewidth=2, marker="o",
                    markersize=5, markerfacecolor=cs[1])
            if xf:
                ax.set_xlabel(x_label or x_col, fontsize=9, fontproperties=fp)
            else:
                _smart_x_labels(ax, xv, n, fp)
            ax.set_ylabel(y_label or y_col, fontsize=9, fontproperties=fp)

        elif chart_type == "scatter":
            sizes = [max(20, min(180, v / (max(yv) + 0.001) * 150)) for v in yv]
            scatter_colors = [cs[i % len(cs)] for i in range(n)]
            ax.scatter(x_positions, yv, c=scatter_colors, alpha=0.75, s=sizes, edgecolors=t["edge"], linewidth=0.3)
            if xf:
                ax.set_xlabel(x_label or x_col, fontsize=9, fontproperties=fp)
            else:
                _smart_x_labels(ax, xv, n, fp)
            ax.set_ylabel(y_label or y_col, fontsize=9, fontproperties=fp)

        elif chart_type == "pie" or chart_type == "donut":
            pie_colors = cs[:n]
            wedges, texts, autotexts = ax.pie(
                yv, labels=xv[:n], autopct="%1.1f%%", colors=pie_colors,
                startangle=140, pctdistance=0.78 if chart_type == "donut" else 0.6
            )
            for at in autotexts:
                at.set_fontsize(8)
                at.set_fontproperties(fp)
            for txt in texts:
                txt.set_fontsize(8)
                txt.set_fontproperties(fp)
            if chart_type == "donut":
                centre = plt.Circle((0, 0), 0.55, fc="#fefefd", edgecolor=t["edge"], linewidth=0.5)
                ax.add_artist(centre)

        elif chart_type == "histogram":
            bins = min(20, max(5, int(n ** 0.5) + 1))
            ax.hist(yv, bins=bins, color=cs[0], alpha=0.82, edgecolor=t["edge"], linewidth=0.5)
            ax.set_xlabel(y_label or y_col, fontsize=9, fontproperties=fp)
            ax.set_ylabel("频数", fontsize=9, fontproperties=fp)

        elif chart_type == "box":
            bp = ax.boxplot(yv, patch_artist=True, vert=True, widths=0.5)
            for patch in bp['boxes']:
                patch.set_facecolor(cs[0])
                patch.set_alpha(0.7)
            ax.set_xticklabels([y_col], fontsize=9, fontproperties=fp)
            ax.set_ylabel("值", fontsize=9, fontproperties=fp)

        elif chart_type == "radar":
            angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
            yv_norm = yv + yv[:1]
            angles += angles[:1]
            ax = fig.add_subplot(111, polar=True)
            ax.set_facecolor("#fefefd")
            ax.fill(angles, yv_norm, alpha=0.15, color=cs[0])
            ax.plot(angles, yv_norm, color=cs[0], linewidth=2, marker="o", markersize=5)
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(xv, fontsize=8, fontproperties=fp)
            ax.set_yticklabels([])

        else:
            ax.bar(range(n), yv, color=[cs[i % len(cs)] for i in range(n)],
                    alpha=0.88, edgecolor=t["edge"], linewidth=0.5, width=0.65)
            _smart_x_labels(ax, xv, n, fp)
            ax.set_ylabel(y_label or y_col, fontsize=9, fontproperties=fp)

        # ---- Common styling ----
        final_title = title or f"{y_col} by {x_col}"
        ax.set_title(final_title, fontsize=13, fontweight="bold", color="#333", pad=12, fontproperties=fp)

        if t.get("grid") and chart_type not in ("pie", "donut", "radar", "box"):
            ax.grid(axis="y", alpha=0.25, color="#999", linewidth=0.4)
            ax.set_axisbelow(True)

        # Clean Y-axis number formatting
        if chart_type not in ("pie", "donut", "radar"):
            from matplotlib.ticker import FuncFormatter
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _fmt_num(v)))

        # Style spines
        for spine in ax.spines.values():
            spine.set_edgecolor("#ddd")
            spine.set_linewidth(0.5)

        fig.patch.set_facecolor('white')
        fig.tight_layout(pad=2.5)
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=200, bbox_inches="tight", facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    finally:
        # Restore previous rcParams
        if _old_sans is not None:
            plt.rcParams['font.sans-serif'] = _old_sans
        if _old_family is not None:
            plt.rcParams['font.family'] = _old_family


def _build_data_summary(data_info: dict) -> str:
    """Build a text summary of the data for AI analysis."""
    columns = data_info.get("columns", [])
    rows = data_info.get("rows", [])
    types = data_info.get("types", {})
    total = data_info.get("total_rows", len(rows))
    all_rows = data_info.get("all_rows", rows)

    # Compute full stats from all_rows if available
    stats = compute_stats({"columns": columns, "rows": all_rows, "types": types, "total_rows": total})

    lines = [f"数据集: {len(columns)} 列, {total} 行\n"]
    lines.append("## 字段")
    for col in columns:
        col_type = types.get(col, "text")
        lines.append(f"- {col} ({col_type})")

    lines.append("\n## 统计摘要 (完整统计)")
    for col in columns:
        s = stats.get(col, {})
        if not s or s.get("type") == "empty":
            lines.append(f"- {col}: 空列, 无数据")
            continue
        if s["type"] == "numeric":
            out_info = ""
            if s.get("outliers", 0) > 0:
                out_vals = ", ".join(str(v) for v in s.get("outlier_values", [])[:3])
                out_info = f", 异常值={s['outliers']}个 (IQR={s['iqr_outliers']}, Z-score={s['z_outliers']}) [{out_vals}]"
            lines.append(
                f"- {col} (数值): n={s['count']}, 缺失={s['missing']}, "
                f"min={s['min']}, Q1={s['q1']}, 中位数={s['median']}, Q3={s['q3']}, max={s['max']}, "
                f"均值={s['mean']}, 标准差={s['std']}, CV={s['cv']}{out_info}"
            )
        else:
            tops = ", ".join(str(v) for v in s.get("top_values", [])[:3])
            lines.append(f"- {col} (文本): n={s['count']}, 缺失={s['missing']}, "
                         f"唯一值={s['unique']}个, Top: {tops}")

    lines.append(f"\n## 数据样本 (前20行)")
    lines.append(" | ".join(columns))
    for row in rows[:20]:
        cells = [str(row[ci]) if ci < len(row) else "" for ci in range(len(columns))]
        lines.append(" | ".join(cells))

    return "\n".join(lines)


DATA_ANALYSIS_PROMPT = """You are an expert data analyst and statistician. Review the dataset statistics below and produce a thorough, actionable analysis.

**Your task:**
1. Write a 2-3 sentence overview — identify the dataset's nature, key patterns, and overall data quality
2. Evaluate EACH column individually — flag data quality issues, unusual distributions, outliers, high variability, or other concerns. Be quantitative where possible (e.g., "CV of 0.70 indicates very high dispersion, max value is 2.8σ from mean")
3. Provide 2-4 specific, actionable suggestions for further analysis or data cleaning
4. Design an optimal visualization — choose chart type and axis columns that best reveal patterns in the data

**Important analysis guidelines:**
- Check coefficient of variation (CV = std/mean): CV > 0.3 = high dispersion, CV > 0.5 = very high, may indicate subgroups or outliers
- For columns with outliers: suggest whether they should be investigated, removed, or kept
- Identify columns that may correlate with each other
- If data appears to have subgroups (bimodal distribution, clusters), mention this
- The visualization should highlight the most interesting pattern — do NOT just plot raw values. Consider: aggregation by category, binning, ranking, or derived metrics

**Return ONLY valid JSON (no markdown fences):**
{
  "overview": "2-3 sentence summary in the same language as column names",
  "evaluations": {
    "col_name": "1-2 sentences assessing this column's quality, distribution, notable issues. Mention CV, outlier count, or other stats where relevant.",
    ...
  },
  "suggestions": ["specific actionable suggestion 1", "suggestion 2", ...],
  "chart": {
    "type": "bar|hbar|line|area|scatter|pie|donut|histogram|box|stacked_bar|radar",
    "x_col": "column name for x-axis",
    "y_col": "column name for y-axis",
    "title": "descriptive chart title",
    "reason": "1 sentence explaining what insight this chart reveals"
  }
}

- Write ALL text in the same language as the column names
- Include EVERY column in evaluations
- Return ONLY the JSON, no extra text"""


async def analyze_data_stream(data_info: dict, provider: str | None = None,
                               user_config=None):
    """Stream AI analysis of uploaded data."""
    from app.services.ai.factory import get_ai_provider, AIProviderConfig

    summary = _build_data_summary(data_info)
    ai = get_ai_provider(name=provider, user_config=user_config)

    async for text in ai.chat_stream(
        system_prompt=DATA_ANALYSIS_PROMPT,
        messages=[{"role": "user", "content": summary}],
    ):
        yield text


CHART_RECOMMEND_PROMPT = """You are a data visualization expert. Based on the dataset statistics below, recommend the single best chart to visualize this data.

Choose chart type from: bar, hbar, line, area, scatter, pie, donut, histogram, box, stacked_bar, radar

Rules:
- bar/hbar: compare values across categories (≤12 categories)
- line/area: show trends over time or ordered sequence
- scatter: show relationship between two numeric variables
- pie/donut: show proportions (≤7 categories)
- histogram: show distribution of a single numeric variable
- box: show statistical distribution with quartiles and outliers
- radar: compare multiple metrics across few items

The x_col MUST be a column that exists in the data. The y_col MUST be a numeric column.
Title should be descriptive and in the same language as the column names.

Return ONLY valid JSON:
{"type": "bar", "x_col": "column_name", "y_col": "column_name", "title": "Chart title", "reason": "Why this chart works best"}"""


async def recommend_chart_ai(data_info: dict, user_config=None) -> dict | None:
    """Use AI to recommend the best chart for the data. Returns None on failure."""
    from app.services.ai.factory import get_ai_provider
    import logging
    _log = logging.getLogger(__name__)
    try:
        summary = _build_data_summary(data_info)
        ai = get_ai_provider(user_config=user_config)
        full = ""
        async for text in ai.chat_stream(
            system_prompt=CHART_RECOMMEND_PROMPT,
            messages=[{"role": "user", "content": summary}],
        ):
            full += text
        # Parse JSON from response
        import json as _json
        full = full.strip()
        if full.startswith("```"):
            full = full.split("\n", 1)[1].rsplit("```", 1)[0]
        result = _json.loads(full)
        _log.info(f"AI chart recommendation: {result}")
        return result
    except Exception as e:
        _log.warning(f"Chart recommendation failed: {e}")
        return None
