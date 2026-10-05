@echo off
rem ============================================================================
rem  instalar_python.cmd  ·  Windows
rem
rem  Instala Python (version elegible), lo anade al PATH del usuario y
rem  comprueba que funciona ejecutando el conversor de skins de Actions & Stuff.
rem
rem  COMO SE USA
rem   1. Doble clic en este archivo.
rem   2. Espera a que termine (descarga unos 25 MB la primera vez).
rem   3. Abre una consola NUEVA y ya podras usar "python" y "py" en cualquier carpeta.
rem
rem  EXTRA
rem   · Arrastra un PNG de skin y sueltalo encima de este .cmd: lo convierte.
rem   · Otra version:  instalar_python.cmd 3.13.5      (o edita la linea PY_VER)
rem   · En Windows 7 la ultima que funciona es la 3.8.x.
rem ============================================================================

setlocal EnableExtensions
title Instalar Python para el conversor de Actions & Stuff

set "SOLTADO=%~1"
set "PY_VER=3.12.10"
set "PY_MAJ=3.12"
set "PY_DIR_NAME=Python312"

rem -- si el primer argumento parece una version (por ejemplo 3.13.5), se usa esa
set "ES_VER="
for /f "tokens=1,2,3 delims=." %%a in ("%SOLTADO%") do if not "%%c"=="" set "ES_VER=%%a.%%b.%%c"
if "%ES_VER:~0,2%"=="3." (
  set "PY_VER=%ES_VER%"
  set "PY_MAJ="
  set "PY_DIR_NAME="
  set "SOLTADO="
)
if defined PY_VER if not defined PY_MAJ for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do set "PY_MAJ=%%a.%%b"
if defined PY_VER if not defined PY_DIR_NAME for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do set "PY_DIR_NAME=Python%%a%%b"

echo.
echo  ============================================================
echo   Python %PY_VER% para el conversor de skins de A^&S
echo  ============================================================
echo.

rem ------------------------------------------------------- 1) ya esta instalado?
set "PY="
call :probar py -3
if not defined PY call :probar python
if not defined PY call :probar python3
if defined PY goto :ya_instalado

rem ------------------------------------------------------------- 2) descargar
echo  [1/3] Python no esta instalado (o no esta en el PATH). Se descarga.
set "ARQ=amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="x86" if not defined PROCESSOR_ARCHITEW6432 set "ARQ="
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARQ=arm64"
set "URL=https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-%ARQ%.exe"
set "INST=%TEMP%\python-%PY_VER%-instalador.exe"
echo        %URL%
echo.
if exist "%INST%" del "%INST%" >nul 2>&1

where curl >nul 2>&1
if not errorlevel 1 (
  curl -L --fail --silent --show-error -o "%INST%" "%URL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%URL%' -OutFile '%INST%' -UseBasicParsing } catch { exit 1 }"
)
if not exist "%INST%" goto :sin_descarga
for %%A in ("%INST%") do if %%~zA LSS 1000000 goto :sin_descarga
echo        Descargado en %INST%
echo.

rem -------------------------------------------------------------- 3) instalar
echo  [2/3] Instalando en tu usuario (no hace falta ser administrador):
echo        - se anade al PATH del usuario  (PrependPath=1)
echo        - se instala pip y el lanzador py  (Include_launcher=1)
echo        - instalacion silenciosa, sin ventanas
echo.
start /wait "" "%INST%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1 Include_test=0 Include_doc=0 SimpleInstall=1
if errorlevel 1 goto :fallo_instalador

rem -- recargar el PATH de esta consola con lo que acaba de escribir el instalador
for /f "tokens=2,*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "UPATH=%%b"
if defined UPATH set "PATH=%UPATH%;%PATH%"

rem ------------------------------------------------------------- 4) comprobar
echo  [3/3] Comprobando...
set "PY="
call :probar py -3
if not defined PY call :probar python
if not defined PY call :probar "%LOCALAPPDATA%\Programs\Python\%PY_DIR_NAME%\python.exe"
if not defined PY goto :instalado_sin_path

