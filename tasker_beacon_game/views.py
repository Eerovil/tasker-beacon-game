from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os


data_folder = 'data'

app = Flask(__name__, static_url_path='/static', static_folder=data_folder, template_folder='../templates')
logger = app.logger

main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Methods']='*'
    response.headers['Access-Control-Allow-Origin']='*'
    response.headers['Vary']='Origin'
    return response


@app.route("/")
def hello_world():
    return render_template("index.html", title = 'App')

