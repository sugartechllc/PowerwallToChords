import pypowerwall
import json
import time
import zoneinfo
import logging
import argparse
import sys
import os
import statistics
import datetime
import pychords.tochords as tochords


class Average:
    def __init__(self, time, value):
        self.time = time
        self.average = value
class Aggregater: 
    '''Collect and average a queue of values
    
    When an average is called for, the average over all values 
    is calculated, and then all values except for the last one in the
    queue is removed.
    '''
    def __init__(self, name:str)->None:
        self.name = name
        self.times = []
        self.values = []

    def add(self, value:float, time:str)->None:
        self.values.append(value)
        self.times.append(time)

    def avg(self)->list:
        avg = statistics.mean(self.values)
        time = statistics.mean(self.times)
        #print(f'>>> {self.name}')
        #print(self.values)
        #print(avg)
        self.values = [self.values[-1]]
        self.times = [self.times[-1]]
        return Average(time=time, value=avg)

class PW_Aggregator:
    def __init__(self, pw:pypowerwall.Powerwall):
        self.pw = pw
        self.time_aggregator = Aggregater('time')
        self.grid_aggregator = Aggregater('grid')
        self.solar_aggregator = Aggregater('solar')
        self.battery_aggregator = Aggregater('battery')
        self.load_aggregator = Aggregater('load')
        self.level_aggregator = Aggregater('level')

    def poll_pw(self):
        time = datetime.datetime.fromisoformat(self.pw.grid(verbose=True)['last_communication_time']).timestamp()
        self.time_aggregator.add(time=time, value=time)
        power = self.pw.power()
        self.grid_aggregator.add(time=time, value=power['site'])
        self.solar_aggregator.add(time=time, value=power['solar'])
        self.battery_aggregator.add(time=time, value=power['battery'])
        self.load_aggregator.add(time=time, value=power['load'])
        self.level_aggregator.add(time=time, value=self.pw.level())

    def avg(self):
        '''Return a dictionary of Average'''
        ret_val = {}
        ret_val['time'] = self.time_aggregator.avg().average
        ret_val['grid'] = self.grid_aggregator.avg().average
        ret_val['solar'] = self.solar_aggregator.avg().average
        ret_val['battery'] = self.battery_aggregator.avg().average
        ret_val['load'] = self.load_aggregator.avg().average
        ret_val['level'] = self.level_aggregator.avg().average
        return ret_val

def check_auth_files(pw_auth_path:str)->bool:
    # If the authorization files can't be found, return false
    ok = True
    auth_files = [f'{pw_auth_path}/.pypowerwall.auth', f'{pw_auth_path}/.pypowerwall.site']
    for f in auth_files:
        if not (os.path.isfile(f) and os.access(f, os.R_OK)):
            print(f'Unable to access tesla credentials file {f}')
            ok = False
    return ok

def main(config_file:dict)->None:

    # Startup chords sender
    tochords.startSender()

    # Load configuration
    logging.info(f"Starting powerwallToChords with {config_file}")
    config = json.loads(open(config_file).read())

    # Setting host and password to emty strings causes pypowerwall.Powerwall
    # to use the cloud api.
    host = ''
    password = ''
    poll_secs = config['powerwalltochords']['poll_secs']
    avg_count = config['powerwalltochords']['avg_count']
    pw_auth_path = os.path.expanduser(config['powerwalltochords']['pw_auth_path'])
    email = config['powerwalltochords']['owner_email']
    timezone = config['powerwalltochords']['timezone']
    debug = config['powerwalltochords']['debug']

    if not check_auth_files(pw_auth_path=pw_auth_path):
        sys.exit(1)

    # Connect to Tesla Cloud Powerwall - auto_select mode (local, fleetapi, cloud)
    pypowerwall.set_debug(debug)
    pw = pypowerwall.Powerwall(
        host=host, 
        password=password, 
        email=email, 
        timezone=timezone, 
        authpath=pw_auth_path, 
        auto_select=True)

    # Some System Info
    print(f'Site Name:{pw.site_name()} Firmware:{pw.version()} DIN:{pw.din()}')
    print(f'Polling: {poll_secs}s Avg count: {avg_count}')

    count = 0
    pw_aggregator = PW_Aggregator(pw)
    while True:
        pw_aggregator.poll_pw()
        count += 1

        if count == avg_count:
            averaged_values = pw_aggregator.avg()
            t = averaged_values['time']
            at = str(datetime.datetime.fromtimestamp(t, zoneinfo.ZoneInfo(timezone))).replace(' ','T')
            vars = {}
            vars['at'] = at
            vars['grid'] = averaged_values['grid']
            vars['solar'] = averaged_values['solar']
            vars['battery'] = averaged_values['battery']
            vars['load'] = averaged_values['load']
            vars['level'] = averaged_values['level']
            #print(vars)

            chords_record = {}
            chords_record["inst_id"] = config['chords']["instrument_id"]
            chords_record["api_email"] = config['chords']["api_email"]
            chords_record["api_key"] = config['chords']["api_key"]
            chords_record["vars"] = vars
            uri = tochords.buildURI(config['chords']["chords_host"], chords_record)
            logging.info(f"Submitting: {uri}")
            max_queue_length = 31*60*24
            tochords.submitURI(uri, max_queue_length)

            count = 0

        #print({**{'time':pw.grid(verbose=True)['last_communication_time']}, **pw.power(), **{'level':pw.level()}})
        time.sleep(poll_secs)

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
