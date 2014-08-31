@echo off
python C:\Python34\Scripts\cxfreeze --base-name=Win32GUI ros_config_monitoring.py --target-dir "RouterOS Configuration Monitoring"
copy router_icon.png dist
copy users.xml dist
copy report.tex dist
echo "The executable and all necessary files was put in dist folder."
echo "You only have to install Miktex or extract the Miktex portable installer into miktex_portable directory and put that directory in dist"
pause
