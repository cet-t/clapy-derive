@echo off
setlocal

echo [1/4] Running tests...
uv run pytest tests/ -q
if errorlevel 1 (
    echo Tests failed. Aborting.
    exit /b 1
)

echo [2/4] Cleaning dist/...
for %%f in (dist\*.whl dist\*.tar.gz) do del /f /q "%%f"

echo [3/4] Building...
uv build
if errorlevel 1 (
    echo Build failed. Aborting.
    exit /b 1
)

echo [4/4] Publishing...
for /f "tokens=2 delims==" %%t in ('findstr /b "password" "%USERPROFILE%\.pypirc"') do set TOKEN=%%t
set TOKEN=%TOKEN: =%
uv publish --username __token__ --password %TOKEN%
if errorlevel 1 (
    echo Publish failed.
    exit /b 1
)

echo Done.
endlocal
