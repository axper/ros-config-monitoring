ros-config-monitoring
=====================

Monitors MikroTik RouterOS machines for configuration changes. Diffs of config changes are stored in a file for each RouterOS user.

Later from each user's diff file can be generated PDF report using LaTeX.

Everyting is backed up in `backups` directory.

Requirements
============

1. Python 2
2. `pip install paramiko`
3. LaTeX with `listings` package

Usage
=====

Monitoring
----------

To start monitoring, run `python ./watch_config.py`. Provide the router's IP, username and password for SSH connection. Multiple machines can be monitoried at once.

When connecting first time, the program will save the whole configuration locally. User will be notified about this, ignore this output and continue the IP/username/password input for the next machine (if desired).

If all machines are connected, simply ignore the "Username:" prompt.

When connected, it will listen to configuration changes and will append them to a diff file for each user.

Generating Reports
------------------

* First, make sure you have working LaTeX installation.
* Customize the report text in `report.tex`.
* Edit `users.xml` and provide names for users.
* To generate report for existing diffs, run `python ./create_reports.py`.
* For each user's diff, a PDF file will be created and opened in default PDF viewer.
* The user's diff file will be moved to backups directory and new changes will be concatenated to a new diff file.

