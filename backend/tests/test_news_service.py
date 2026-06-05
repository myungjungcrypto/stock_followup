from app.models import Stock, TrackingItem
from app.services.news import NewsService


def test_korean_market_uses_kr_google_news_locale():
    service = NewsService()

    locale = service._locale("한국")

    assert locale == {"hl": "ko", "gl": "KR", "ceid": "KR:ko"}


def test_query_deduplicates_company_name_and_ticker():
    service = NewsService()
    stock = Stock(ticker="이엔에프테크놀로지", company_name="이엔에프테크놀로지", market="한국")
    item = TrackingItem(label="실적", query="이엔에프테크놀로지 실적 영업이익", stock_id=1)

    query = service._build_query(stock, item)

    assert query.startswith("이엔에프테크놀로지 실적")
    assert query.count("이엔에프테크놀로지") == 1


def test_clean_text_removes_html_and_entities():
    service = NewsService()

    cleaned = service._clean_text("이엔에프 <b>증가</b> &nbsp;&amp; 개선")

    assert cleaned == "이엔에프 증가 & 개선"


def test_relevance_accepts_company_alias():
    service = NewsService()
    stock = Stock(ticker="이엔에프테크놀로지", company_name="이엔에프테크놀로지", market="한국")
    item = TrackingItem(label="미국 현지 공급망", query="이엔에프테크놀로지 미국 공급망", stock_id=1)

    score, terms = service.relevance(
        stock,
        item,
        {"title": "이엔에프, 삼성전자 美 공장에 반도체 소재 공급", "summary": ""},
    )

    assert score >= 0.6
    assert "이엔에프" in terms


def test_relevance_rejects_other_stock_news_with_sector_terms():
    service = NewsService()
    stock = Stock(ticker="이엔에프테크놀로지", company_name="이엔에프테크놀로지", market="한국")
    item = TrackingItem(label="반도체·디스플레이 소재 업황", query="이엔에프테크놀로지 반도체 소재 업황", stock_id=1)

    score, terms = service.relevance(
        stock,
        item,
        {"title": "원익QnC, 반도체 소재 업황 수혜 기대", "summary": ""},
    )

    assert score < 0.6
    assert "이엔에프테크놀로지" not in terms
