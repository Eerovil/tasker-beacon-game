from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import json
from logging.config import dictConfig
import random
import time


FILE_PATH = os.path.dirname(os.path.abspath(__file__))
data_folder = 'data'


RUNTIME_RAND = random.randrange(0, 100000)


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
                'price': random.randint(1, 3),
            }

    merchants = {}
    for item_file in os.listdir(os.path.join(FILE_PATH, '../static/merchants')):
        if item_file.endswith('.png'):
            slug = item_file.split('.')[0]
            merchants[slug] = {
                'slug': slug,
                'name': slug.capitalize(),
                'url': os.path.join('/static/merchants', item_file),
                'happiness': 0,
            }

    def random_pop(_dict):
        if len(list(_dict.keys())) == 0:
            logger.warning("Out of items!")
            return None
        return _dict.pop(random.choice(list(_dict.keys())))

    index = 1
    for beacon_mac in beacons.keys():
        _items = [random_pop(items) for _ in range(3)]
        for _item in _items:
            _item['price'] *= index
        index += 2
        shop_table[beacon_mac] = {
            'mac_address': beacon_mac,
            'shopkeeper': random_pop(merchants),
            'items': _items
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
        shop_table[beacon_mac]['shopkeeper']['favorite_item'] = favorite_item


refresh_shops()


def get_ip():
    ip_address = request.remote_addr
    # ip_address = "192.168.100.128"
    return ip_address


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

    ip_address = get_ip()
    if ip_address not in user_table:
        return '', 404

    user_data = user_table[ip_address]

    if ip_address not in user_items_table:
        user_items_table[ip_address] = {
            'inventory': None,
            'money': 5,
        }

    return json.dumps({**user_data, **user_items_table.get(ip_address, {}), 'run': RUNTIME_RAND})


@app.route("/purchase_item", methods=['POST'])
def purchase_item():
    if request.method != 'POST':
        return '', 405

    ip_address = get_ip()
    if ip_address not in user_table:
        return '', 404

    user_data = user_table[ip_address]

    if not user_data.get('closest_scan'):
        return '', 400

    user_items = user_items_table.get(ip_address, {})

    item_slug = request.json['slug']

    mac_address = user_data['closest_scan']['mac_address']

    for item in shop_table[mac_address]['items']:
        if item['slug'] == item_slug:
            break
    else:
        return '', 404

    if item['price'] > user_items['money']:
        return 'Not enough money ({} < {})'.format(item['price'], user_items['money']), 400

    user_items['money'] -= item['price']
    user_items['inventory'] = item
    user_items_table[ip_address] = user_items

    return json.dumps({
        'inventory': user_items['inventory'],
        'money': user_items['money'],
    })


@app.route("/sell_item", methods=['POST'])
def sell_item():
    if request.method != 'POST':
        return '', 405

    ip_address = get_ip()
    if ip_address not in user_table:
        return '', 404

    user_data = user_table[ip_address]

    if not user_data.get('closest_scan'):
        return '', 400

    user_items = user_items_table.get(ip_address, {})

    item_slug = request.json['slug']

    mac_address = user_data['closest_scan']['mac_address']

    item = None
    in_current_shop = False
    for shop in shop_table.values():
        logger.info(shop)
        for _item in shop['items']:
            if _item['slug'] == item_slug:
                item = _item
                in_current_shop = (shop['mac_address'] == mac_address)
                break
        if item:
            break
    if not item:
        return '', 404

    shop = shop_table[mac_address]
    sale_price = item['price']

    if not in_current_shop:
        sale_price += 1

    if shop['shopkeeper']['favorite_item']['slug'] == item_slug:
        sale_price *= 2
        shop_table[mac_address]['shopkeeper']['happiness'] += 1

    user_items['money'] += sale_price
    user_items['inventory'] = None
    user_items_table[ip_address] = user_items
    return json.dumps({
        'shops': shop_table,
        'inventory': user_items['inventory'],
        'money': user_items['money'],
    })


@app.route("/send_scan", methods=['POST'])
def send_scan():
    if request.method == 'POST':
        ip_address = get_ip()
        data = request.json
        # logger.info("scans from {}: {}".format(ip_address, data))
        mac_addresses = data.get('mac', '').upper().split(',')
        signal_strengths = data.get('ss', '').split(',')
        current_ms = time.time_ns() // 1000000

        if not user_table.get(ip_address):
            scans = {}
        else:
            scans = user_table[ip_address]['scans']

        for mac_address, signal_strength in zip(mac_addresses, signal_strengths):
            if not mac_address:
                continue
            if mac_address not in beacons:
                continue

            signal_strength = int(signal_strength)
            signal_offset = beacons[mac_address].get('offset', 0)
            signal_strength += signal_offset
            # if signal_strength < -75:
            #     continue
            scans[mac_address] = {
                'mac_address': mac_address,
                'signal_strength': signal_strength,
                'name': beacons[mac_address].get('name') or '',
                'last_seen': current_ms,
            }

        closest_scan = None
        to_delete = []
        for scan in scans.values():
            if scan['last_seen'] < (current_ms - 10000):
                to_delete.append(scan['mac_address'])
                continue

            # if closest_scan:
            #     logger.info("comparinng %s > %s -> %s", closest_scan['signal_strength'], scan['signal_strength'], closest_scan['signal_strength'] > scan['signal_strength'])
            if closest_scan is None or scan['signal_strength'] > closest_scan['signal_strength']:
                closest_scan = scan

        # logger.info(scans)

        for mac_address in to_delete:
            logger.info("dropping %s", mac_address)
            del scans[mac_address]

        if not closest_scan:
            return '', 200

        closest_scan['beacon'] = beacons[closest_scan['mac_address']]

        user_table[ip_address] = {
            'closest_scan': closest_scan,
            'ip_address': ip_address,
            'scans': scans,
        }
        logger.info('User {} is near {} ({} {})'.format(ip_address, closest_scan['name'], closest_scan['mac_address'], closest_scan['signal_strength']))
        return json.dumps(user_table[ip_address])

    return '', 405