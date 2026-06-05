# Stock Follow-Up

주식별 투자 논리와 사용자가 입력한 기사/메모를 바탕으로, 앞으로 팔로우업해야 할 정보를 추출하고 새 뉴스가 나왔을 때 행동 판단과 텔레그램 알림까지 이어주는 대시보드입니다.

## 현재 MVP

- 종목 watchlist 추가
- 종목별 thesis 저장
- 기사, 글, 메모, URL 입력
- AI 또는 오프라인 fallback으로 팔로우업 항목 자동 추출
- Google News RSS 기반 수동/주기적 스캔
- 새 이벤트에 대한 행동 판단 생성
- 중요 판단에 대한 Telegram 알림 기록 및 발송 시도
- EC2 배포를 위한 Docker Compose 구성

## 구조

```text
backend/
  app/
    main.py              FastAPI 엔트리포인트
    models.py            SQLAlchemy 모델
    services/
      ai.py              추적 항목 추출, 이벤트 판단
      news.py            뉴스 RSS 검색
      monitor.py         스캔/판단/알림 오케스트레이션
      telegram.py        텔레그램 발송
      scheduler.py       주기 실행
frontend/
  src/
    App.tsx              대시보드 UI
    api.ts               API 클라이언트
docker-compose.yml       Postgres + backend + frontend
```

## 로컬 실행

```bash
cp .env.example .env
docker compose up --build
```

브라우저에서 `http://localhost:5173`을 엽니다.

## 개발 모드

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/python -m pytest
env SCHEDULER_ENABLED=false ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

다른 터미널에서:

```bash
cd frontend
npm install
npm run dev
npm run build
```

## 환경변수

`.env.example`을 `.env`로 복사한 뒤 필요한 값을 채웁니다.

- `OPENAI_API_KEY`: 있으면 AI 분석 사용, 없으면 fallback 분석 사용
- `OPENAI_MODEL`: 사용할 모델명
- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 알림 받을 채팅 ID
- `DATABASE_URL`: Docker Compose에서는 Postgres URL 사용

## EC2 배포 메모

1. EC2에 Docker와 Docker Compose를 설치합니다.
2. 이 저장소를 clone합니다.
3. `.env`를 생성하고 API 키와 텔레그램 값을 채웁니다.
4. `docker compose up -d --build`를 실행합니다.
5. 보안 그룹에서 5173 또는 reverse proxy 포트를 엽니다.

운영에서는 `Caddy` 또는 `Nginx`를 앞에 두고 HTTPS를 붙이는 구성이 좋습니다. 초기에는 5173 포트를 제한된 IP에서만 열고, 안정화 후 도메인과 HTTPS를 붙이는 식으로 가면 됩니다.

## 다음 구현 후보

- 로그인과 사용자별 데이터 분리
- SEC/전자공시/실적 캘린더 데이터 소스 추가
- 가격/거래량 이상 감지
- 추적 항목별 enable/disable 및 민감도 조정
- 알림 정책 편집 UI
- Alembic 마이그레이션 도입
