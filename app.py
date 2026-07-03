from flask import Flask, send_from_directory, jsonify
import json
import os

app = Flask(__name__, static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory('.', filename)

@app.route('/api/stats')
def stats():
    with open('data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data['stats'])

if __name__ == '__main__':
    app.run(debug=True)
