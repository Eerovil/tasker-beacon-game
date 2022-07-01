# Pass through any arguments to the python program.

FLASK_APP=tasker_beacon_game.views python3 -m flask run --host=0.0.0.0 --port=5000 --reload $@
