import pypowerwall
import json
import time
import logging
import argparse
import sys
import pychords.tochords as tochords

#pypowerwall.set_debug(True)
host = password = ""
email='tickranch@gmail.com'
timezone = "America/Denver"

def main(config_file:dict)->None:

    # Startup chords sender
    tochords.startSender()

    # Load configuration
    logging.info(f"Starting Powerwall to Chords with {config_file}")
    config = json.loads(open(config_file).read())
    host = ''
    password = ''
    email = config['tesla']['owner_email']
    timezone = config['tesla']['timezone']

    # Connect to Tesla Cloud Powerwall - auto_select mode (local, fleetapi, cloud)
    pw = pypowerwall.Powerwall(host, password, email, timezone, auto_select=True)

    # Some System Info
    print("Site Name: %s - Firmware: %s - DIN: %s" % (pw.site_name(), pw.version(), pw.din()))
    print("System Uptime: %s\n" % pw.uptime())

    while True:
        vars = {}
        vars['at'] = pw.grid(verbose=True)['last_communication_time']
        power = pw.power()
        vars['grid'] = power['site']
        vars['solar'] = power['solar']
        vars['battery'] = power['battery']
        vars['load'] = power['load']
        vars['level'] = pw.level()

        chords_record = {}
        chords_record["inst_id"] = config['chords']["instrument_id"]
        chords_record["api_email"] = config['chords']["api_email"]
        chords_record["api_key"] = config['chords']["api_key"]
        chords_record["vars"] = vars
        uri = tochords.buildURI(config['chords']["chords_host"], chords_record)
        logging.info(f"Submitting: {uri}")
        max_queue_length = 31*60*24
        tochords.submitURI(uri, max_queue_length)

        #print({**{'time':pw.grid(verbose=True)['last_communication_time']}, **pw.power(), **{'level':pw.level()}})
        time.sleep(60)

if __name__ == '__main__':

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", help="Path to json configuration file to use.", required=True)
    parser.add_argument(
        "--debug", help="Enable debug logging",
        action="store_true")
    args = parser.parse_args()

    # Configure logging
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(stream=sys.stdout, level=level, format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.debug("Debug logging enabled")

    # Run main
    main(args.config)
