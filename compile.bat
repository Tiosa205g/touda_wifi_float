@echo off
nuitka --lto=no --jobs=5 --onefile --mingw64 --standalone --output-dir="output" --windows-console-mode=disable --windows-icon-from-ico=res/ico/favicon.ico --enable-plugin=pyside6 --include-qt-plugins=sensible,styles --include-data-files=res/ico/*.ico=res/ico/ main.py
pause