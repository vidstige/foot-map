import io
from typing import Tuple

from flask import Flask, jsonify
import numpy as np
import requests
from werkzeug.routing import BaseConverter

class ExternalLinkConverter(BaseConverter):
    regex = r'[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}'


def _strip_comment(line: str) -> str:
    index = line.find('#')
    if index < 0:
        return line.rstrip()
    return line[:index].rstrip()


def vertex_index(vertex: str) -> int:
    return int(vertex.split('/')[0]) - 1


def parse_wavefront(f) -> Tuple[np.ndarray, np.ndarray]:
    """Parses wavefront .obj file and returns vertices and triangle indices"""
    stripped = (_strip_comment(line) for line in f)
    skip_empty = (line for line in stripped if line)
    vertices = []
    faces = []
    for line in skip_empty:
        parts = line.split()
        if parts[0] == 'v':
            vertices.append([float(c) for c in parts[1:]])
            
        if parts[0] == 'f':
            faces.append([vertex_index(v) for v in parts[1:]])

    return np.array(vertices), np.array(faces)


app = Flask(__name__, template_folder='templates')
app.url_map.converters['external_link'] = ExternalLinkConverter


@app.route('/')
def index():
    return jsonify('hi')


@app.route('/<external_link:external_link>/')
def foot_map(external_link: str):
    r = requests.get(f'https://my.volumental.com/uploads/{external_link}/left.obj')
    r.raise_for_status()
    vertices, faces = parse_wavefront(io.StringIO(r.content.decode()))
    return jsonify('abc')
