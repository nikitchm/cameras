@echo off
rem Navigate to the directory containing this script, then go up one level (to 'repos')
pushd "%~dp0..\ "
conda run -n pycapture2 python -m cameras
popd