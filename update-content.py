#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index.html 의 <!-- AUTO:... --> 구역을 유튜브 채널 / 티스토리 블로그에서
자동으로 채워 넣는 스크립트.

  · 대표 영상  = 채널 '인기순' 1위 영상을 주제(역사/과학/경제)별로 선정
  · 대표 글    = 블로그 최신 글
  · 최신 목록  = 유튜브 최신 영상 3개 + 블로그 최신 글 3개
  · 초저녁야담 = 자매 채널 최신 에피소드 3개 (쇼츠 제외)

실행:  python update-content.py       (또는 update-content.bat 더블클릭)
의존성 없음 — 파이썬 표준 라이브러리만 사용합니다.
"""

import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# ────────────────────────────────── 설정 ──────────────────────────────────

HANDLE     = "@ChronosArche_ruvinpapa"
CHANNEL_ID = "UCBeVZJex5unVywCxnDEYwrQ"
BLOG       = "https://ruvinfather.com"

# 자매 채널 '초저녁야담' — 조선 야담 수면 오디오북 (섹션 #yadam)
YADAM_CHANNEL_ID = "UCoEeRkwnzuHWwGnOQz1RUFg"
LATEST_YADAM     = 3       # 야담 섹션에 보여줄 최신 에피소드 수 (쇼츠 제외)

LATEST_VIDEOS = 3          # '최신 영상' 에 몇 개까지 보여줄지
LATEST_POSTS  = 3          # '블로그 최신 글' 에 몇 개까지 보여줄지
INCLUDE_SHORTS = False     # True 로 바꾸면 최신 목록에 쇼츠도 포함
MAX_VIEW_LOOKUPS = 40      # 조회수를 확인할 최근 영상 편수 (많을수록 느려집니다)

# 특정 영상을 대표로 '고정'하고 싶을 때만 영상 ID를 적습니다. (예: "doIzLpDyp4M")
# None 이면 인기순 1위가 자동으로 올라갑니다.
PIN = {"history": None, "science": None, "economy": None}
# 블로그 대표 글도 고정하려면 글 주소를 그대로 붙여넣으세요. None 이면 최신 글.
PIN_POST = None

# 제목에 아래 단어가 들어 있으면 해당 주제로 분류합니다. 자유롭게 추가하세요.
KEYWORDS = {
    "history": ["역사", "왕", "황제", "전쟁", "전투", "제국", "문명", "조선", "고구려",
                "백제", "신라", "고려", "로마", "몽골", "안시성", "정예군", "장군",
                "혁명", "왕조", "유물", "고대", "중세", "근대", "식민", "독립", "성벽"],
    "science": ["과학", "우주", "광년", "외계", "행성", "은하", "물리", "화학", "생물",
                "유전", "자기장", "블랙홀", "입자", "실험", "진화", "기후", "빙하",
                "폭발", "운석", "미생물", "양자", "에너지", "백신", "지구", "얼음",
                "발견", "남극", "북극", "화산", "지진", "공룡", "심해", "인공지능"],
    "economy": ["경제", "금융", "투자", "주식", "ETF", "배당", "금리", "환율", "인플레",
                "자산", "부동산", "연금", "세금", "달러", "증시", "자본", "버블",
                "통화", "채권", "커버드콜", "IRP", "ISA", "퇴직", "파이어족", "노후"],
}

TOPIC_LABEL = {"history": "역사", "science": "과학", "economy": "경제"}
TOPIC_CHIP  = {"history": ("史", "surface-peach"),
               "science": ("科", "surface-mint"),
               "economy": ("經", "surface-yellow")}

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "index.html")
BACKUP = os.path.join(HERE, "index.bak.html")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
KST = timezone(timedelta(hours=9))

ARROW = ('<span class="arrow" aria-hidden="true">\n'
         '              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" focusable="false">\n'
         '                <path d="M4.75 12h14.5"/><path d="m13.5 6.25 5.75 5.75-5.75 5.75"/>\n'
         '              </svg>\n'
         '            </span>')


# ───────────────────────────────── 수집 ──────────────────────────────────

def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def channel_videos():
    """채널 '동영상' 탭 목록 (쇼츠 제외). 유튜브가 정렬을 서버에서만 바꿔 주므로
    여기서는 목록만 받아오고, 인기 순위는 아래 with_view_counts() 로 직접 매긴다."""
    page = get("https://www.youtube.com/%s/videos" % HANDLE)
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    if not m:
        raise RuntimeError("유튜브 페이지 구조가 바뀌어 영상 목록을 읽지 못했습니다.")

    found = []

    def walk(node):
        if isinstance(node, dict):
            if "lockupViewModel" in node:
                found.append(node["lockupViewModel"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(m.group(1)))

    out, seen = [], set()
    for it in found:
        vid = it.get("contentId")
        title = ((it.get("metadata", {}).get("lockupMetadataViewModel", {})
                    .get("title")) or {}).get("content")
        if not vid or not title or vid in seen:
            continue
        seen.add(vid)
        out.append({"id": vid, "title": title, "views": 0, "views_text": "",
                    "url": "https://www.youtube.com/watch?v=%s" % vid})
    return out


def with_view_counts(videos):
    """영상 페이지에서 조회수를 읽어 채운 뒤 조회수 많은 순으로 정렬한다."""
    for v in videos[:MAX_VIEW_LOOKUPS]:
        try:
            page = get(v["url"])
            m = re.search(r'"viewCount":"(\d+)"', page)
            if m:
                v["views"] = int(m.group(1))
                v["views_text"] = "조회수 %s회" % format(v["views"], ",")
        except Exception:                      # 한 편 실패해도 전체는 계속 진행
            pass
    return sorted(videos, key=lambda v: v["views"], reverse=True)


# ─────────────────────── 유튜브 공식 API (키가 있을 때만) ───────────────────────
# 환경변수 YOUTUBE_API_KEY 가 있으면 공식 API 로 조회수를 읽습니다.
# 깃허브 서버처럼 일반 접속으로는 조회수를 못 읽는 환경에서 쓰려고 만든 경로입니다.

API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()


def api_get(path, **params):
    params["key"] = API_KEY
    url = "https://www.googleapis.com/youtube/v3/%s?%s" % (
        path, urllib.parse.urlencode(params))
    return json.loads(get(url))


def iso_seconds(text):
    """PT1H2M3S 형태의 재생시간을 초로 바꾼다."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def api_videos():
    """공식 API 로 업로드 목록과 조회수를 가져온다 (쇼츠 제외, 조회수 많은 순)."""
    uploads = "UU" + CHANNEL_ID[2:]          # 업로드 재생목록 ID 규칙
    ids, token = [], None
    while len(ids) < MAX_VIEW_LOOKUPS:
        extra = {"pageToken": token} if token else {}
        data = api_get("playlistItems", part="contentDetails",
                       playlistId=uploads, maxResults=50, **extra)
        ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])]
        token = data.get("nextPageToken")
        if not token:
            break

    ids = ids[:MAX_VIEW_LOOKUPS]
    out = []
    for i in range(0, len(ids), 50):
        data = api_get("videos", part="snippet,statistics,contentDetails",
                       id=",".join(ids[i:i + 50]), maxResults=50)
        for it in data.get("items", []):
            if iso_seconds(it.get("contentDetails", {}).get("duration")) <= 60:
                continue                      # 쇼츠는 대표 후보에서 제외
            views = int(it.get("statistics", {}).get("viewCount", 0))
            out.append({"id": it["id"],
                        "title": it["snippet"]["title"],
                        "views": views,
                        "views_text": "조회수 %s회" % format(views, ","),
                        "url": "https://www.youtube.com/watch?v=%s" % it["id"]})
    if not out:
        raise RuntimeError("API 응답에 영상이 없습니다.")
    return sorted(out, key=lambda v: v["views"], reverse=True)


