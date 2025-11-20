# PowerShell script to run DCS Persistence main.py using Python Launcher

# Force working directory
Set-Location "D:\Persistencia"

# Run the script with Python 3.13 (explicit, safest)
# py -3.13 "D:\Persistencia\app\main.py"

# Alternatively, if 3.13 is default:
cd app
python .\main.py
