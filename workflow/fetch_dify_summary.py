import os
import requests
import feedparser
from datetime import datetime
import re

# ----------------------------
# 설정값 (필요시 수정)
# ----------------------------

# 채널 리스트: 채널명 -> 채널 URL 매핑
CHANNELS = {
    "JoCoding": "https://www.youtube.com/@jocoding",
    "Mr.5PM": "https://www.youtube.com/@mr.5pm",
    "CitizenDev": "https://www.youtube.com/@citizendev9c",
    "AI Adjunct": "https://www.youtube.com/@aiadjunct",
    "AI Korea Community": "https://www.youtube.com/@AIKoreaCommunity",
    "TeddyNote": "https://www.youtube.com/@teddynote"
}

# 환경변수: GitHub Actions에서 secrets에 등록 필요
DIFY_API_KEY = os.getenv("DIFY_API_KEY")
DIFY_WORKFLOW_ID = os.getenv("DIFY_WORKFLOW_ID")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")

# Dify API Endpoint
DIFY_API_URL = f"https://api.dify.ai/v1/workflows/{DIFY_WORKFLOW_ID}/execute"

# ----------------------------
# 함수 정의
# ----------------------------

def sanitize_filename(name):
    """파일명에서 사용할 수 없는 문자 제거"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def resolve_channel_id(youtube_url):
    """@사용자명 형태의 유튜브 URL을 입력받아 채널 ID를 추출합니다."""
    response = requests.get(youtube_url)
    if response.status_code != 200:
        raise Exception(f"유튜브 페이지 접근 실패: {youtube_url}")

    html = response.text
    match = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', html)
    if match:
        return match.group(1)
    else:
        raise Exception(f"채널 ID를 찾을 수 없습니다: {youtube_url}")

def get_today_videos(youtube_url):
    """오늘 업로드된 유튜브 영상 목록 가져오기"""
    channel_id = resolve_channel_id(youtube_url)
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    feed = feedparser.parse(feed_url)
    today = datetime.utcnow().date()

    today_videos = []
    for entry in feed.entries:
        published_date = datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%S%z').date()
        if published_date == today:
            today_videos.append({
                'title': entry.title,
                'url': entry.link,
                'published': entry.published
            })
    return today_videos

def summarize_video(youtube_url):
    """Dify Workflow 호출하여 요약 생성"""
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "inputs": {
            "youtube_url": youtube_url
        }
    }
    response = requests.post(DIFY_API_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["outputs"]

def save_summary(channel_name, video_title, youtube_url, summary_data):
    """Structured Output JSON을 Markdown 파일로 저장"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    sanitized_title = sanitize_filename(video_title)
    filename = f"{date_str}-{channel_name}-{sanitized_title}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    summary_text = summary_data.get("summary", "")
    keywords_list = summary_data.get("keywords", [])
    keywords_text = ", ".join(keywords_list)

    content = f"""# YouTube 영상 요약

- **링크**: {youtube_url}
- **요약 날짜**: {date_str}

## 📋 요약 내용

{summary_text}

## 🔑 주요 키워드
{keywords_text}
"""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Saved: {filepath}")

# ----------------------------
# 메인 실행부
# ----------------------------

def main():
    if not DIFY_API_KEY or not DIFY_WORKFLOW_ID or not OUTPUT_DIR:
        raise EnvironmentError("환경변수(DIFY_API_KEY, DIFY_WORKFLOW_ID, OUTPUT_DIR)가 설정되어 있지 않습니다.")

    for channel_name, channel_url in CHANNELS.items():
        try:
            today_videos = get_today_videos(channel_url)
            if not today_videos:
                print(f"[INFO] 오늘 {channel_name} 채널에 새 영상 없음.")
                continue

            for video in today_videos:
                try:
                    print(f"[INFO] 요약 시작: {video['title']} ({channel_name})")
                    summary_data = summarize_video(video['url'])
                    save_summary(channel_name, video['title'], video['url'], summary_data)
                except Exception as e:
                    print(f"[ERROR] 영상 요약 실패: {video['title']} - {str(e)}")
        except Exception as e:
            print(f"[ERROR] 채널 처리 실패: {channel_name} - {str(e)}")

if __name__ == "__main__":
    main()