def collect_videos():
    """상황에 맞는 방법으로 영상 목록과 조회수를 가져온다."""
    if API_KEY:
        print("· 유튜브 공식 API 로 영상 목록과 조회수 읽는 중...")
        try:
            return api_videos()
        except Exception as e:                # 키가 잘못됐거나 할당량 초과일 때
            print("  (공식 API 실패: %s)" % e)
            print("  일반 방식으로 대신 시도합니다.")
    print("· 유튜브 영상 목록 읽는 중...")
    videos = channel_videos()
    print("· 조회수 확인 중... (영상 %d편)" % min(len(videos), MAX_VIEW_LOOKUPS))
    return with_view_counts(videos)


def feed_videos(channel_id=CHANNEL_ID):
    """채널 RSS — 업로드 최신순 (쇼츠 포함)."""
    xml = get("https://www.youtube.com/feeds/videos.xml?channel_id=%s" % channel_id)
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    out = []
    for e in ET.fromstring(xml).findall("a:entry", ns):
        vid = e.findtext("yt:videoId", "", ns)
        title = html.unescape(e.findtext("a:title", "", ns))
        pub = e.findtext("a:published", "", ns)
        when = datetime.fromisoformat(pub).astimezone(KST) if pub else None
        out.append({"id": vid, "title": title, "when": when,
                    "url": "https://www.youtube.com/watch?v=%s" % vid})
    return out


