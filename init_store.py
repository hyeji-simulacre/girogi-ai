#!/usr/bin/env python3
"""
끼록이 AI - Gemini File Search 스토어 관리 및 메타데이터 생성

기능:
1. data/ 폴더의 .md 파일을 Gemini File Search에 업로드
2. article_metadata.json 자동 생성 (title, url, author 포함)

GitHub Actions에서 자동 실행됨
"""

import os
import re
import json
import time
import requests
import yaml
from pathlib import Path

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta"

# 경로 설정 (repo 기준)
SCRIPT_DIR = Path(__file__).parent
DATA_PATH = SCRIPT_DIR / "data"
METADATA_PATH = SCRIPT_DIR / "article_metadata.json"
CONFIG_PATH = SCRIPT_DIR / "store_config.json"
UPLOADED_TRACKER_PATH = SCRIPT_DIR / ".uploaded_files.json"


def get_api_key():
    """API 키 가져오기"""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경변수를 설정해주세요")
    return api_key


def load_config():
    """스토어 설정 로드"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def load_uploaded_files():
    """이미 업로드된 파일 목록 로드"""
    if UPLOADED_TRACKER_PATH.exists():
        with open(UPLOADED_TRACKER_PATH, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()


def save_uploaded_files(files: set):
    """업로드된 파일 목록 저장"""
    with open(UPLOADED_TRACKER_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(files), f, ensure_ascii=False, indent=2)


def parse_frontmatter(file_path: Path) -> dict:
    """마크다운 파일에서 YAML frontmatter 파싱"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # YAML frontmatter 추출
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if match:
            yaml_content = match.group(1)
            data = yaml.safe_load(yaml_content)
            return data if data else {}
    except Exception as e:
        print(f"  frontmatter 파싱 실패 ({file_path.name}): {e}")
    return {}


def load_existing_metadata():
    """기존 메타데이터 로드"""
    if METADATA_PATH.exists():
        try:
            with open(METADATA_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"  기존 메타데이터 로드 실패: {e}")
    return {}


def generate_metadata():
    """data/ 폴더의 .md 파일에서 메타데이터 생성 (기존 메타데이터 보존)"""
    # 기존 메타데이터 로드 (보존)
    metadata = load_existing_metadata()
    existing_count = len(metadata)
    print(f"기존 메타데이터: {existing_count}개 로드")

    if not DATA_PATH.exists():
        print(f"데이터 폴더가 없습니다: {DATA_PATH}")
        return metadata  # 기존 메타데이터 반환

    md_files = list(DATA_PATH.glob("*.md"))
    new_count = 0

    print(f"data/ 폴더 스캔 중... ({len(md_files)}개 파일)")

    for file_path in md_files:
        # 파일명 (확장자 제외)을 키로 사용
        key = file_path.stem

        # 이미 존재하면 건너뜀
        if key in metadata:
            continue

        frontmatter = parse_frontmatter(file_path)

        # 저자 추출 (리스트 또는 문자열)
        author = frontmatter.get('author', [])
        if isinstance(author, list):
            author = author[0] if author else '기록과 사회'

        metadata[key] = {
            'title': frontmatter.get('title', key),
            'url': frontmatter.get('source', ''),
            'author': author
        }
        new_count += 1

    print(f"새로 추가된 메타데이터: {new_count}개")
    return metadata


def save_metadata(metadata: dict):
    """메타데이터를 JSON 파일로 저장"""
    with open(METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"✓ 메타데이터 저장: {METADATA_PATH} ({len(metadata)}개)")


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
        raise Exception(f"스토어 생성 실패: {response.status_code}")


def upload_file(api_key: str, store_id: str, file_path: Path) -> bool:
    """파일을 스토어에 업로드"""
    url = f"{UPLOAD_URL}/{store_id}:uploadToFileSearchStore"
    params = {"key": api_key}

    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()

        files = {
            'file': (file_path.name, file_content, 'text/markdown')
        }

        metadata = {
            'displayName': file_path.stem[:100]
        }

        response = requests.post(
            url,
            params=params,
            files=files,
            data={'metadata': json.dumps(metadata)}
        )

        return response.status_code in [200, 202]
    except Exception as e:
        print(f"  업로드 실패 ({file_path.name}): {e}")
        return False


def save_config(store_id: str, store_name: str):
    """설정 파일 저장"""
    config = {
        "corpus_name": store_id,
        "store_name": store_name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "data/",
        "description": "기록과사회 뉴스레터 아카이브"
    }

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✓ 설정 저장: {CONFIG_PATH}")


def main():
    print("=" * 60)
    print("끼록이 AI - Gemini Store 업데이트 & 메타데이터 생성")
    print("=" * 60)
    print()

    # 1. 메타데이터 생성 (항상 실행)
    metadata = generate_metadata()
    if metadata:
        save_metadata(metadata)
    else:
        print("! 메타데이터 생성할 파일이 없습니다")
    print()

    # 2. API 키 확인
    try:
        api_key = get_api_key()
        print("✓ API 키 로드 완료")
    except ValueError as e:
        print(f"! {e}")
        print("메타데이터만 생성하고 종료합니다.")
        return

    store_name = "girogi-ai-archive"

    # 3. 기존 스토어 확인
    existing_stores = list_stores(api_key)
    existing_map = {s.get('displayName', ''): s.get('name', '') for s in existing_stores}
    print(f"✓ 기존 스토어 {len(existing_stores)}개 발견")

    # 4. 스토어 생성 또는 재사용
    if store_name in existing_map:
        store_id = existing_map[store_name]
        print(f"✓ 기존 스토어 재사용: {store_name}")
    else:
        result = create_store(api_key, store_name)
        store_id = result.get('name', '')
        print(f"✓ 새 스토어 생성: {store_name}")
        save_config(store_id, store_name)

    print(f"  Store ID: {store_id}")
    print()

    # 5. 새 파일만 업로드
    if not DATA_PATH.exists():
        print("! data/ 폴더가 없습니다")
        return

    md_files = list(DATA_PATH.glob("*.md"))
    uploaded_files = load_uploaded_files()

    new_files = [f for f in md_files if f.name not in uploaded_files]

    if not new_files:
        print("✓ 업로드할 새 파일이 없습니다")
        return

    print(f"새 파일 업로드 중... ({len(new_files)}개)")
    print("-" * 60)

    uploaded = 0
    failed = 0

    for idx, file_path in enumerate(new_files, 1):
        # 파일 크기 체크 (10MB 제한)
        if file_path.stat().st_size > 10 * 1024 * 1024:
            print(f"[{idx}] 건너뜀 (>10MB): {file_path.name[:40]}")
            continue

        if upload_file(api_key, store_id, file_path):
            uploaded += 1
            uploaded_files.add(file_path.name)
            if idx % 10 == 0:
                print(f"[{idx}/{len(new_files)}] 진행 중...")
        else:
            failed += 1

        # Rate limit 방지
        time.sleep(0.3)

    print("-" * 60)
    print(f"✓ 업로드 완료: {uploaded}개 성공, {failed}개 실패")

    # 업로드 추적 파일 저장
    save_uploaded_files(uploaded_files)

    print()
    print("=" * 60)
    print("✓ 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
