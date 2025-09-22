@echo off
if "%1"=="hide" goto start_software  
mshta vbscript:createobject("wscript.shell").run("""%~f0"" hide",0)(window.close)&&exit
:start_software
main.exe setting