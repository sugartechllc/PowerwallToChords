import pypowerwall
import time

#pypowerwall.set_debug(True)
host = password = ""
email='<Tesla account email>'
timezone = "America/Denver"

# Connect to Tesla Cloud Powerwall - auto_select mode (local, fleetapi, cloud)
pw = pypowerwall.Powerwall(host,password,email,timezone,auto_select=True)

# Some System Info
print("Site Name: %s - Firmware: %s - DIN: %s" % (pw.site_name(), pw.version(), pw.din()))
print("System Uptime: %s\n" % pw.uptime())

while True:
    print({**{'time':pw.grid(verbose=True)['last_communication_time']}, **pw.power(), **{'level':pw.level()}})
    time.sleep(6)
