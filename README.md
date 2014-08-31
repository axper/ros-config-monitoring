ros-config-monitoring
=====================

Tracks configuration changes in MikroTik RouterOS machines.
When a configuration change is made, the diff of that change is stored in a file.
Each RouterOS user has has his own file which contains detailed information about the changes they have made.
Later on from each user's diff file a PDF report can be generated.

Features
--------

* Winbox-like gui
* Automatically reconnects when the router is rebooted
* Monitor multiple routers at once
* Every file is automatically backed up
* PDF report generation for each user's changes
* Works on both Linux and Windows
* Logs to both the main window and `ros_config_monitoring_log.txt` file
* Minimize to tray by clicking on "router" icon in tray

Building on Windows
===================

1. Download/Install the latest version of Python 3. During installation enable the "Add python.exe to Path" feature
https://www.python.org/downloads/
2. Download/Install cx\_Freeze from: (The pip/PyPi version fails for me)
http://www.lfd.uci.edu/~gohlke/pythonlibs/#cx\_freeze
3. Download/Install pycrypto from:
https://github.com/axper/python3-pycrypto-windows-installer
Or, if using older version of Python, install pycrypto from:
http://www.voidspace.org.uk/python/modules.shtml#pycrypto
4. Open cmd and run:

    pip install paramiko

5. Download/Install PyQt5 from:
http://www.riverbankcomputing.co.uk/software/pyqt/download5
6. Run the `build.cmd` script

The `build.cmd` script will create a directory `RouterOS Configuration Monitoring` which will contain all the necessary files.

PDF generation on Windows
-------------------------

If you want to also generate PDF reports:

1. Open the `users.xml` file in your favourite text editor and add the usernames and real names of all your router users. Follow the schema.
2. Download Miktex portable installer from: (click "Other downloads" at the bottom)
http://miktex.org/download
3. Install/Extract Miktex portable into a new directory called `miktex_portable`
4. Move the `miktex_portable` directory to `RouterOS Configuration Monitoring` directory as a subdirectory

The first time only when generating PDF it will take quite a long time as Miktex will be downloading necessary LaTeX packages from the internet. Miktex will promt to download necessary packages, for convenience uncheck the "Always show this dialog before installing packages" box at the bottom and click "Install".

Usage
=====

To start monitoring, first edit the `users.xml` file and provide names of all router users. If a user isn't specified, a report won't be generated for him/her!
Run `ros_config_monitoring.exe` and connect to the router(s).
The program will start listening for configuration changes in the memory log of the router.
When a change is made, it will be appended to `<username>_diff.txt` file.

To minimize the program to tray, click on the "router" icon in the system tray.

Generating PDF reports
----------------------

When you click "Generate PDF Reports", the program will create PDF for each user specified in `users.txt` it finds a diff file. The resulting PDF will be opened in the system's default PDF viewer for your convenience.

If you know some LaTeX, you can customize the report text and style in `report.tex`.

Troubleshooting
===============

* If the program crashes, look for the `ros_config_monitoring_log.txt` file. Open it and try to figure out what went wrong. If you can't, send that file to me with your system details and the exact steps that led to crash.
* For the program to work, the configuration logging of the `info` topic to memory must be enabled in `/system logging` (which is the default).
Be wary of users who might disable this and change whatever they like without this program detecting!
* A PDF viewer must be present on the system. I recommend Sumatra PDF, a very small and very fast PDF viewer:
http://blog.kowalczyk.info/software/sumatrapdf/download-free-pdf-viewer.html

How it works
============

* This program monitors specifically which RouterOS user makes changes in configuration by watching the router log by `/log print follow-only` command.
* When connecting first time, the program will save the whole configuration locally. User will be notified about this, ignore this output and continue the IP/username/password input for the next machine (if desired).
* When it detects a configuration change in the router log, it connects again, fetches new configuration, diffs the old and new configuration and appends the diff to the diff file of the user who made the configuration change.
* When configuration was changes while the program wasn't monitoring, the changes will be written for the user called `UNKNOWN`.

