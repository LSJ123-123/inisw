import os
import subprocess
import uuid
import cv2
import numpy as np
import requests
import boto3
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from urllib.parse import urlparse
from botocore.exceptions import NoCredentialsError, ClientError
from skimage.metrics import structural_similarity as compare_ssim
from pyngrok import ngrok
from concurrent.futures import ThreadPoolExecutor

# 초기 환경 설정
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

os.system(f"pip install -r scripts/diffusion-requirements.txt")

# diffusion 저장소 클론 및 파일 설정
CODE_DIR = 'diffusion'
if not os.path.exists(CODE_DIR):
    os.system(f'git clone https://github.com/Fantasy-Studio/Paint-by-Example {CODE_DIR}')

os.chdir(CODE_DIR)

# 필요한 디렉토리 생성
pretrain_dir = 'checkpoints'
os.makedirs(pretrain_dir, exist_ok=True)

def download_file_if_not_exists(url, save_name, target_dir):
    save_path = os.path.join(target_dir, save_name)
    
    # 파일 존재 여부 확인
    if os.path.exists(save_path):
        # 파일이 있지만 용량이 0이거나 너무 작은 경우(다운로드 실패 흔적)를 대비해 체크하면 더 좋습니다.
        if os.path.getsize(save_path) > 1000: # 최소 1KB 이상인지 확인
            print(f"{save_name} 파일이 이미 존재하여 다운로드를 생략합니다.")
            return
        else:
            print(f"기존 파일이 손상된 것으로 보여 다시 다운로드합니다.")

    print(f"{save_name} 다운로드 시작...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"{save_name} 다운로드 완료!")
    except Exception as e:
        print(f"{save_name} 다운로드 중 오류 발생: {e}")

model_url = "https://huggingface.co/Fantasy-Studio/Paint-by-Example/resolve/main/model.ckpt"
download_file_if_not_exists(model_url, "model.ckpt", pretrain_dir)

print("모든 파일 다운로드 완료!")

os.chdir('..') 
print(f"현재 위치: {os.getcwd()}")

app = Flask(__name__)
CORS(app)

# 상대 경로를 사용하여 .env.local 파일 경로 설정
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_s3_region = os.getenv('AWS_S3_REGION')
bucket_name = os.getenv('AWS_S3_BUCKET_NAME')
ngrok_token = os.getenv('NGROK_AUTH_TOKEN_diffusion')

# 환경 변수 로드 확인
print(f"AWS S3 Region: {aws_s3_region}")
print(f"Bucket Name: {bucket_name}")
print(f"AWS Access Key ID 존재: {'있음' if aws_access_key_id else '없음'}")
print(f"AWS Secret Access Key 존재: {'있음' if aws_secret_access_key else '없음'}")

# --- 비동기 작업 관리 설정 ---
executor = ThreadPoolExecutor(max_workers=2)
tasks = {} # 작업 상태를 저장할 딕셔너리

# S3 클라이언트 초기화
s3_client = boto3.client(
    's3',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=aws_s3_region
)

def get_output_dir_from_image(reference_url, base_dir="."):
    """입력 이미지 파일명(lampX.png)에 맞는 lampX_results 폴더를 찾는 함수"""
    # URL에서 파일명(lampX.png) 추출
    base_name = os.path.splitext(os.path.basename(urlparse(reference_url).path))[0]  # lampX 추출
    output_dir = os.path.join(base_dir, f"{base_name}_results")
    os.makedirs(output_dir, exist_ok=True)

    # 결과 폴더가 존재하는지 확인
    if os.path.exists(output_dir):
        return output_dir
    else:
        raise Exception(f"Output directory not found: {output_dir}")

def get_s3_key_prefix(image_url, reference_url): 
    """S3에 업로드할 때 사용할 키 프리픽스 생성 함수"""
    # URL에서 파일명 추출 (예: 10_449_4.png)
    file_name = os.path.basename(urlparse(image_url).path)

    # reference_url 기반으로 출력 디렉토리 이름 가져오기
    refer_name = get_output_dir_from_image(reference_url)

    # S3 키 프리픽스 생성 (예: lamp1/10_449_4.png-diffusion-results/)
    return f"{refer_name}/{file_name}-diffusion-results/"

def upload_file_to_s3(local_path, s3_key, content_type="image/png"):
    """로컬 파일을 S3에 업로드하는 함수"""
    try:
        s3_client.upload_file(
            local_path, 
            bucket_name, 
            s3_key,
            ExtraArgs={'ContentType': content_type}
        )
        return f"https://{bucket_name}.s3.{aws_s3_region}.amazonaws.com/{s3_key}"
    except NoCredentialsError:
        raise Exception("AWS 자격 증명이 없거나 잘못되었습니다.")
    except ClientError as e:
        raise Exception(f"S3 업로드 중 오류 발생: {str(e)}")
    except Exception as e:
        raise Exception(f"파일 업로드 실패: {str(e)}")

def upload_directory_to_s3(local_dir, s3_prefix):
    """디렉토리 전체를 S3에 업로드하는 함수"""
    s3_urls = {}
    
    try:
        for root, dirs, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                
                # 로컬 경로에서 상대 경로 추출
                relative_path = os.path.relpath(local_path, start=local_dir)
                
                # 상대 경로가 None이나 빈 문자열이 아닌지 확인
                if not relative_path:
                    print(f"Warning: Empty relative path for {local_path}")
                    continue
                
                # 윈도우 경로 구분자를 URL 경로 구분자로 변환
                relative_path_fixed = relative_path.replace('\\', '/')
                
                # S3 키 생성
                s3_key = f"{s3_prefix}{relative_path_fixed}"
                
                # 파일이 실제로 존재하는지 확인
                if not os.path.exists(local_path):
                    print(f"Warning: File does not exist: {local_path}")
                    continue
                
                # 콘텐츠 타입 결정
                content_type = "image/png" if file.endswith(".png") else "application/octet-stream"
                
                # S3에 업로드
                try:
                    s3_client.upload_file(
                        local_path, 
                        bucket_name, 
                        s3_key,
                        ExtraArgs={'ContentType': content_type}
                    )
                    s3_url = f"https://{bucket_name}.s3.{aws_s3_region}.amazonaws.com/{s3_key}"
                    s3_urls[relative_path_fixed] = s3_url
                    print(f"파일 업로드 완료: {local_path} -> {s3_url}")
                except Exception as e:
                    print(f"개별 파일 업로드 실패: {local_path} -> {str(e)}")
                    continue
                
        return s3_urls
    except Exception as e:
        print(f"디렉토리 업로드 세부 오류: {str(e)}")
        raise Exception(f"디렉토리 업로드 실패: {str(e)}")

def read_image_from_url(url, grayscale=False):
    """Directly read image from URL without saving"""
    try:
        # Read image from URL
        response = requests.get(url)
        response.raise_for_status()

        # Convert to numpy array
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)

        # Decode image
        if grayscale:
            return cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    except Exception as e:
        raise Exception(f"Failed to read image from {url}: {str(e)}")

