"""
  web server to create signs and return them
"""
import os
from make_signs import make_signs_from_lines
from flask import Flask, Response, send_from_directory
from flask import request

PUBLIC_DIR = 'web'

app = Flask(__name__)

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
    make_signs_from_lines(data.split('\n'))
    return send_from_directory('output', 'signs.zip')

@app.route('/<path:path>')
def send_report(path):
    return send_from_directory('web', path)

@app.route("/")
def hello():
    content = get_file('index.html')
    return Response(content, mimetype="text/html")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7100)
