from flask import Flask, jsonify

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return jsonify('hi')