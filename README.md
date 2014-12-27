ros-config-monitoring
=====================

Tracks configuration changes in MikroTik RouterOS machine.
When a configuration change is made, an email is sent to an address specified in `config.txt`.

Features
--------

* Sends an email when config is changed
* Works on both Linux and Windows
* Configuration file is automatically backed up upon change
* Automatically reconnects when the router is rebooted

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

5. ...

Usage
=====

To start monitoring, first edit the `config.txt` file and set the `mail\_to`, `mail\_from` and `mail\_server` variables. If you prefer not to receive emails, set `enable_email = false` in `config.txt`.
Run `./ros\_config\_monitoring.py` and specify the ip/username/password.
The program will start listening for configuration changes by listening to the action `memory` log of the router.
When a change is made, the program will send an email to specified addresses. It will also append the change line to `log.txt` file (or other name specified in `config.txt`).
Leave the program/terminal running or background the process.
To exit the program, press `Ctrl+C`.

Troubleshooting
===============

* For the program to work, the configuration logging of the `info` topic to memory must be enabled in `/system logging` (which is the default).
Be wary of users who might disable this and make changes without this program detecting it!

How it works
============

* This program monitors specifically which RouterOS user makes changes in configuration by watching the router log using the `/log print follow-only` command.
* When connecting first time, the program will save the whole configuration locally. User will be notified about this, ignore this output and continue the IP/username/password input for the next machine (if desired).
* When it detects a configuration change in the router log, it connects again, fetches new configuration, diffs the old and new configuration and appends the diff to the diff file of the user who made the configuration change.
* When configuration was changes while the program wasn't monitoring, the changes will be written for the user called `UNKNOWN`.

