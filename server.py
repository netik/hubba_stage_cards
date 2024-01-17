#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
  web server to create signs and return them
"""
import os
from make_signs import make_signs_from_lines
from flask import Flask, request, send_from_directory, render_template, send_file
import uuid

app = Flask(__name__, static_url_path='/static', static_folder='static')

def root_dir():  # pragma: no cover
    return os.path.abspath(os.path.dirname(__file__))

def get_file(filename):  # pragma: no cover
    try:
        src = os.path.join(root_dir(), PUBLIC_DIR, filename)
        # Figure out how flask returns static files
        # Tried:
        # - render_template
        # - send_file
        # This should not be so non-obvious
        return open(src, encoding='utf-8').read()
    except IOError as exc:
        return str(exc)

@app.route('/make', methods = ['POST'])
def make():
    data = request.form['namelist']
    id = str(uuid.uuid4())
    output_dir = 'output/' + id
    os.makedirs(output_dir)
    base_name = 'output/' + id
    make_signs_from_lines(data.split('\n'), output_dir=output_dir, base_name=base_name)
    return send_file(base_name + '.zip',
                     mimetype='application/zip', 
                     download_name='signs.zip', 
                     as_attachment=True)

@app.route('/<path:path>')
def send_report(path):
    return send_from_directory('web', path)

@app.route("/") 
def hello(): 
    message = "Hello, World"
    return render_template('index.html',  
                           message=message) 
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7100)
