from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import json
from logging.config import dictConfig


data_folder = 'data'


dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})



app = Flask(__name__, static_url_path='/static', static_folder=data_folder, template_folder='../templates')
logger = app.logger


main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)
user_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="users", autocommit=True)


beacons = {}
with open(os.path.join(data_folder, 'beacons.json'), 'r') as f:
    beacons_file = json.load(f)
    for mac_address in beacons_file:
        beacons[mac_address.upper()] = {
            'mac_address': mac_address.upper(),
            **beacons_file[mac_address]
        }


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Methods']='*'
    response.headers['Access-Control-Allow-Origin']='*'
    response.headers['Vary']='Origin'
    return response


@app.route("/")
def hello_world():
    return render_template("index.html", title = 'App')



@app.route("/send_scan", methods=['POST'])
def send_scan():
    if request.method == 'POST':
        ip_address = request.remote_addr
        data = request.json
        logger.info("scans from {}: {}".format(ip_address, data))
        mac_addresses = data.get('mac', '').upper().split(',')
        signal_strengths = data.get('ss', '').split(',')

        # NAMES IS NOT ALWAYS PROVIDED; THE LIST MAY BE OF DIFFERENT LENGTH
        names = data.get('n', '').split(',')

        scans = []

        for mac_address, signal_strength, name in zip(mac_addresses, signal_strengths, names):
            if not mac_address:
                continue
            if mac_address not in beacons:
                continue
            scans.append({
                'mac_address': mac_address,
                'signal_strength': signal_strength,
                'name': beacons[mac_address].get('name') or name
            })

        if len(scans) == 0:
            logger.info("No scans sent from {}".format(ip_address))
            return 'No scans sent'
        
        closest_scan = None
        for scan in scans:
            if closest_scan is None or closest_scan['signal_strength'] > scan['signal_strength']:
                closest_scan = scan

        user_table[ip_address] = {
            'closest_scan': closest_scan,
            'ip_address': ip_address,
            'scans': scans,
        }
        logger.info('User {} is near {} ({})'.format(ip_address, closest_scan['name'], closest_scan['mac_address']))

    return render_template("index.html", title = 'App')
