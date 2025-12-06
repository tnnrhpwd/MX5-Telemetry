Import("env")
import os

# Change source directory to src_slave for led_slave environment
project_dir = env["PROJECT_DIR"]
src_slave_dir = os.path.join(project_dir, "src_slave")

# Update the source directory
env.Replace(PROJECT_SRC_DIR=src_slave_dir)

# Clear and reset SRC_FILTER to include all files from src_slave
env.Replace(SRC_FILTER=["+<*>"])

print(f"✓ Using source directory: {src_slave_dir}")
