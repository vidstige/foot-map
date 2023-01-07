import io
from typing import Tuple

from flask import Flask, jsonify, Response
import meshcut
import numpy as np
import requests
import svgwrite
from werkzeug.routing import BaseConverter


A4 = ('210mm', '297mm')


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
        if np.isclose(n[0], 0):
            u = normalized(np.array([n[2], -n[1], 0]))
        else:
            u = normalized(np.array([n[1], -n[0], 0]))
        v = np.cross(u, n)

        # compute u, v components
        u0 = np.dot(u, p - o).item()
        v0 = np.dot(v, p - o).item()
        return u0, v0


def grid_lines(dwg: svgwrite.Drawing, spacing: Tuple[float, float], **extra) -> svgwrite.container.Group:
    spacing_x, spacing_y = spacing
    group = svgwrite.container.Group()
    minx, miny, width, height = [float(c) for c in dwg['viewBox'].split()]
    # draw vertical lines
    for x in np.arange(minx, minx + width, spacing_x):
        group.add(dwg.line((x, miny), (x, miny + height), **extra))
    # draw horizontal lines
    for y in np.arange(miny, miny + height, spacing_y):
        group.add(dwg.line((minx, y), (minx + width, y), **extra))
    return group


@app.route('/<external_link:external_link>/')
def foot_map(external_link: str):
    r = requests.get(f'https://my.volumental.com/uploads/{external_link}/left.obj')
    r.raise_for_status()
    vertices, faces = parse_wavefront(io.StringIO(r.content.decode()))

    h = 0.005
    dwg = svgwrite.Drawing('{external_link}.svg', size=A4, viewBox="0 0 0.210 0.297")
    dwg.add(grid_lines(dwg, spacing=(0.01, 0.01), stroke=svgwrite.rgb(40, 40, 46, '%'), stroke_width='0.0002'))
    group = svgwrite.container.Group(transform='translate(0.1, 0.275)')
    dwg.add(group)
    for offset in np.arange(h, 0.10, h):
        plane = Plane(origin=(0.0, 0.0, offset), normal=(0, 0, 1))
        # compute conturs at offset
        contours = meshcut.cross_section(
            vertices, faces,
            plane_orig=plane.origin, plane_normal=plane.normal)
        for contour in contours:
            points = [plane.project(p) for p in contour]
            group.add(dwg.polygon(points, stroke=svgwrite.rgb(10, 10, 16, '%'), stroke_width='0.0005', fill='white', fill_opacity=0.05))

    #dwg.add(dwg.text('vidstige', insert=(0, 0.2), fill='red'))

    return Response(dwg.tostring(), content_type="image/svg+xml")