def resize_image(image, target_height=512, target_width=512):
    return cv2.resize(image, (target_width, target_height))

# --- 백그라운드 작업 함수 (Worker) ---

def background_process_image(task_id, data):
    """Diffusion 모델 처리 백그라운드 작업"""
    try:
        tasks[task_id]['status'] = 'processing'
        image_url = data.get("image_path")
        mask_url = data.get("mask_path")
        reference_url = data.get("reference_path")
        seed = data.get("seed", 321)
        scale = data.get("scale", 20)

        output_dir = get_output_dir_from_image(reference_url)
        img = read_image_from_url(image_url)
        mask = read_image_from_url(mask_url, grayscale=True)
        reference = read_image_from_url(reference_url)

        if img.shape[:2] != (512, 512): img = resize_image(img)
        if mask.shape[:2] != (512, 512): mask = resize_image(mask)
        if reference.shape[:2] != (512, 512): reference = resize_image(reference)

        base_name = os.path.splitext(os.path.basename(urlparse(image_url).path))[0] or "image"
        temp_paths = {
            "image": os.path.join(output_dir, f"{base_name}_temp.png"),
            "mask": os.path.join(output_dir, f"{base_name}_mask_temp.png"),
            "reference": os.path.join(output_dir, f"{base_name}_reference_temp.png")
        }
        for path, img_data in zip(temp_paths.values(), [img, mask, reference]):
            cv2.imwrite(path, img_data)

        command = ["python", "diffusion/scripts/inference.py", "--plms", "--outdir", output_dir,
                   "--config", "diffusion/configs/v1.yaml", "--ckpt", "diffusion/checkpoints/model.ckpt",
                   "--image_path", temp_paths['image'], "--mask_path", temp_paths['mask'],
                   "--reference_path", temp_paths['reference'], "--seed", str(seed), "--scale", str(scale)]
        
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0: raise Exception(result.stderr)

        processed_file_path = os.path.join(output_dir, "results", f"{base_name}_temp_{seed}.png")
        for p in temp_paths.values(): 
            if os.path.exists(p): os.remove(p)

        filename = image_url.split('-')[-1]
        s3_prefix = get_s3_key_prefix(filename, reference_url)
        s3_urls = upload_directory_to_s3(output_dir, s3_prefix)
        
        rel_path = os.path.relpath(processed_file_path, start=output_dir).replace('\\', '/')
        s3_processed_image_path = f"https://{bucket_name}.s3.{aws_s3_region}.amazonaws.com/{s3_prefix}{rel_path}"

        tasks[task_id].update({
            'status': 'completed',
            'result': {
                "processed_image_path": processed_file_path,
                "s3_processed_image_path": s3_processed_image_path,
                "s3_urls": s3_urls
            }
        })
    except Exception as e:
        tasks[task_id].update({'status': 'failed', 'error': str(e)})

