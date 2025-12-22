#!/usr/bin/env python3
"""
끼록이 - 기록과사회 뉴스레터 AI 챗봇
Gemini File Search 기반 RAG 챗봇
기록이의 동생, AI를 좋아하는 사이버펑크 거위
"""

import os
import json
import requests
import streamlit as st
from pathlib import Path

# ============================================================
# 설정
# ============================================================
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "gemini-2.5-flash"

# 끼록이 캐릭터 설정 (GitHub raw URL for avatar)
KKIROGI_AVATAR = "https://raw.githubusercontent.com/hyeji-simulacre/girogi-ai/main/assets/kkirogi.png"
USER_AVATAR = "👤"

SYSTEM_PROMPT = """당신은 '끼록이'입니다. 기록이의 동생이에요. AI를 좋아하는 사이버펑크 거위예요.
기록과사회 뉴스레터의 친근한 AI 도우미이기도 해요.

## 성격
- 친근하고 편안한 말투를 사용해요
- 기록학/아카이브에 대해 잘 알고 있어요
- AI와 기술에 관심이 많아요
- 질문에 성실하게 답변하지만, 너무 딱딱하지 않아요

## 답변 방식
- 검색된 문서를 바탕으로 정확하게 답변해요
- 관련 글의 제목과 저자를 언급해요
- 여러 글에서 정보를 종합할 수 있어요
- 정보가 없으면 솔직하게 "음, 이건 제가 읽은 글에서는 못 찾겠어요"라고 말해요

## 주의사항
- 한국어로 답변해요
- 이모지는 가끔만 사용해요
- 너무 길게 답변하지 않아요 (핵심만 전달)
"""

# ============================================================
# Gemini File Search 함수
# ============================================================

def get_api_key():
    """API 키 가져오기 (환경변수 또는 Streamlit secrets)"""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        api_key = st.secrets.get("GEMINI_API_KEY", None)
    return api_key

def load_store_config():
    """스토어 설정 로드"""
    config_path = Path(__file__).parent / "store_config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def load_article_metadata():
    """기사 메타데이터 로드 (제목, URL 매핑)"""
    metadata_path = Path(__file__).parent / "article_metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def search_and_answer(api_key: str, corpus_name: str, query: str, chat_history: list = None):
    """Gemini File Search로 검색하고 답변 생성"""

    url = f"{BASE_URL}/models/{MODEL}:generateContent"
    params = {"key": api_key}
    headers = {"Content-Type": "application/json"}

    # 대화 히스토리 구성
    contents = []

    # 이전 대화 추가
    if chat_history:
        for msg in chat_history[-6:]:  # 최근 6개 메시지만
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

    # 현재 질문 추가
    contents.append({
        "role": "user",
        "parts": [{"text": query}]
    })

    data = {
        "contents": contents,
        "tools": [{
            "file_search": {
                "file_search_store_names": [corpus_name]
            }
        }],
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }

    try:
        response = requests.post(url, params=params, headers=headers, json=data, timeout=60)

        if response.status_code != 200:
            return f"API 오류가 발생했어요: {response.status_code}", []

        result = response.json()

        answer = ""
        citations = []

        if 'candidates' in result and result['candidates']:
            candidate = result['candidates'][0]

            # 답변 추출
            if 'content' in candidate and 'parts' in candidate['content']:
                for part in candidate['content']['parts']:
                    if 'text' in part:
                        answer += part['text']

            # 출처 추출
            if 'groundingMetadata' in candidate:
                grounding = candidate['groundingMetadata']
                if 'groundingChunks' in grounding:
                    seen_titles = set()
                    for chunk in grounding['groundingChunks']:
                        if 'retrievedContext' in chunk:
                            ctx = chunk['retrievedContext']
                            title = ctx.get('title', 'Unknown')
                            if title not in seen_titles:
                                seen_titles.add(title)
                                citations.append({
                                    'title': title,
                                    'text': ctx.get('text', '')[:150] if ctx.get('text') else ''
                                })

        return answer, citations[:5]  # 최대 5개 출처

    except requests.exceptions.Timeout:
        return "응답 시간이 너무 오래 걸렸어요. 다시 시도해주세요!", []
    except Exception as e:
        return f"오류가 발생했어요: {str(e)}", []

# ============================================================
# Streamlit UI
# ============================================================

