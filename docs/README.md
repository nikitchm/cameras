This repository includes implementation of the grabbers for different cameras, as well as modules for visualization, recording and other processing of the grabbed images.

At the moment, the GUI implementation is done with PyQt5 due to the fact that the last provided pycapture2 implmenetation is for python 3.6, and I couldn't resolve the conda environment for python 3.6, PyQt6, pycapture2, and opencv at the same time.


Example for starting the camera GUI:
`path-to-pycapture2-environment/python.exe path-to-camera-gui/camera_gui.py --grabber pycapture2 --width=640 --height=640 --mode=0 --fps=90 --offsetX=500 --offsetY=500`