def background_generate_mask(task_id, data):
    """마스크 생성 백그라운드 작업"""
    try:
        tasks[task_id]['status'] = 'processing'
        processed_image_path = os.path.abspath(data.get("processed_image_path"))
        original_image_path = data.get("original_image_path")
        reference_url = data.get("reference_path")
        image_url = data.get("original_image_path")

        output_dir = get_output_dir_from_image(reference_url)
        imageA = cv2.imread(processed_image_path)
        imageB = read_image_from_url(original_image_path)

        if imageA.shape[:2] != imageB.shape[:2]:
            imageB = cv2.resize(imageB, (imageA.shape[1], imageA.shape[0]))

        grayA, grayB = cv2.cvtColor(imageA, cv2.COLOR_BGR2GRAY), cv2.cvtColor(imageB, cv2.COLOR_BGR2GRAY)
        (score, diff) = compare_ssim(grayA, grayB, full=True)
        diff = (diff * 255).astype("uint8")
        _, thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        flood_filled = thresh.copy()
        h, w = flood_filled.shape[:2]
        cv2.floodFill(flood_filled, np.zeros((h + 2, w + 2), dtype=np.uint8), (0, 0), 255)
        combined_filled = cv2.bitwise_or(thresh, cv2.bitwise_not(flood_filled))
        
        _, bright_mask = cv2.threshold(grayA, 200, 255, cv2.THRESH_BINARY)
        common_mask = cv2.bitwise_and(combined_filled, bright_mask)
        blurred_mask = cv2.GaussianBlur(common_mask, (51, 51), 0)

        base_name = os.path.splitext(os.path.basename(urlparse(processed_image_path).path))[0]
        mask_path = os.path.join(output_dir, f"mask_{base_name}.png")
        cv2.imwrite(mask_path, blurred_mask)

        filename = image_url.split('-')[-1]
        s3_prefix = get_s3_key_prefix(filename, reference_url)
        s3_key = f"{s3_prefix}{os.path.relpath(mask_path, start=os.path.dirname(output_dir)).replace('\\', '/')}"
        s3_mask_url = upload_file_to_s3(mask_path, s3_key)

        tasks[task_id].update({
            'status': 'completed',
            'result': {"mask_path": mask_path, "s3_mask_url": s3_mask_url}
        })
    except Exception as e:
        tasks[task_id].update({'status': 'failed', 'error': str(e)})

# --- API 엔드포인트 ---

@app.route("/process_image", methods=["POST"])
def process_image():
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': 'queued'}
    executor.submit(background_process_image, task_id, request.json)
    return jsonify({"message": "Processing started", "task_id": task_id}), 202

@app.route("/generate_mask", methods=["POST"])
def generate_mask():
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': 'queued'}
    executor.submit(background_generate_mask, task_id, request.json)
    return jsonify({"message": "Mask generation started", "task_id": task_id}), 202

@app.route("/task_status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    task = tasks.get(task_id)
    if not task: return jsonify({"error": "Task not found"}), 404
    return jsonify(task), 200

# 로컬에서 실행할 때
# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8080, debug=True)

if __name__ == '__main__':
    # ngrok 인증 및 터널 생성
    PORT = 8080
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