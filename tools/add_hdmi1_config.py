import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.1.28', username='pi', password='Hopwood12', timeout=10)

# Add HDMI1 config for second HDMI port
config_lines = [
    '',
    '# HDMI1 config (second HDMI port - farthest from USB-C)',
    '[HDMI:1]',
    'hdmi_force_hotplug=1',
    'hdmi_drive=2',
    'hdmi_group=2',
    'hdmi_mode=87',
    'hdmi_cvt=800 480 60 6 0 0 0',
    '',
    '[all]',
]

for line in config_lines:
    cmd = f"echo '{line}' | sudo tee -a /boot/config.txt"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.read()  # wait for completion

# Verify
stdin, stdout, stderr = ssh.exec_command('tail -15 /boot/config.txt')
print('Config added:')
print(stdout.read().decode())

ssh.close()
print('Done! Reboot required for changes to take effect.')
