@echo off
cd /d "G:\Trading Report"
py morning_report.py >> "G:\Trading Report\logs\scheduler.log" 2>&1
