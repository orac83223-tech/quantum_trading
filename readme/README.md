# Quantum–Gann Confluence Trader v1

## 🎯 프로젝트 목표

코스피(KOSPI) 및 코스닥(KOSDAQ) 일봉(1D) 기반의 **Quantum–Gann Confluence v1** 전략을 구현한다.
백테스트 → 페이퍼트레이딩 → (선택) 실거래까지 연결 가능한 실행형 파이썬 프로젝트다.

---

## ⚙️ 기술 스택

| 항목 | 선택 |
|---|---|
| Python | 3.11+ |
| 데이터 | `pykrx` (코스피/코스닥 OHLCV) |
| 캐시 | `pyarrow` + Parquet |
| CLI | `typer` |
| 설정 | `config.yaml` + `.env` |
| 테스트 | `pytest` |
| 옵션 | `rich` (터미널 출력) |

의존성은 최소화한다. `pandas`, `numpy`, `pykrx`, `pyarrow`, `typer`, `rich`, `pytest` 이외 라이브러리 추가를 지양한다.

---

## 🗂️ 프로젝트 구조 (목표)

```
trader/
├── __init__.py
├── cli.py                    # typer CLI 진입점
├── config.py                 # config.yaml 로드 + 파라미터 데이터클래스
├── calendar_krx.py           # 거래일 캘린더(주말/휴일 제외)
│
├── data/
│   ├── pykrx_loader.py       # 코스피/코스닥 티커 목록 + OHLCV 수집
│   └── cache.py              # ./data/cache/{ticker}.parquet 읽기/쓰기
│
├── indicators/
│   ├── atr.py                # ATR(14)
│   ├── pivots.py             # Pivot Low(3,3) — t+3 확정 로직
│   ├── so9.py                # Square of 9 레벨 계산
│   └── gann_angle.py         # 1x1 Gann Angle (자동 스케일)
│
├── strategy/
│   ├── qg_confluence_v1.py   # 메인 신호 생성 함수
│   └── ev_gate.py            # Expected Value 필터
│
├── backtest/
│   ├── engine.py             # 이벤트 루프 (다음날 시가 진입)
│   ├── metrics.py            # 승률/PF/MDD/CAGR/avgR 산출
│   └── report.py             # equity curve + trades.csv 출력 등 리포트 총괄
│
├── execution/
│   ├── broker_base.py        # BrokerBase 추상 클래스
│   ├── csv_broker.py         # CsvBroker (주문 파일만 생성)
│   ├── mock_broker.py        # MockBroker (페이퍼 시뮬레이션)
│   ├── risk.py               # 포지션 사이징 + 일일 손실 한도
│   └── portfolio.py          # 오픈 포지션 상태 관리 (JSON Save/Load)
│
├── reporting/
│   ├── html_report.py        # Jinja2 템플릿 렌더링
│   ├── plots.py              # 차트(PNG) 생성 유틸
│   ├── templates/            # base.html, backtest.html, portfolio.html
│   └── assets/               # style.css
│
│
└── utils/
    ├── logging.py            # 로깅 설정
    └── math.py               # 공통 수학 유틸

tests/
├── test_pivots.py            # Pivot look-ahead 방지 검증
├── test_so9.py               # Square of 9 레벨 계산 검증
├── test_time_window.py       # time_ok 계산 검증
└── test_ev_gate.py           # EV gate 계산 검증

data/
└── cache/                    # {ticker}.parquet 자동 생성

config.yaml                   # 전체 파라미터 (아래 참고)
.env.example                  # 민감 정보 템플릿
requirements.txt
README.md
```

---

## 📋 전략 명세: Quantum–Gann Confluence v1

### 1. 유니버스 필터 (일별)

```yaml
# config.yaml
universe:
  market: KOSDAQ
  min_listed_days: 250          # 상장 후 최소 거래일
  min_value_krw: 5_000_000_000  # 최근 60일 평균 거래대금 (기본 50억)
  min_price: 1000               # 최소 종가 (원)
  exclude_list: []              # 수동 제외 종목 (스팩/관리종목 등)
```

