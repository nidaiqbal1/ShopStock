# PyInstaller spec - builds dist/ShopStock/ShopStock(.exe).  Use build_windows.bat on Windows.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("templates", "templates"), ("static", "static"), ("README.md", "."), ("docs", "docs")]
binaries, hiddenimports = [], ["waitress", "openpyxl", "dotenv"] + collect_submodules("routes") + collect_submodules("services")
for pkg in ("reportlab", "openpyxl", "arabic_reshaper", "bidi"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(["run_shopstock.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL.ImageTk"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ShopStock", console=True, icon="static/shopstock.ico" if __import__("os").path.exists("static/shopstock.ico") else None)
coll = COLLECT(exe, a.binaries, a.datas, name="ShopStock")
