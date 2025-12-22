#!/usr/bin/env python3
"""
끼록이 AI - Gemini File Search 스토어 초기화 및 파일 업로드
기록과사회 뉴스레터 420건을 Gemini File Search에 업로드
"""

import os
import json
import time
import requests
from pathlib import Path

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta"

# 데이터 경로
DATA_PATH = Path("/Users/junghyeji/Library/Mobile Documents/iCloud~md~obsidian/Documents/정혜지_obsidian_2025_v2.0/10-work/11-project/119-기로기ai챗봇/기록과사회 뉴스레터 데이터")

def get_api_key():
    """API 키 가져오기"""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수를 설정해주세요")
    return api_key

def list_stores(api_key: str) -> list:
    """기존 스토어 목록 조회"""
    url = f"{BASE_URL}/fileSearchStores"
    params = {"key": api_key, "pageSize": 50}

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get('fileSearchStores', [])
    return []

def create_store(api_key: str, display_name: str) -> dict:
    """새 File Search Store 생성"""
    url = f"{BASE_URL}/fileSearchStores"
    params = {"key": api_key}
    headers = {"Content-Type": "application/json"}
    data = {"displayName": display_name}

    response = requests.post(url, params=params, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"스토어 생성 실패: {response.status_code} - {response.text[:200]}")

def upload_file(api_key: str, store_id: str, file_path: Path) -> dict:
    """파일을 스토어에 업로드"""
    url = f"{UPLOAD_URL}/{store_id}:uploadToFileSearchStore"
    params = {"key": api_key}

    with open(file_path, 'rb') as f:
        file_content = f.read()

    files = {
        'file': (file_path.name, file_content, 'text/markdown')
    }

    metadata = {
        'displayName': file_path.stem[:100]  # 파일명 (확장자 제외)
    }

    response = requests.post(
        url,
        params=params,
        files=files,
        data={'metadata': json.dumps(metadata)}
    )

    if response.status_code in [200, 202]:
        return response.json()
    else:
        raise Exception(f"업로드 실패: {response.status_code}")

def save_config(store_id: str, store_name: str):
    """설정 파일 저장"""
    config = {
        "corpus_name": store_id,
        "store_name": store_name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": str(DATA_PATH),
        "description": "기록과사회 뉴스레터 아카이브"
    }

    config_path = Path(__file__).parent / "store_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✓ 설정 저장: {config_path}")

def main():
    print("=" * 60)
    print("끼록이 AI - Gemini File Search 스토어 초기화")
    print("=" * 60)
    print()

    api_key = get_api_key()
    print("✓ API 키 로드 완료")

    store_name = "girogi-ai-archive"

    # 1. 기존 스토어 확인
    existing_stores = list_stores(api_key)
    existing_map = {s.get('displayName', ''): s.get('name', '') for s in existing_stores}
    print(f"✓ 기존 스토어 {len(existing_stores)}개 발견")

    # 2. 스토어 생성 또는 재사용
    if store_name in existing_map:
        store_id = existing_map[store_name]
        print(f"✓ 기존 스토어 재사용: {store_name}")
        print(f"  Store ID: {store_id}")
    else:
        result = create_store(api_key, store_name)
        store_id = result.get('name', '')
        print(f"✓ 새 스토어 생성: {store_name}")
        print(f"  Store ID: {store_id}")

    print()

    # 3. 파일 목록 확인
    md_files = list(DATA_PATH.glob("*.md"))
    print(f"✓ 업로드할 파일: {len(md_files)}개")
    print()

    # 4. 파일 업로드
    uploaded = 0
    failed = 0

    print("파일 업로드 중...")
    print("-" * 60)

    for idx, file_path in enumerate(md_files, 1):
        try:
            # 파일 크기 체크 (10MB 제한)
            if file_path.stat().st_size > 10 * 1024 * 1024:
                print(f"[{idx}/{len(md_files)}] 건너뜀 (>10MB): {file_path.name[:40]}")
                continue

            upload_file(api_key, store_id, file_path)
            uploaded += 1

            if idx % 50 == 0:
                print(f"[{idx}/{len(md_files)}] {uploaded}개 업로드 완료...")

            # Rate limit 방지
            time.sleep(0.2)

        except Exception as e:
            failed += 1
            if failed <= 5:  # 처음 5개 오류만 출력
                print(f"[{idx}] 실패: {file_path.name[:30]} - {str(e)[:30]}")

    print("-" * 60)
    print(f"✓ 업로드 완료: {uploaded}개 성공, {failed}개 실패")
    print()

    # 5. 설정 저장
    save_config(store_id, store_name)

    print()
    print("=" * 60)
    print("✓ 초기화 완료!")
    print(f"  Store ID: {store_id}")
    print()
    print("다음 단계:")
    print("  streamlit run app.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
