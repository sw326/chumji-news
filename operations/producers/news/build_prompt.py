#!/usr/bin/env python3
"""Build the exact prompt used by the surviving production news cron."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"

INTRO = {
    "morning": "너는 뉴스 브리핑 전문 에이전트다. 아래 [플레이북]과 [템플릿]을 정확히 따라, [원천 기사 JSON]을 한국어 아침 뉴스 브리핑으로 정리해라. 본문만 출력, 서론·결론·메타멘트 절대 금지.",
    "it": "너는 뉴스 브리핑 전문 에이전트다. 아래 [플레이북]과 [템플릿]을 정확히 따라, [원천 기사 JSON]을 한국어 IT/테크 브리핑으로 정리해라. 본문만 출력, 서론·결론·메타멘트 절대 금지.",
    "trend": "너는 뉴스 브리핑 전문 에이전트다. 아래 [플레이북]과 [템플릿]을 정확히 따라, [원천 기사 JSON]을 한국어 IT 트렌드 브리핑으로 정리해라. 본문만 출력, 서론·결론·메타멘트 절대 금지.",
}

CONSTRAINTS = {
    "morning": """- 첫 줄은 반드시: 📰 {date_kor} 아침 뉴스 브리핑
- 출처 링크는 기사의 url 필드 그대로 사용. 홈페이지/섹션 URL 사용 금지.
- 해외 3-4건, 보수 2-3건, 진보 2-3건. 포토/영상/광고/중복 제외.
- 증시 섹션: 이 실행에는 실시간 주식 데이터 없음. 섹션 전체 생략.
- 핫이슈 TOP 3: 수집된 기사 중 반복·중요도 높은 이슈 3개.
- 출력은 웹 상세 페이지 (chumji-news.vercel.app) 에 마크다운으로 렌더링된다. 볼드는 **text** (double asterisk), 링크는 [text](url) 표준 마크다운. 이스케이프 불필요.""",
    "it": """- 첫 줄은 반드시: 💻 {date_kor} IT/테크 브리핑
- 출처 링크는 기사의 url 필드 그대로 사용. 홈페이지/섹션 URL 사용 금지.
- 해외 4-5건, 국내 3-4건. 포토/영상/광고/중복 제외. 각 뉴스에 \"왜 중요한지\" 개발자 관점 한마디 포함.
- 테크 핫토픽 TOP 3: 수집된 기사 중 기술 업계에서 반복·중요도 높은 토픽 3개.
- 출력은 웹 상세 페이지 (chumji-news.vercel.app) 에 마크다운으로 렌더링된다. 볼드는 **text** (double asterisk), 링크는 [text](url) 표준 마크다운. 이스케이프 불필요.""",
    "trend": """- 첫 줄은 반드시: 🔥 {date_kor} IT 트렌드 브리핑
- articles 배열에는 코드가 선별한 selected=true 항목만 있다. 모델이 항목을 추가·삭제·재선정하지 말고 모든 항목을 정확히 한 번 요약한다.
- 목표 건수를 채우지 않는다. 항목이 없는 섹션은 생략한다.
- 출처 링크는 article_url과 discussion_url 필드만 사용한다. 홈페이지/섹션 URL 사용 금지.
- 출력은 웹 상세 페이지 (chumji-news.vercel.app) 에 마크다운으로 렌더링된다. 볼드는 **text** (double asterisk), 링크는 [text](url) 표준 마크다운. 이스케이프 불필요.

[근거 계약]
- 원천 JSON의 title, summary, metrics만 사실 근거로 사용한다. URL·도메인·고유명만 보고 정체성·산업·기능을 추측하지 않는다.
- source_metrics_repository_description은 GitHub Trending 페이지의 저장소 이름·설명과 관측된 언어·오늘 스타 증가·일일 순위만 표현한다. 총 스타 수, 평가, 성능, 인기 이유를 추측하지 않는다.
- official_metrics_title_only_no_comment_text는 HN 공식 API의 점수·댓글 수에 근거해 수치화된 화제 규모만 표현할 수 있다. source_metrics_title_only_no_comment_text는 Lobsters 공개 JSON의 점수·댓글 수·태그에 근거해 Lobsters 안의 화제 규모와 분류만 표현할 수 있다. 두 경우 모두 댓글 원문은 수집하지 않았으므로 반응의 내용·방향·평가를 만들지 않는다.
- feed_content_no_engagement와 title_only_no_engagement에는 신뢰 가능한 참여 지표가 없다. 확산, 화제, 열광, 반응이 많다는 표현을 쓰지 않는다.
- 지표 없는 제목 자체에 viral, gains momentum, 뜨거운 반응, 화제 같은 수식어가 있어도 반복·번역하지 말고 사건·제품·주제의 핵심만 중립적으로 전달한다.
- summary가 비어 있으면 제목에 명시된 내용 이상으로 설명을 확장하지 않는다. OpenLogi처럼 불투명한 고유명도 의미를 추측하지 말고 제목과 관측 수치만 전달한다.
- 다른 항목에 같은 이름의 설명이 있더라도 항목끼리 근거를 섞지 않는다.
- 출력 소스 순서는 GitHub Trending, GeekNews, Hacker News, Lobsters, Reddit, ZDNet Korea로 고정한다. Product Hunt와 핫딜은 입력에 없으며 추가하지 않는다.
- Hacker News, Lobsters, Reddit은 article_url 원문 링크와 discussion_url 댓글·토론 링크를 모두 표시한다. Reddit·GeekNews의 community_submission을 근거 없는 커뮤니티 화제로 바꾸지 않는다.
- selection_policy.hacker_news.temporary_threshold=true이며 현재 36시간·50점 또는 댓글 20개 기준은 임시값이다. selection_policy.lobsters.temporary_threshold=true이며 현재 48시간·30점 또는 댓글 10개 기준도 임시값이다. 브리핑 본문에는 정책 설명을 덧붙이지 않는다.""",
}

TEMPLATE = {"morning": "morning-news.md", "it": "it-tech.md", "trend": "trend.md"}


def build_prompt(profile: str, date_kor: str, source_json: str) -> str:
    # Validate without reserializing: production passes collector bytes verbatim.
    json.loads(source_json)
    playbook = (PROMPTS / "playbook.md").read_text().rstrip("\n")
    template = (PROMPTS / TEMPLATE[profile]).read_text().rstrip("\n")
    return (
        f"{INTRO[profile]}\n\n[플레이북]\n{playbook}\n\n[템플릿]\n{template}\n\n"
        f"[제약]\n{CONSTRAINTS[profile].format(date_kor=date_kor)}\n\n[원천 기사 JSON]\n{source_json}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(INTRO))
    parser.add_argument("--date-kor", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(build_prompt(args.profile, args.date_kor, Path(args.input).read_text()))


if __name__ == "__main__":
    main()
