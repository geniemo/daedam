# 배포 — Azure VM

대상: 2 vCPU · 7.7 GB(여유 4.4 GB) · 51 GB · Ubuntu 24.04.
프로세스 하나가 API와 프론트를 같이 서빙하고, Caddy가 HTTPS를 맡는다.

```
브라우저 ──HTTPS──▶ Caddy(:443) ──▶ uvicorn(127.0.0.1:8000) ──▶ SQLite + data/
                                          │
                                          └─ web/dist/ 를 같은 오리진에서
```

**워커는 하나다.** 늘리면 깨진다 — 필러 커넥션 레지스트리와 준비·평가 진행
상태가 프로세스 메모리에 있어서, 콜백이 A 워커에서 돌고 소켓이 B 워커에 있으면
필러가 안 나간다. 기동 시 마이그레이션이 안전한 것도 프로세스가 하나라서다.

## 1. 준비

```bash
sudo apt update && sudo apt install -y git caddy
curl -LsSf https://astral.sh/uv/install.sh | sh          # uv
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
```

## 2. 코드와 의존성

```bash
git clone <저장소> ~/daedam && cd ~/daedam

cd server && uv sync                  # 로컬 임베딩은 안 받는다 — 아래 참고
cd ../web && npm ci && npm run build  # dist/ 를 서버가 서빙한다
```

`uv sync`만으로 충분하다. 로컬 임베딩(`sentence-transformers`+torch, 수 GB)은
선택 의존성이라 안 깔린다 — 기본이 Gemini 임베딩 API이기 때문이다. 이 VM에서
로컬 모델을 돌리면 인덱스 하나에 50초가 걸린다(2 vCPU 실측).

## 3. 환경변수

`server/.env`를 만든다(`.env.example`이 원본). 로컬과 다른 값만:

> 유닛 파일이 `DAEDAM_ENV=production`을 준다. 운영 모드에서는 아래 값이 하나라도
> 빠지면 서버가 **기동을 거부**하고 빠진 항목을 `운영 설정 누락: …` 로그로
> 남긴다(`daedam/server/preflight.py`). 유닛 없이 손으로 띄울 때는
> `DAEDAM_ENV=production`을 직접 export한다 — 안 주면 기본이 production이라
> 결과는 같다.

```bash
SERVER_BASE_URL=https://{도메인}     # OAuth 콜백이 여기에 /api/auth/... 를 붙인다
APP_BASE_URL=                        # 비운다 — 프론트가 같은 오리진이다
COOKIE_SECURE=1                      # HTTPS이므로
SESSION_SECRET=<고정값>              # 비우면 재시작마다 전원 로그아웃
INTERVIEW_PROFILE=full               # 제품 길이. 시연용은 demo
RESEARCH_MODE=live
SEARCH_EMBEDDINGS=gemini
```

`SESSION_SECRET` 생성:
```bash
cd ~/daedam/server && uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 4. 카카오 콘솔

**[앱] > [플랫폼 키] > [REST API 키] > [Redirect URI]**에 배포 주소를
**추가**한다(로컬 것은 지우지 말 것 — 여러 개 등록된다).

```
https://{도메인}/api/auth/kakao/callback
```

## 5. 서비스 등록

```bash
sudo cp ~/daedam/deploy/daedam.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now daedam
sudo journalctl -u daedam -f
```

기동 로그에서 셋을 확인한다.

```
INFO  daedam.knowledge.embedding: 의미 검색 임베더: gemini
INFO  daedam.server.app: 로그인: kakao
INFO  daedam.server.app: 프론트를 같은 오리진에서 서빙합니다
```

`.env`가 안 읽혔거나 값이 빠졌으면 뜨지 않는다 — `운영 설정 누락: …` 줄이 이유다.

## 6. HTTPS

`deploy/Caddyfile`의 `{도메인}`을 바꿔 넣고:

```bash
sudo cp ~/daedam/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

DNS A 레코드가 VM 공인 IP를 가리키고 있어야 하고, **80·443이 열려 있어야**
한다(Azure 네트워크 보안 그룹). Caddy가 인증서를 자동으로 받는다.

## 갱신

```bash
cd ~/daedam && git pull
cd server && uv sync
cd ../web && npm ci && npm run build
sudo systemctl restart daedam        # 마이그레이션은 기동 시 자동
```

**면접이 도는 중에 재시작하지 말 것.** 대화 세션은 DB에 있어 살아남지만
WebSocket이 끊긴다. 프론트가 재접속하므로 복구는 되지만 몇 초 끊긴다.

## 지켜볼 것

| | 명령 | 왜 |
|---|---|---|
| 디스크 | `du -sh ~/daedam/server/data` | 20분 면접 한 판이 73 MB(pcm+wav). 51 GB면 약 700판 |
| 메모리 | `systemctl status daedam` | 정상 약 180 MB. 크게 늘면 새는 것이다 |
| 면접 원가 | `journalctl -u daedam \| grep '토큰 사용'` | 크레딧 가격을 확정할 근거 |
| 크레딧 | `journalctl -u daedam \| grep 크레딧` | 지급·차감·환불이 의도대로 도는지 |

## 아직 안 한 것

- **PostgreSQL** — 동시 면접이 늘어 SQLite 쓰기 경합이 보이면 `DATABASE_URL`만
  바꾼다. 드라이버(`asyncpg`)는 이미 들어 있다
- **워커 다중화** — 위의 프로세스 메모리 상태를 밖으로 빼야 가능하다
- **녹음 보관 정책** — 지금은 무한히 쌓인다. `mic.pcm`은 `mic.wav`를 만든 뒤
  지워도 되고(절반), 오래된 녹음을 정리하는 기준도 필요하다
- **백업** — `data/` 하나만 챙기면 된다(DB 파일과 녹음이 다 그 안에 있다)
