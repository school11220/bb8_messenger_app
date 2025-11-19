@echo off
echo INFO: Cleaning up previous build artifacts...
if exist "dist" ( rmdir /s /q dist )
if exist "build" ( rmdir /s /q build )
if exist "app.spec" ( del app.spec )
echo INFO: Cleanup complete.

echo INFO: Finding required Qiskit library paths...

:: Find the path for qiskit_aer
for /f "delims=" %%i in ('python -c "import os, qiskit_aer; print(os.path.dirname(qiskit_aer.__file__))"') do (
    set QISKIT_AER_PATH=%%i
)

:: Find the path for the core qiskit library
for /f "delims=" %%i in ('python -c "import os, qiskit; print(os.path.dirname(qiskit.__file__))"') do (
    set QISKIT_PATH=%%i
)

if not defined QISKIT_AER_PATH (
    echo ERROR: Could not determine path for qiskit_aer. Please ensure it is installed.
    exit /b 1
)
if not defined QISKIT_PATH (
    echo ERROR: Could not determine path for qiskit. Please ensure it is installed.
    exit /b 1
)

echo INFO: Found qiskit_aer at: %QISKIT_AER_PATH%
echo INFO: Found qiskit at: %QISKIT_PATH%
echo INFO: Building executable with PyInstaller...

:: Run PyInstaller, adding data from BOTH qiskit packages and the static web files.
pyinstaller --noconfirm app.py ^
--onefile ^
--add-data "%QISKIT_AER_PATH%;qiskit_aer" ^
--add-data "%QISKIT_PATH%;qiskit" ^
--add-data "static;static" ^
--hidden-import=engineio.async_drivers.threading

echo INFO: Build complete! Your application is in the 'dist' folder.

