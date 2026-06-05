from io import BytesIO
from zipfile import ZipFile

from app.models import Stock
from app.services.dart import DART_DISCLOSURE_VIEW_URL, DartService


def _corp_code_zip() -> bytes:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>삼성전자</corp_name>
    <corp_eng_name>SAMSUNG ELECTRONICS CO,.LTD</corp_eng_name>
    <stock_code>005930</stock_code>
    <modify_date>20240101</modify_date>
  </list>
  <list>
    <corp_code>01234567</corp_code>
    <corp_name>이엔에프테크놀로지</corp_name>
    <corp_eng_name>ENF TECHNOLOGY</corp_eng_name>
    <stock_code>102710</stock_code>
    <modify_date>20240101</modify_date>
  </list>
</result>
"""
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", xml)
    return buffer.getvalue()


def test_parse_corp_code_zip_and_match_by_stock_code():
    service = DartService()
    rows = service._parse_corp_code_zip(_corp_code_zip())
    stock = Stock(ticker="102710", stock_code="102710", company_name="이엔에프테크놀로지", market="한국")

    corp_code = service._find_corp_code(rows, stock)

    assert corp_code == "01234567"


def test_find_corp_code_falls_back_to_company_name():
    service = DartService()
    rows = service._parse_corp_code_zip(_corp_code_zip())
    stock = Stock(ticker="이엔에프테크놀로지", company_name="이엔에프테크놀로지", market="한국")

    corp_code = service._find_corp_code(rows, stock)

    assert corp_code == "01234567"


def test_disclosure_payload_becomes_event():
    service = DartService()
    event = service._to_event(
        {
            "corp_code": "01234567",
            "corp_name": "이엔에프테크놀로지",
            "stock_code": "102710",
            "report_nm": "분기보고서",
            "rcept_no": "20260501000123",
            "flr_nm": "이엔에프테크놀로지",
            "rcept_dt": "20260501",
            "rm": "K",
        }
    )

    assert event["title"] == "[DART] 분기보고서"
    assert event["source"] == "opendart"
    assert event["url"] == DART_DISCLOSURE_VIEW_URL.format(rcept_no="20260501000123")
    assert event["published_at"].year == 2026
    assert event["relevance_score"] == 1.0
