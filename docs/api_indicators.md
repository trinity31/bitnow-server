# 시장 지표 API 문서

암호화폐의 기술적 지표를 제공하는 API입니다.

## RSI (Relative Strength Index)

RSI는 가격의 상승/하락 추세를 나타내는 기술적 지표입니다.

### 요청

- Method: `GET`
- Endpoint: `/rsi`

### 쿼리 파라미터

| 이름     | 타입    | 필수 | 기본값 | 설명                                       |
| -------- | ------- | ---- | ------ | ------------------------------------------ |
| symbol   | string  | N    | "BTC"  | 암호화폐 심볼 (예: BTC)                    |
| interval | string  | N    | "1d"   | 캔들 간격 ("15m", "1h", "4h", "1d", "all") |
| length   | integer | N    | 14     | RSI 기간                                   |

### 응답 예시

#### 단일 interval 요청 시

json
{
"rsi": 65.42,
"signal": "overbought"
}

#### interval=all 요청 시

{
"15m": {
"rsi": 62.45,
"signal": "neutral"
},
"1h": {
"rsi": 58.32,
"signal": "neutral"
},
"4h": {
"rsi": 70.15,
"signal": "overbought"
},
"1d": {
"rsi": 45.78,
"signal": "neutral"
}
}

### signal 값 설명

- "overbought": RSI > 70, 과매수 구간
- "oversold": RSI < 30, 과매도 구간
- "neutral": 중립 구간

### 에러 응답

{
"detail": "에러 메시지"
}

### 주의사항

- interval이 "all"일 경우, 모든 시간대의 RSI 값을 한번에 반환합니다
- 데이터 조회 실패 시 해당 interval의 RSI는 50.0으로 반환됩니다

## 도미넌스 (Market Dominance)

비트코인의 시장 지배율을 나타내는 지표입니다.

### 요청

- Method: `GET`
- Endpoint: `/dominance`

### 응답 예시

{
"dominance": 52.31,
}

### 응답 필드 설명

| 필드      | 설명                                            |
| --------- | ----------------------------------------------- |
| dominance | 전체 시가총액 대비 비트코인의 시가총액 비율 (%) |
| timestamp | 데이터 시간 (UTC)                               |

## MVRV (Market Value to Realized Value)

시장가치와 실현가치의 비율을 나타내는 온체인 지표입니다.

### 요청

- Method: `GET`
- Endpoint: `/mvrv`

### 응답 예시

{
"mvrv": 1.82,
}

### 응답 필드 설명

| 필드      | 설명                   |
| --------- | ---------------------- |
| mvrv      | 시장가치/실현가치 비율 |
| timestamp | 데이터 시간 (UTC)      |