- 스팩·ETF·ETN은 exclude_list로 수동 제외 지원 (자동 구분이 어려울 경우)
- 신규상장·유동성 필터는 필수 적용

### 2. 지표 계산

#### ATR(14)

```python
# indicators/atr.py
atr = ATR(period=14)           # Wilder 방식
band = BAND_ATR_MULT * atr     # 기본 BAND_ATR_MULT = 0.25
```

#### Pivot Low (3, 3) — **look-ahead 방지 핵심**

```python
# indicators/pivots.py
# Low[t]가 Low[t-3..t+3] 구간 최저일 때 피벗 로우 후보
# → t+3 이후에만 확정 사용 (그 전 사용 절대 금지)
# → 가장 최근 확정 Pivot Low를 앵커 (P0, t0)로 사용
```

#### Square of 9 (So9) — 앵커 P0 기반

```python
# indicators/so9.py
angles = [45, 90, 135, 180, 270, 360]
k_cycles = [0, 1]

r = sqrt(P0)
for k in k_cycles:
    for angle in angles:
        delta = angle / 360
        upper = (r + k + delta) ** 2
        lower = (r - k - delta) ** 2

# 현재가 기준 → 가장 가까운 하단 레벨 Ls, 상단 레벨 Lr 선택
```

#### Time Window (Subharmonic)

```python
# T_bars = [45, 90, 135, 180, 270, 360]  (거래일 기준)
# time_ok = any(abs((t - t0) - Ti) <= TIME_WINDOW for Ti in T_bars)
# TIME_WINDOW 기본값: 5
```

#### Gann 1×1 Angle (자동 스케일)

```python
# indicators/gann_angle.py
scale_n = 90
price_range = max(High[t-scale_n+1..t]) - min(Low[t-scale_n+1..t])
slope = price_range / scale_n
line_1x1 = P0 + slope * (t - t0)
trend_ok = Close[t] >= line_1x1   # True → 롱 우호
# trend_ok == False: 진입 가능하되 position_fraction = 0.5 (설정 선택)
```

### 3. 신호 스코어

```
score = 0
  + 1  if Low[t] <= Ls + band          (price_touch: 지지 접촉)
  + 1  if time_ok                       (time_ok: 시간 공명)
  + 1  if qpl_confluence (기본 OFF)    (QPL confluence: v2에서 활성화)

→ score >= 2 이상일 때만 진입 검토
```

### 4. 진입 조건 (Long Only — Main Reversal)

신호일 t에서 **아래 조건 전부 충족** → **t+1 시가(market open) 진입**

| 조건 | 내용 |
|---|---|
| score >= 2 | price_touch + time_ok 기본 |
| Rejection | `Low[t] <= Ls + band` AND `Close[t] >= Ls + 0.5*band` |
| Confirmation | `Close[t] >= SMA5[t]` OR `Close[t] > High[t-1]` (기본: SMA5) |
| Trend Filter | `Close[t] >= SMA200[t]` (보수) / `SMA50[t]` (공격적) (설정 선택) |
| EV Gate | `p * G > (1 - p) * R + COST_BUFFER` (아래 참고) |

> **백테스트에서 진입가 = `Open[t+1]`** (미래정보 없음)

### 5. Breakout-Retest 진입 (Optional)

```
1) Close[t] > (Lr + band)             → 상단 레벨 돌파 확인
2) 이후 10 bars 이내에 Low <= (Lr + band) AND Close >= Lr  → 되돌림 확인
3) 되돌림 확인 다음날 시가 진입
```

### 6. 청산 규칙

