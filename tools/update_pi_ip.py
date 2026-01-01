#!/usr/bin/env python3
"""Update Pi IP address from 192.168.1.28 to 192.168.1.23 across all files"""

import os
import glob

# Define the search root
root = r"c:\Users\tanne\Documents\Github\MX5-Telemetry"

# Files to update
patterns = [
    "tools/*.py",
    "docs/**/*.md"
]

old_ip = "192.168.1.28"
new_ip = "192.168.1.23"

updated_files = []

for pattern in patterns:
    for filepath in glob.glob(os.path.join(root, pattern), recursive=True):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_ip in content:
                new_content = content.replace(old_ip, new_ip)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated_files.append(filepath)
                print(f"✓ Updated: {filepath}")
        except Exception as e:
            print(f"✗ Error updating {filepath}: {e}")

print(f"\n{len(updated_files)} files updated successfully")
