# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os

app = Flask(__name__)
CORS(app)

@app.route('/run-higan', methods=['POST'])
def run_higan():
    try:
        # Execute the higan-code.py script
        script_path = os.path.join(os.path.dirname(__file__), "higan-code.py")
        print(f"Executing script at: {script_path}")
        # subprocess
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,   # stdout/stderr
            text=True              # text
        )
        
        if result.returncode != 0:
            return jsonify({"error": result.stderr}), 500
        return jsonify({"message": "Higan script executed successfully", "output": result.stdout}), 200
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
