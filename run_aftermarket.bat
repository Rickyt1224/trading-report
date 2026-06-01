@echo off
cd /d "G:\Trading Report"
py aftermarket_report.py >> "G:\Trading Report\logs\scheduler.log" 2>&1