def is_short(vid):
    """/shorts/ 주소가 /watch 로 넘어가지 않고 그대로 열리면 쇼츠다.
    확인에 실패하면 일반 영상으로 본다 (목록에서 빠지는 것보다 낫다)."""
    try:
        req = urllib.request.Request("https://www.youtube.com/shorts/%s" % vid,
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return "/shorts/" in r.geturl()
    except Exception:
        return False


def yadam_episodes():
    """초저녁야담 최신 에피소드 (쇼츠 제외)."""
    out = []
    for v in feed_videos(YADAM_CHANNEL_ID):
        if len(out) >= LATEST_YADAM:
            break
        if not is_short(v["id"]):
            # '… / 야담 옛날이야기 민담 수면동화' 같은 검색용 꼬리는 떼어 낸다
            v["title"] = re.split(r"\s+/\s+|\s*\|\s*", v["title"])[0].strip()
            out.append(v)
    return out


def blog_posts():
    """티스토리 RSS — 최신순."""
    xml = get(BLOG.rstrip("/") + "/rss")
    out = []
    for it in ET.fromstring(xml).findall("./channel/item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        raw = it.findtext("pubDate")
        try:
            when = parsedate_to_datetime(raw).astimezone(KST) if raw else None
        except (TypeError, ValueError):
            when = None
        if title and link:
            out.append({"title": title, "url": link, "when": when})
    return out


# ──────────────────────────────── 선정 ───────────────────────────────────

def topic_of(title):
    """제목에 등장한 키워드 수가 가장 많은 주제를 고른다. 하나도 없으면 None."""
    score = {t: sum(1 for k in ws if k.lower() in title.lower())
             for t, ws in KEYWORDS.items()}
    best = max(score, key=score.get)
    return best if score[best] else None


def pick_videos(popular):
    """주제별 대표 영상 = 그 주제 영상 중 조회수 1위."""
    picks = {}
    for v in popular:                       # popular 는 이미 인기순
        t = topic_of(v["title"])
        if t and t not in picks:
            picks[t] = v
    for t, vid in PIN.items():              # 고정 설정이 있으면 그것이 우선
        if vid:
            forced = next((v for v in popular if v["id"] == vid), None)
            if forced:
                picks[t] = forced
    return picks


def short_title(title, limit=34):
    """프래그먼트 행에 들어갈 짧은 제목."""
    head = re.split(r"\s*[—|]\s*|:\s|\s-\s", title)[0].strip()
    return head if len(head) <= limit else head[:limit - 1].rstrip() + "…"


# ──────────────────────────────── 렌더 ───────────────────────────────────

def esc(s):
    return html.escape(s, quote=True)


def render_pick(label, item):
    return ('        <p class="pick">\n'
            '          <span class="k">%s</span>\n'
            '          <a class="text-link" href="%s" target="_blank" rel="noopener">\n'
            '            %s\n'
            '            %s\n'
            '          </a>\n'
            '        </p>' % (esc(label), esc(item["url"]), esc(item["title"]), ARROW))


def render_rows(items):
    if not items:
        return '      <p class="feed-empty">아직 표시할 항목이 없습니다.</p>'
    rows = []
    for it in items:
        when = it["when"].strftime("%m.%d") if it.get("when") else ""
        rows.append('      <div class="feed-row">\n'
                    '        <a class="feed-link" href="%s" target="_blank" rel="noopener">%s</a>\n'
                    '        <span class="date">%s</span>\n'
                    '      </div>' % (esc(it["url"]), esc(it["title"]), esc(when)))
    return "\n".join(rows)


def render_frag(entries):
    rows = []
    for topic, title, meta in entries:
        chip, surface = TOPIC_CHIP[topic]
        rows.append('        <div class="frag-row">\n'
                    '          <span class="frag-chip %s">%s</span>\n'
                    '          <strong>%s</strong>\n'
                    '          <span class="meta">%s</span>\n'
                    '        </div>' % (surface, chip, esc(title), esc(meta)))
    return "\n".join(rows)


def replace_block(doc, key, body):
    open_, close = "<!-- AUTO:%s -->" % key, "<!-- /AUTO:%s -->" % key
    i, j = doc.find(open_), doc.find(close)
    if i < 0 or j < 0:
        raise RuntimeError("index.html 에서 %s 구역을 찾지 못했습니다." % key)
    nl = chr(10)
    indent = doc[doc.rfind(nl, 0, j) + 1:j]          # 닫는 주석의 들여쓰기 유지
    return doc[:i + len(open_)] + nl + body + nl + indent + doc[j:]


# ───────────────────────────────── 실행 ──────────────────────────────────

def current_block(doc, key):
    """index.html 에 지금 들어 있는 구역 내용을 그대로 돌려준다."""
    open_, close = "<!-- AUTO:%s -->" % key, "<!-- /AUTO:%s -->" % key
    i, j = doc.find(open_), doc.find(close)
    if i < 0 or j < 0:
        return ""
    return doc[i + len(open_):j].strip(chr(10)).rstrip()


def video_pick_only(block):
    """구역 안에서 '대표 영상' 줄만 잘라낸다. 없으면 빈 문자열."""
    i = block.find('<span class="k">대표 영상')
    if i < 0:
        return ""
    start = block.rfind('<p class="pick">', 0, i)
    end = block.find("</p>", i)
    if start < 0 or end < 0:
        return ""
    line_start = block.rfind(chr(10), 0, start) + 1
    return block[line_start:end + len("</p>")]


def main():
    popular = collect_videos()
    print("· 유튜브 최신 업로드 읽는 중...")
    feed = feed_videos()
    print("· 블로그 최신 글 읽는 중...")
    posts = blog_posts()
    print("· 초저녁야담 최신 에피소드 읽는 중...")
    try:
        yadam = yadam_episodes()
    except Exception as e:                    # 야담 쪽이 실패해도 본 채널 갱신은 계속
        print("  (초저녁야담 읽기 실패: %s — 기존 목록 유지)" % e)
        yadam = None

    if not popular and not feed:
        raise RuntimeError("영상 정보를 하나도 가져오지 못했습니다.")
    if not posts:
        raise RuntimeError("블로그 글을 가져오지 못했습니다.")

    # 유튜브가 조회수를 내주지 않는 환경(깃허브 서버 등)이 있다. 그때는 순위를 매길 수
    # 없으므로 대표 영상은 지금 올라가 있는 것을 그대로 두고 최신 목록만 갱신한다.
    have_views = any(v["views"] for v in popular)

    picks = pick_videos(popular)
    top_post = next((p for p in posts if p["url"] == PIN_POST), posts[0])

    longform = {v["id"] for v in popular}
    latest_videos = [v for v in feed
                     if INCLUDE_SHORTS or v["id"] in longform][:LATEST_VIDEOS]
    latest_posts = posts[:LATEST_POSTS]

    doc = io.open(TARGET, encoding="utf-8").read()

    # 1) 주제 카드의 대표 영상 / 대표 글
    for topic in ("history", "science", "economy"):
        key = "pick-%s" % topic
        blocks = []
        if have_views:
            v = picks.get(topic)
            if v:
                label = "대표 영상 · %s" % v["views_text"] if v["views_text"] else "대표 영상"
                blocks.append(render_pick(label, v))
        else:
            kept = video_pick_only(current_block(doc, key))   # 기존 대표 영상 유지
            if kept:
                blocks.append(kept)
        if topic == "economy":
            blocks.append(render_pick("대표 글", top_post))    # 대표 글은 언제나 최신으로
        if not blocks:
            blocks.append('        <p class="feed-empty">준비 중입니다.</p>')
        doc = replace_block(doc, key, chr(10).join(blocks))

    # 2) 최신 목록
    doc = replace_block(doc, "latest-videos", render_rows(latest_videos))
    doc = replace_block(doc, "latest-posts", render_rows(latest_posts))
    if yadam is not None:
        doc = replace_block(doc, "yadam-videos", render_rows(yadam))

    # 3) 히어로 카드의 세 줄 요약 (대표 영상을 건드리지 않는 날은 그대로 둔다)
    if have_views:
        frag = []
        for topic in ("history", "science"):
            v = picks.get(topic)
            if v:
                frag.append((topic, short_title(v["title"]), TOPIC_LABEL[topic]))
        frag.append(("economy", short_title(top_post["title"]), "경제 · 블로그"))
        doc = replace_block(doc, "frag", render_frag(frag))

    # 4) 갱신 시각
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    doc = doc.replace(
        doc[doc.find("<!-- AUTO:updated -->"):doc.find("<!-- /AUTO:updated -->")],
        "<!-- AUTO:updated -->" + stamp)

    if os.path.exists(TARGET):
        io.open(BACKUP, "w", encoding="utf-8", newline="").write(
            io.open(TARGET, encoding="utf-8").read())
    io.open(TARGET, "w", encoding="utf-8", newline="").write(doc)

    print("")
    print("반영 결과")
    if have_views:
        for topic in ("history", "science", "economy"):
            v = picks.get(topic)
            print("  대표 %s : %s" % (TOPIC_LABEL[topic],
                                      "%s (%s)" % (v["title"], v["views_text"] or "조회수 미확인")
                                      if v else "해당 영상 없음"))
    else:
        print("  대표 영상 : 조회수를 읽지 못해 기존 선정을 그대로 두었습니다.")
    print("  대표 글  : %s" % top_post["title"])
    print("  최신 영상 %d개 / 최신 글 %d개" % (len(latest_videos), len(latest_posts)))
    print("  초저녁야담 %s" % ("%d편" % len(yadam) if yadam is not None else "기존 유지"))
    print("")
    print("완료 — index.html 갱신 (%s), 직전 파일은 index.bak.html 로 보관" % stamp)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                     # noqa: BLE001 - 사용자에게 한 줄로 알린다
        print("\n[실패] %s" % e)
        print("index.html 은 건드리지 않았습니다. 인터넷 연결을 확인하고 다시 실행해 주세요.")
        sys.exit(1)