echo.
echo  ------------------------------------------------------------
echo   LISTO: Python %PYV% instalado y en el PATH
echo  ------------------------------------------------------------
echo.
echo   Abre una consola NUEVA (la que ya tenias abierta no lo vera) y prueba:
echo.
echo       python --version
echo       py --version
echo.
call :probar_conversor
call :recordatorio
echo.
pause
exit /b 0

rem ============================================================================
rem  Etiquetas
rem ============================================================================

:ya_instalado
echo  Python ya estaba instalado: %PYV%
echo        se usara "%PY%"
echo.
call :probar_conversor
call :recordatorio
echo.
pause
exit /b 0

:instalado_sin_path
echo.
echo   Python se ha instalado, pero esta consola todavia no lo ve.
echo   ABRE UNA CONSOLA NUEVA y escribe:   python --version
echo   Ruta de instalacion: %LOCALAPPDATA%\Programs\Python\%PY_DIR_NAME%\
echo.
pause
exit /b 0

:sin_descarga
echo.
echo   No he podido descargar el instalador de Python.
echo   Revisa la conexion, o descargalo a mano desde:
echo       %URL%
echo   y al instalarlo MARCA la casilla "Add python.exe to PATH".
echo.
pause
exit /b 1

:fallo_instalador
echo.
echo   El instalador no ha terminado bien.
echo   Prueba a mano: abre %INST% y marca "Add python.exe to PATH".
echo.
pause
exit /b 1

rem -------------------------------------------------------------- subrutinas

:probar
rem  %* = comando a probar (por ejemplo: py -3). Si funciona, deja PY y PYV.
if "%~1"=="" goto :eof
set "PYV="
for /f "delims=" %%v in ('%* -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYV=%%v"
if not defined PYV goto :eof
echo        Encontrado: Python %PYV%   usando: %*
set "PY=%*"
goto :eof

:probar_conversor
if not exist "%~dp0conversor_actions_stuff.py" goto :sin_conversor
"%PY%" "%~dp0conversor_actions_stuff.py" --version >nul 2>&1
if errorlevel 1 goto :conversor_falla
echo   Prueba real del conversor (lista de tipos de la plantilla oficial):
"%PY%" "%~dp0conversor_actions_stuff.py" --estilos
echo.
if not defined SOLTADO goto :eof
if not exist "%SOLTADO%" goto :eof
echo   Convirtiendo el archivo que has soltado: %SOLTADO%
echo.
"%PY%" "%~dp0conversor_actions_stuff.py" "%SOLTADO%" --info
goto :eof

:sin_conversor
echo   Aviso: no encuentro conversor_actions_stuff.py en esta carpeta.
echo   Ponlo al lado de este .cmd y vuelve a ejecutarlo para probarlo.
echo   Carpeta: %~dp0
echo.
goto :eof

:conversor_falla
echo   Aviso: el conversor no ha arrancado. Prueba a mano:
echo       "%PY%" conversor_actions_stuff.py --help
echo.
goto :eof

:recordatorio
echo   ------------------------------------------------------------
echo   Como se usa el conversor:
echo.
echo       python conversor_actions_stuff.py mi_skin.png
echo       python conversor_actions_stuff.py mi_skin.png --info
echo       python conversor_actions_stuff.py *.png -d salida --pack mis_skins.mcpack
echo.
echo   Si en el juego no pestanea la skin:
echo      - Actions ^& Stuff 1.5 o superior
echo      - Ajustes - Recursos - Actions ^& Stuff - engranaje - "Enable Expressions" ACTIVADO
echo      - Vibrant Visuals DESACTIVADO
echo      - la skin debe ser una skin clasica subida (no del creador de personajes)
echo   ------------------------------------------------------------
goto :eof
