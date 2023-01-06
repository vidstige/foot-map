import io
from tempfile import NamedTemporaryFile
from typing import Tuple

from flask import Flask, jsonify, Response
import meshcut
import numpy as np
import requests
import svgwrite
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


def normalized(a, axis=-1, order=2):
    l2 = np.atleast_1d(np.linalg.norm(a, order, axis))
    return a / np.expand_dims(l2, axis)


class Plane:
    def __init__(self, origin: Tuple[float, float, float], normal: Tuple[float, float, float]):
        self.origin = origin
        self.normal = normal

    def project(self, point: Tuple[float, float, float]) -> Tuple[float, float]:
        n = np.array(self.normal)
        o = np.array(self.origin)
        p = np.array(point)
        # create arbtitary u,v basis vectors in the plane
        print(n)
        if np.isclose(n[0], 0):
            u = normalized(np.array([n[2], -n[1], 0]))
        else:
            u = normalized(np.array([n[1], -n[0], 0]))
        v = np.cross(u, n)

        # compute u, v components
        u0 = np.dot(u, p - o).item()
        v0 = np.dot(v, p - o).item()
        return (1000 * u0 + 100, 1000 * v0 + 400)


@app.route('/<external_link:external_link>/')
def foot_map(external_link: str):
    r = requests.get(f'https://my.volumental.com/uploads/{external_link}/left.obj')
    r.raise_for_status()
    vertices, faces = parse_wavefront(io.StringIO(r.content.decode()))
    plane = Plane(origin=(0.0, 0.0, 0.02), normal=(0, 0, 1))
    contours = meshcut.cross_section(
        vertices, faces,
        plane_orig=plane.origin, plane_normal=plane.normal)

    with NamedTemporaryFile(suffix='svg') as tmp:
        dwg = svgwrite.Drawing(tmp.name)
        
        for contour in contours:
            points = [plane.project(p) for p in contour]
            dwg.add(dwg.polygon(points, stroke=svgwrite.rgb(10, 10, 16, '%'), fill='none'))

        #dwg.add(dwg.text('vidstige', insert=(0, 0.2), fill='red'))

        return Response(dwg.tostring(), content_type="image/svg+xml")
