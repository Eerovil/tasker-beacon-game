from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import json
from logging.config import dictConfig
import random


FILE_PATH = os.path.dirname(os.path.abspath(__file__))
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



app = Flask(__name__, static_url_path='/static', static_folder='../static', template_folder='../templates')
logger = app.logger


main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)
user_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="users", autocommit=True)
shop_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="shops", autocommit=True)
shop_table = {}
user_items_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="user_items", autocommit=True)


beacons = {}
with open(os.path.join(data_folder, 'beacons.json'), 'r') as f:
    beacons_file = json.load(f)
    for mac_address in beacons_file:
        beacons[mac_address.upper()] = {
            'mac_address': mac_address.upper(),
            **beacons_file[mac_address]
        }


def refresh_shops():
    # Generate shopkeeper and items for each beacon
    # Get items at glob FILE_PATH/../static/items/*.png
    items = {}
    for item_file in os.listdir(os.path.join(FILE_PATH, '../static/items')):
        if item_file.endswith('.png'):
            slug = item_file.split('.')[0]
            items[slug] = {
                'slug': slug,
                'name': slug.capitalize(),
                'url': os.path.join('/static/items', item_file),
                'price': random.randint(1, 5),
            }

    merchants = {}
    for item_file in os.listdir(os.path.join(FILE_PATH, '../static/merchants')):
        if item_file.endswith('.png'):
            slug = item_file.split('.')[0]
            merchants[slug] = {
                'slug': slug,
                'name': slug.capitalize(),
                'url': os.path.join('/static/merchants', item_file)
            }

    def random_pop(_dict):
        if len(list(_dict.keys())) == 0:
            logger.warning("Out of items!")
            return None
        return _dict.pop(random.choice(list(_dict.keys())))

    for beacon_mac in beacons.keys():
        shop_table[beacon_mac] = {
            'shopkeeper': random_pop(merchants),
            'items': [random_pop(items) for _ in range(3)]
        }

    # Find favorite thing for each shopkeeper from another shop
    for beacon_mac in beacons.keys():
        other_items = []
        for other_beacon_mac in beacons.keys():
            if other_beacon_mac != beacon_mac:
                other_items.extend(shop_table[other_beacon_mac]['items'])

        if len(other_items) == 0:
            continue
        
        favorite_item = random.choice(other_items)
        shop_table[beacon_mac]['favorite_item'] = favorite_item


refresh_shops()


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Methods']='*'
    response.headers['Access-Control-Allow-Origin']='*'
    response.headers['Vary']='Origin'
    return response


@app.route("/")
def hello_world():
    return render_template("index.html", title = 'App')



@app.route("/map", methods=['GET'])
def map():
    if request.method != 'GET':
        return '', 405

    return json.dumps({
        'beacons': beacons,
        'shops': shop_table
    })


@app.route("/get_my_data", methods=['GET'])
def get_my_data():
    if request.method != 'GET':
        return '', 405

    ip_address = request.remote_addr
    ip_address = "192.168.100.128"
    if ip_address not in user_table:
        return '', 404

    user_data = user_table[ip_address]
    return json.dumps({**user_data, **user_items_table.get(ip_address, {})})


@app.route("/send_scan", methods=['POST'])
def send_scan():
    if request.method == 'POST':
        ip_address = request.remote_addr
        ip_address = "192.168.100.128"
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
            user_table[ip_address] = {
                'ip_address': ip_address,
                'scans': [],
            }
            return 'No scans sent'
        
        closest_scan = None
        for scan in scans:
            if closest_scan is None or closest_scan['signal_strength'] > scan['signal_strength']:
                closest_scan = scan

        closest_scan['beacon'] = beacons[closest_scan['mac_address']]

        user_table[ip_address] = {
            'closest_scan': closest_scan,
            'ip_address': ip_address,
            'scans': scans,
        }
        logger.info('User {} is near {} ({})'.format(ip_address, closest_scan['name'], closest_scan['mac_address']))
        return json.dumps(user_table[ip_address])

    return '', 405