#!/usr/bin/env python3
"""Check logs after restart"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.lib.pi_ssh import connect as pi_connect


ssh = pi_connect(host="192.168.1.23", user="pi", timeout=10)
stdin, stdout, stderr = ssh.exec_command("journalctl -u mx5-display.service --since '20 seconds ago' --no-pager | tail -30")
print(stdout.read().decode())

ssh.close()