```yaml
exits:
  initial_sl: "Ls - 1.0 * ATR"        # 기본 초기 손절
  tp1_price: "Lr"                      # 목표가 1 (So9 상단 레벨)
  tp1_ratio: 0.5                       # TP1 도달 시 50% 청산
  trail_trigger: "Close > Lr"          # 트레일링 발동 조건
  trail_sl: "Lr - band"                # 트레일링 후 손절 이동
  time_stop_bars: 45                   # TP1 미달 시 강제 청산 기한
  gap_handling: true                   # 다음날 시가가 SL 아래면 즉시 청산
```

### 7. EV Gate (Expected Value 필터)

```python
# strategy/ev_gate.py
R = entry_price - SL                  # 리스크
G = TP1_price - entry_price           # 기대 보상

# 유사 이벤트 기반 성공률 p 추정
# 조건: 같은 종목, score >= 2, 동일 rejection 패턴
# 기간: 최근 3년 OR 최근 700 bars
# 성공: 진입 후 45 bars 이내 TP1 도달

COST_BUFFER = 0.005 * entry_price     # 왕복 0.5% 비용
gate_pass = (p * G) > ((1 - p) * R + COST_BUFFER)
```

### 8. 포지션 사이징 & 리스크

```yaml
risk:
  risk_pct_per_trade: 0.005           # 포지션당 자본의 0.5%
  max_positions: 10                   # 최대 동시 포지션
  daily_stop_R: 2                     # 일일 -2R 도달 시 신규 진입 금지
  cost_roundtrip: 0.005               # 왕복 거래비용 0.5%
  slippage: 0.001                     # 슬리피지 0.1% (별도 적용 가능)
```

```python
R = entry_price - SL
size = (equity * risk_pct_per_trade) / R
```

---

## 🖥️ CLI 사용법

### 백테스트

```bash
python -m trader backtest \
  --start 2015-01-01 \
  --end   2026-01-01 \
  --universe kosdaq  # kosdaq | kospi | all
```

**출력:**
- `reports/backtest/<run_id>/index.html` — 인터랙티브 오프라인 HTML 리포트
- `reports/backtest/latest/index.html` — (오픈용) `open reports/backtest/latest/index.html`
- 호환용: `results/equity_curve.png`, `results/trades.csv`, `results/metrics.txt`

*(참고: 리포트 자동 생성이 부담스러울 경우 `--no-report` 옵션 지원)*

### 포트폴리오 관리 및 리포트

**수동 포트폴리오 가져오기:**
```bash
python -m trader portfolio import \
  --csv positions.csv \
  --asof 2026-03-03 \
  --cash 0
```

**포트폴리오 리포트 생성:**
```bash
python -m trader report portfolio --date 2026-03-03
```
- 결과: `reports/portfolio/latest/index.html` (오프라인 오픈: `open reports/portfolio/latest/index.html`)

### 저장된 리포트 다시 렌더링

```bash
python -m trader report backtest --run_id <run_id>
```

### 신호 생성 (장 마감 후 실행)

```bash
python -m trader signals --date 2026-03-02
```

**출력:** `orders/orders_next_open.csv`

```csv
ticker,side,qty,entry_price_est,sl,tp1,score,reason
035420,BUY,100,72000,68000,79000,2,"price_touch+time_ok"
```

### 페이퍼트레이딩

```bash
python -m trader paper \
  --from 2025-01-01 \
  --to   2026-03-02
```

**옵션 플래그 (기본 DRY-RUN):**

```bash
# 주문 파일만 생성 (기본, 실거래 없음)
python -m trader signals --date 2026-03-02 --universe kosdaq

# 페이퍼 시뮬레이션
python -m trader paper --from 2025-01-01 --to 2026-03-02 --universe kosdaq --broker mock

# 실거래 (--live 없으면 절대 전송 금지)
python -m trader signals --date 2026-03-02 --live  # 미래 구현
```

### 리포트 및 포트폴리오 관리

