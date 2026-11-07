@echo off
setlocal
REM ============================================================
REM  build_exe.bat - build Local Translator (ProInventive, by Lungpee)
REM   full : LocalTranslator.spec      -> dist\LocalTranslator        (own machine; voice ask included)
REM   lite : LocalTranslator-lite.spec -> dist_lite\LocalTranslator   (distribution; no voice ask)
REM  Builds into build_dist\ first, then copies over dist\ so PyInstaller never wipes
REM  dist\LocalTranslator (it holds settings.json / history.json / installer files).
REM  Then make_setup_zip.py -> LocalTranslator-setup.zip (lite) + LocalTranslator-full.zip
REM  Usage: build_exe.bat [full|lite|all]   (default all)
REM ============================================================
cd /d "%~dp0"
set "WHAT=%~1"
if "%WHAT%"=="" set "WHAT=all"
taskkill /f /im LocalTranslator.exe >nul 2>&1

if /i "%WHAT%"=="lite" goto lite
echo === FULL build ===
if exist build_dist rd /s /q build_dist
py -m PyInstaller LocalTranslator.spec --noconfirm --distpath build_dist --workpath build || goto fail
robocopy build_dist\LocalTranslator\_internal dist\LocalTranslator\_internal /MIR /NFL /NDL /NJH /NJS /R:3 /W:2
copy /y build_dist\LocalTranslator\LocalTranslator.exe dist\LocalTranslator\LocalTranslator.exe >nul || goto fail
rd /s /q build_dist
echo     [OK] dist\LocalTranslator
if /i "%WHAT%"=="full" goto zip

:lite
echo === LITE build (distribution, no voice ask) ===
if exist dist_lite rd /s /q dist_lite
py -m PyInstaller LocalTranslator-lite.spec --noconfirm --distpath dist_lite --workpath build_lite || goto fail
for %%F in (Install-LocalTranslator.bat README-install.txt README-translator.md glossary.txt translator.ico translator.png) do copy /y "dist\LocalTranslator\%%F" "dist_lite\LocalTranslator\%%F" >nul
echo     [OK] dist_lite\LocalTranslator

:zip
py make_setup_zip.py || goto fail
echo.
echo Done.
exit /b 0
:fail
echo.
echo [!] build failed
exit /b 1
