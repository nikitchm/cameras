@echo off
rem Navigate to the directory containing this script, then go up one level (to 'repos')
pushd "%~dp0..\ "
conda run -n cameras python -m cameras --grabbers=pycapture2 --width=2048 --height=2048 --mode=0 --fps=90 --offsetX=0 --offsetY=0
popd