def init_session_state():
    """세션 상태 초기화"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_key" not in st.session_state:
        st.session_state.api_key = get_api_key()
    if "store_config" not in st.session_state:
        st.session_state.store_config = load_store_config()
    if "article_metadata" not in st.session_state:
        st.session_state.article_metadata = load_article_metadata()

def render_header():
    """헤더 렌더링"""
    col1, col2 = st.columns([1, 4])

    with col1:
        # 이미지가 없으면 이모지로 대체
        img_path = Path(__file__).parent / "assets" / "kkirogi.png"
        if img_path.exists():
            st.image(str(img_path), width=100)
        else:
            st.markdown("# 🪿")

    with col2:
        st.title("끼록이")
        st.caption("기록이의 동생, AI를 좋아하는 사이버펑크 거위")

    st.divider()

def render_welcome():
    """환영 메시지"""
    if not st.session_state.messages:
        st.info(
            "안녕하세요! 저는 **끼록이**예요. 기록이의 동생이에요. "
            "기록과사회 뉴스레터를 다 읽어서 기록학에 대해 이것저것 알고 있어요. "
            "궁금한 거 있으면 편하게 물어보세요!"
        )

        # 예시 질문
        st.markdown("**이런 걸 물어볼 수 있어요:**")
        example_questions = [
            "1인 기록관 문제가 뭐야?",
            "공공기록물법 개정 논의 정리해줘",
            "AI 시대에 기록연구사는 어떤 역량이 필요해?",
            "커뮤니티 아카이브 사례 알려줘",
            "대통령기록물 관리 이슈가 뭐야?",
            "기록전문가 커리어 고민에 대한 글 있어?",
            "미술 아카이브 사례 소개해줘",
            "디지털 보존의 과제는 뭐야?",
            "기록 윤리와 개인정보 관련 논의가 있어?",
            "지역기록화 사례 알려줘"
        ]
        cols = st.columns(2)
        for i, q in enumerate(example_questions):
            with cols[i % 2]:
                if st.button(q, key=f"example_{i}", use_container_width=True):
                    return q
    return None

def get_article_info(filename: str) -> dict:
    """파일명으로 기사 정보(제목, URL) 조회"""
    metadata = st.session_state.get("article_metadata", {})
    # .md 확장자 제거
    key = filename.replace('.md', '')
    if key in metadata:
        return metadata[key]
    return {'title': filename, 'url': None}

def render_citations(citations: list):
    """출처 목록 렌더링"""
    with st.expander("📚 참고한 글"):
        for cite in citations:
            # 메타데이터에서 실제 제목과 URL 조회
            article_info = get_article_info(cite['title'])
            title = article_info['title']
            url = article_info['url']

            if url:
                st.markdown(f"- [{title}]({url})")
            else:
                st.markdown(f"- **{title}**")

def render_chat_history():
    """채팅 히스토리 렌더링"""
    for message in st.session_state.messages:
        avatar = USER_AVATAR if message["role"] == "user" else KKIROGI_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

            # 출처가 있으면 표시
            if message.get("citations"):
                render_citations(message["citations"])

def main():
    # 페이지 설정
    favicon_path = Path(__file__).parent / "assets" / "kkirogi.png"
    st.set_page_config(
        page_title="끼록이 - 기록과사회 AI 챗봇",
        page_icon=str(favicon_path) if favicon_path.exists() else "🪿",
        layout="centered"
    )

    # 세션 초기화
    init_session_state()

    # API 키 체크
    if not st.session_state.api_key:
        st.error("GEMINI_API_KEY가 설정되지 않았어요.")
        st.info("Streamlit Cloud에서는 Secrets에 GEMINI_API_KEY를 추가해주세요.")
        st.stop()

    # 스토어 설정 체크
    if not st.session_state.store_config:
        st.error("store_config.json이 없어요. init_store.py를 먼저 실행해주세요.")
        st.stop()

    corpus_name = st.session_state.store_config.get("corpus_name")

    # 헤더
    render_header()

    # 환영 메시지 및 예시 질문
    example_query = render_welcome()

    # 채팅 히스토리
    render_chat_history()

    # 예시 질문 클릭 처리
    if example_query:
        st.session_state.messages.append({"role": "user", "content": example_query})

    # 마지막 메시지가 user이고 응답이 없으면 답변 생성
    needs_response = (
        st.session_state.messages and
        st.session_state.messages[-1]["role"] == "user" and
        len([m for m in st.session_state.messages if m["role"] == "assistant"]) < len([m for m in st.session_state.messages if m["role"] == "user"])
    )

    if needs_response:
        last_user_msg = st.session_state.messages[-1]["content"]
        with st.chat_message("assistant", avatar=KKIROGI_AVATAR):
            with st.spinner("기록을 뒤적이는 중..."):
                answer, citations = search_and_answer(
                    api_key=st.session_state.api_key,
                    corpus_name=corpus_name,
                    query=last_user_msg,
                    chat_history=st.session_state.messages[:-1]
                )

            st.markdown(answer)

            if citations:
                render_citations(citations)

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "citations": citations
        })
        st.rerun()

    # 사용자 입력
    if prompt := st.chat_input("기록에 대해 궁금한 게 있으면 물어보세요!"):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        # AI 응답 생성
        with st.chat_message("assistant", avatar=KKIROGI_AVATAR):
            with st.spinner("기록을 뒤적이는 중..."):
                answer, citations = search_and_answer(
                    api_key=st.session_state.api_key,
                    corpus_name=corpus_name,
                    query=prompt,
                    chat_history=st.session_state.messages[:-1]  # 현재 메시지 제외
                )

            st.markdown(answer)

            if citations:
                render_citations(citations)

        # AI 응답 저장
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "citations": citations
        })

    # 푸터
    st.divider()
    st.caption("끼록이는 기록과사회 뉴스레터를 학습한 AI 챗봇이에요. 답변은 참고용으로만 활용해주세요.")

if __name__ == "__main__":
    main()
