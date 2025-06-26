This is the frame grabber for the FLIR cameras implemented via the pycapture2 interface provided by the vendor.


### Installation of the necessary drivers and packages

* Download `FlyCapture_2xxx.exe` and `PyCapture2xxx.zip` from here (other downloads might work as well, but they aren't tested):
https://www.teledynevisionsolutions.com/support/support-center/software-firmware-downloads/iis/flycapture-sdk/flycapture2-download-files

* Install `FlyCapture_2xxx.exe` (full installation is the safest in terms of making sure all of the necessary features are present)

* from `PyCapture2xxx.zip` we need only `python3.6` version
    * Deselect "Python xx from registry (if present)
    * Click on the pictogram next to "Python from another location" and select: "Entire feature will be installed on a local drive". In the entry field below, select a folder to hold the installation files. However, if you want to install PyCapture2 in more than one location (e.g., different conda environments), choose a new empty folder, where you will be able to get back to in the future. Then, for whichever environment you want PyCapture2 to be present in, simply copy the content of the PyCapture2 folder into that environment folder (e.g., the head folder of the conda environment).
    * docs folder contain Readme file with instructions on installation, etc