```bash
# 특정 백테스트 실행의 웹 리포트 생성
python -m trader report backtest --run-id <run_id>

# 현재 포트폴리오 상태 기반 리포트 생성
python -m trader report portfolio --date 2026-03-02

# 증권사 등 외부 CSV 포지션을 포트폴리오로 가져오기
python -m trader portfolio import --csv data.csv --asof 2026-03-02
```

---

## ⚙️ config.yaml (전체 파라미터)

```yaml
# config.yaml
universe:
  market: KOSDAQ
  min_listed_days: 250
  min_value_krw: 5_000_000_000
  min_price: 1000
  exclude_list: []

indicators:
  atr_period: 14
  band_atr_mult: 0.25
  pivot_bars: 3                   # Pivot Low(3,3)
  so9_angles: [45, 90, 135, 180, 270, 360]
  so9_k_cycles: [0, 1]
  time_bars: [45, 90, 135, 180, 270, 360]
  time_window: 5
  gann_scale_n: 90
  gann_penalty_fraction: 0.5      # trend_ok == False 시 포지션 분율

strategy:
  score_threshold: 2
  confirmation: sma5              # sma5 | prev_high
  trend_filter: sma200            # sma200 | sma50 | none
  use_qpl_confluence: false       # v1: OFF
  use_breakout_retest: false      # v1: OFF
  sl_atr_mult: 1.0
  tp1_ratio: 0.5
  time_stop_bars: 45

ev_gate:
  enabled: true
  lookback_bars: 700
  success_bars: 45
  cost_buffer_pct: 0.005

risk:
  risk_pct_per_trade: 0.005
  max_positions: 10
  daily_stop_R: 2
  cost_roundtrip: 0.005
  slippage: 0.001

broker:
  default: csv                    # csv | mock | (kis | kiwoom — 미구현 스텁)
  output_dir: orders/

data:
  cache_dir: data/cache
  source: pykrx
```

---

## 🔌 브로커 인터페이스

```python
# execution/broker_base.py
from abc import ABC, abstractmethod

class BrokerBase(ABC):

    @abstractmethod
    def place_order(self, ticker: str, side: str, qty: int,
                    order_type: str = "MARKET", price: float = 0.0) -> str:
        """주문 전송. 반환값: order_id"""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_positions(self) -> dict[str, dict]:
        """{'ticker': {'qty': int, 'avg_price': float}}"""
        ...
```

| 구현체 | 동작 |
|---|---|
| `CsvBroker` | 주문을 CSV 파일로만 저장 (기본값, 실거래 없음) |
| `MockBroker` | 다음날 시가를 체결가로 가정하는 시뮬레이션 |
| `KisBroker` | TODO 스텁 (한국투자증권 API) |
| `KiwoomBroker` | TODO 스텁 (키움 OpenAPI+) |

> ⚠️ **`--live` 플래그 없으면 실거래 API 호출 코드는 절대 실행되지 않아야 한다.**

---

## 🧪 테스트

```bash
pytest tests/ -v
```

| 테스트 파일 | 검증 항목 |
|---|---|
| `test_pivots.py` | Pivot Low가 반드시 t+3 이후에만 확정되는지 검증 |
| `test_so9.py` | Square of 9 레벨 수식 정확성 검증 |
| `test_time_window.py` | time_ok 범위 계산 검증 |
| `test_ev_gate.py` | EV gate 통과/실패 케이스 검증 |

---

## 🚫 불변 규칙 (Non-Negotiable)

1. **미래 정보(Look-ahead) 사용 절대 금지**
   - Pivot Low는 반드시 `t+3` 이후에 확정된 것만 사용
   - 신호 계산은 `t`일의 데이터만, 진입은 `t+1 Open`

2. **DRY-RUN 기본값**
   - `--live` 플래그 없이는 실거래 주문 전송 코드가 실행되면 안 됨

3. **비용 반영**
   - 왕복 수수료 + 슬리피지는 기본 파라미터화 (기본 0.5% + 0.1%)

