#!/usr/bin/env python3
"""Deep diagnostic - check where Python is loading telemetry_data from"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


import time

ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
print("Stopping service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl stop mx5-display")
stdout.read()
time.sleep(2)

print("Finding telemetry_data module locations...")
stdin, stdout, stderr = ssh.exec_command("python3 -c \"import sys; sys.path.insert(0, '/home/pi/MX5-Telemetry/pi/ui/src'); from telemetry_data import TelemetryData; import inspect; print('File:', inspect.getfile(TelemetryData)); t = TelemetryData(); print('Has oil_status:', hasattr(t, 'oil_status')); print('Fields:', [f for f in dir(t) if 'oil' in f.lower()])\"")
result = stdout.read().decode()
error = stderr.read().decode()
print("STDOUT:", result)
if error:
    print("STDERR:", error)

print("\nRestarting service...")
stdin, stdout, stderr = ssh.exec_command("sudo systemctl start mx5-display")
stdout.read()

ssh.close()
