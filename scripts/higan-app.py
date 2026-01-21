# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
from pyngrok import ngrok
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)

# ngrok 사용을 위한 환경 변수 로드
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))
ngrok_token = os.getenv('NGROK_AUTH_TOKEN_higan')

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

# 로컬에서 실행할 때
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    # ngrok 인증 및 터널 생성
    PORT = 8000
    if ngrok_token:
        try:
            # 토큰 설정
            ngrok.set_auth_token(ngrok_token)
            # 터널 열기
            public_url = ngrok.connect(PORT).public_url
            print(f"\n" + "="*50)
            print(f" * ngrok 터널이 활성화되었습니다!")
            print(f" * Public URL: {public_url}")
            print(f" * 위 주소를 프론트엔드의 API 엔드포인트로 사용하세요.")
            print("="*50 + "\n")
        except Exception as e:
            print(f"ngrok 연결 실패: {e}")
    else:
        print("경고: NGROK_AUTH_TOKEN이 설정되지 않았습니다. 로컬에서만 접속 가능합니다.")

    # Flask 실행 (debug=True 사용 시 use_reloader=False 권장)
    # use_reloader=False를 안 하면 ngrok 터널이 두 번 실행되려다 에러가 날 수 있습니다.
    app.run(host='0.0.0.0', port=PORT, debug=True, use_reloader=False)