4. **갭 처리**
   - 백테스트: 다음날 시가가 SL 아래면 해당 시가에서 즉시 청산

---

## 🏗️ 구현 순서 (Step-by-Step)

```
Step 1  프로젝트 스캐폴딩 + requirements.txt
Step 2  pykrx 코스닥 티커 + OHLCV 수집 / Parquet 캐싱
Step 3  ATR → Pivot Low(t+3) → So9 → Time Window → Gann Angle 구현 + 단위 테스트
Step 4  전략 신호 함수 구현 (look-ahead 검증 포함)
Step 5  백테스트 엔진 (t+1 시가 진입 / SL·TP·Trailing·Time Stop / 비용 반영)
Step 6  리포트 & 지표 구현 (정적 HTML 보고서 생성, reports/backtest/<run_id> / latest/index.html 포함)
Step 7  signals CLI → orders_next_open.csv (EV gate + 리스크 사이징)
Step 8  paper CLI (MockBroker 연동) + 일일 손실 한도 로직
```

---

## 📦 설치 및 첫 실행

```bash
# 1. 저장소 클론
git clone https://github.com/yourname/qg-trader.git
cd qg-trader

# 2. 가상환경 생성
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env
# .env 에서 필요한 API 키 입력 (실거래 시만 필요)

# 5. 백테스트 실행
python -m trader backtest --start 2015-01-01 --end 2026-01-01 --universe kosdaq

# 6. 오늘 신호 생성
python -m trader signals --date $(date +%Y-%m-%d)

# 7. 페이퍼트레이딩
python -m trader paper --from 2025-01-01 --to 2026-03-02 --broker mock

# 8. 테스트 실행
pytest tests/ -v
```

---

## 📊 백테스트 출력 예시

```
=== Quantum–Gann Confluence v1 Backtest (2015-01-01 ~ 2026-01-01) ===

Universe       : KOSDAQ (avg 1,234 stocks/day)
Total Trades   : 847
Win Rate       : 52.3%
Profit Factor  : 1.84
CAGR           : 18.7%
Max Drawdown   : -14.2%
Avg R          : 0.42R
Trades / Year  : 76.8

결과 저장: (Run ID: 20260303_001000)
  ✓ reports/backtest/20260303_001000/index.html
  ✓ reports/backtest/latest/index.html
  ✓ 호환: results/equity_curve.png, results/trades.csv, results/metrics.txt
```

**리포트 확인 방법:**
```bash
open reports/backtest/latest/index.html
open reports/portfolio/latest/index.html
```

---

## 🤖 바이브코딩 활용 방법

이 README를 AI 코딩 어시스턴트(Claude Sonnet, Cursor, Copilot)에 붙여넣고 아래처럼 프롬프트하세요:

```
위 README.md의 내용대로 전체 프로젝트를 구현해줘.
REPO STRUCTURE에 있는 모든 파일을 실제로 생성하고,
각 구현 단계(Step 1~8)를 순서대로 진행해줘.
각 스텝 완료 후 "무엇을 만들었는지"를 알려줘.
```

**각 파일별 구현 요청 예시:**

```
# 단계별 요청 예시
"Step 1: trader/__init__.py, cli.py, config.py, requirements.txt 생성"
"Step 2: data/pykrx_loader.py, data/cache.py 구현"
"Step 3: indicators/pivots.py 구현 + tests/test_pivots.py 작성"
```

---

## 🗓️ 버전 로드맵

| 버전 | 내용 |
|---|---|
| **v1.1 (현재)** | Main Reversal 신호, EV Gate, 오프라인 정적 HTML 보고서(Backtest / Portfolio) 추가 |
| v2 | QPL Confluence 활성화, Breakout-Retest, 테마 집중도 제한 |
| v3 | KIS/Kiwoom 실거래 연동, 라이브 웹 대시보드 |

---

*최종 수정: 2026-03-02 | 전략: Quantum–Gann Confluence v1 | 시장: KOSDAQ 1D*
