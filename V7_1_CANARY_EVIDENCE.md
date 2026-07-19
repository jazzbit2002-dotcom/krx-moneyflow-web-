# V7.1 CANARY 번들 증거 (2026-07-19)

> 기준: 서버 `macro_prompt_v7.txt` = RATIFIED BASE, **무변경**.
> 번들 재구성 프롬프트(8,431B `5d3c1340…`)와 `delivery_v7.patch`는 REJECTED.
> 라이브 `PROMPT_FILE`은 v6 유지. v7 전환은 canary 승인 후.

## 1. 정본 기준값

| 항목 | 값 |
|---|---|
| 서버 macro_prompt_v7.txt | 17,229 B / 216행 / SHA `5f4d65cb6366bf7616a00e6a7c8207269adf92ea165ac00c397efca14db4b2f3` |
| us_macro_delivery.py 패치 전 | 10,819 B / 250행 / SHA `b6a3f13edcad5b43ebe9d2b4bd62cb596e4e8bc6068da8b87c90286bf08db267` |
| us_macro_delivery.py 패치 후(사본 실측) | 13,794 B / SHA `ea58ff85000112c3e8a265a932b2213fbd473420d2b0a5ab8b485d518f9a8462` |

서버 실물 바이트 확보 방법: 로컬 사본 + `PROMPT_FILE` v2→v6 치환 결과가 서버 SHA와 **완전 일치**함을 확인해 재구성이 아닌 실물 기준임을 증명.

## 2. 번들 파일 SHA-256

| 파일 | SHA-256 | bytes |
|---|---|---|
| brief_contract_v1_1.py | `bdb26c84baea6152cadc406973464a43cc606a7c519b6022971a135135c0315f` | 25553 |
| us_macro_brief_v1_1.schema.json | `9e0993a986f09bfdf8e9a8458376ce1eda4d9bd37775f03a070c6af04f1fb2ab` | 3,077 |
| build_review_v2_1.py | `c3e97861487e3cbfdc0b6e548afe8119a39187a4e80f7b6bc2b144ba938b1f36` | 16499 |
| apply_delivery_v71.py | `09336c082cd34471656c2448a34ad42aae10e45a0749d8b1c3c4f942cc5c2741` | 8023 |
| test_contract.py | `bba2736afba9d4d46235988545919d0eddc620527411b5de0ff10d6713f06e06` | 12040 |

전 파일 `py_compile` PASS / schema `json.load` PASS / Draft202012 로드 PASS.

## 3. 테스트 50건 (exit 0)

### 3-1. 정본 무결성 8건 (r3.1 계약 복원)

```
I1  정상 run                          -> latest 적격
I2  brief.json 없음                   -> 부적격
I3  brief.json 실측 SHA 불일치        -> 부적격
I4  원시 응답 <-> brief.json 객체 불일치 -> 부적격
I5  status != brief_saved             -> 부적격
I6  contract_mode != v7               -> 부적격
I7  변조 run latest 배제 / 정상 run 유지 -> PASS
I7b 실패 run 화면도 생성               -> PASS
==== 8 passed / 0 failed ====  exit 0
```

**저장 계약**: `brief.json.tmp` 작성 → `flush` → `fsync` → `os.replace` → **디스크 재읽기 후 실측 SHA-256** → `evidence.brief_sha256`.
인메모리 정규화 해시는 `brief_canonical_sha256` 으로 분리 보관.

**latest 자격 전건**: brief.json 존재 · status=brief_saved · contract_mode=v7 · contract_ok=true ·
evidence.brief_sha256 존재 · 디스크 실측 SHA 일치 · 원시 응답 strict parse 객체 == brief.json 객체 ·
validation.ok · schema_validation=DRAFT202012 · freshness·comparison 게이트.

### 3-2. 계약 테스트 42건 (exit 0)

```
정상 1 · digest 실사용 3 · ticker 양방향 4 · themes 양방향 2 · 파생 폐포 2
구조 11 · 표현 계약 4 · comparison_status 3 · schema 런타임 3 · 파싱 6 · digest 상태 3
==== 42 passed / 0 failed ====  exit 0
```

**mutation test**: `rotation` d7/d90 검사를 무력화 → T02가 예상 FAIL이 아닌 PASS로 뒤집힘 → `35 passed / 1 failed`, **exit 1**. 정본 복원 시 `42/0`, exit 0.
→ 음성 테스트가 원인별 `must_contain`으로 고정돼 거짓 양성이 발생하지 않음을 증명.

## 4. L1 보정 5건 + 추가 보강 2건

| 항목 | 구현 |
|---|---|
| L1-1 ticker 양방향 | `ticker_aliases()` 로 `{MSFT:{MSFT,마이크로소프트}}` 매핑. 선언↔본문 양방향 + **전체 unique 8개 상한** |
| L1-2 themes 양방향 | 선언 테마는 body 등장 필수, body의 허용 테마는 배열 필수. 긴 이름 우선 매칭 후 마스킹(`반도체장비`가 `반도체`로 오탐 방지) |
| L1-3 파생 신규 종목 | 숫자와 동일하게 종목도 폐포 검사, 한글명 정규화 |
| L1-4 코드펜스 | `strip_code_fence` 폐기 → `ContractParseError`. 코드펜스·앞 설명·뒤 문자열·빈 응답 전부 FAIL (`raw_decode` 로 후행 검출) |
| L1-5 exit code | 원인별 `must_contain` + `SystemExit(1 if F else 0)` |
| 보강 1 comparison_status | 무음 기본값 제거. `baseline_only`/`ready` 외 전부 FAIL |
| 보강 2 schema 런타임 | `us_macro_brief_v1_1.schema.json` 을 Draft202012Validator 로 실제 로드. 모듈 부재 시 **건너뛰지 않고 FAIL**(`schema_validation=DEPENDENCY_MISSING`) |
| 비차단 정정 | `digest_is_usable()` 이 close_snapshot freshness 참조 제거. digest 자체 freshness 필드가 있을 때만 SKIPPED_STALE |

## 5. 스키마 정정 (번들 대비)

| 필드 | 번들(오류) | v1.1(정정) |
|---|---|---|
| disclaimer | "이 브리핑은 시장 상태를 정리한 정보이며, 특정 자산의 매수·매도 권유가 아닙니다." | 정본 2문장 (번들 문구는 금칙어 패턴·가운뎃점 포함이라 v7 표현계약 자체를 위반) |
| headline | 1~140 | 12~60 |
| deck | 1~700 | 30~160 |
| section.body | 1~1800 | 60~900 |
| social_summary | 1~900 | 80~240 |
| email_subject / preview | 1~120 / 1~360 | 10~50 / 30~120 |

## 6. delivery 패치 실증

```
base SHA gate : PASS (b6a3f13edcad5b43)
anchor gate   : 3/3 count==1   (IMPORT / EVID / TAIL)
py_compile    : PASS (패치 전·후 모두)
post SHA      : ea58ff85000112c3e8a265a932b2213fbd473420d2b0a5ab8b485d518f9a8462
```
추정 앵커·fuzz·오프셋·미존재 helper 호출 **0건**. 기존 변수 `text` / `ob` / `outdir` 그대로 사용.

**통합 동작 실증:**

| 케이스 | mode | status | publishable | response.json | exit |
|---|---|---|---|---|---|
| v7 정상 | v7 | brief_saved | true | **생성** | 0 |
| v7 코드펜스 | v7 | contract_failed | false | 없음 | **3** |
| v7 깨진 JSON | v7 | contract_failed | false | 없음 | **3** |
| v7 disclaimer 변조 | v7 | contract_failed | false | 없음 | **3** |
| v6 산문(fallback) | v6 | draft_saved | false | 없음 | 0 |

**v6 fallback 보존**: 계약은 `PROMPT_FILE`이 `macro_prompt_v7*`일 때만 작동. v6 산문 실행은 기존 동작 유지 → 별도 run ID로 fallback 가능.

## 7. 검수 화면 검증 17/17

Validation summary(strict parse·JSON Schema·contract·comparison_status·as_of·article length·digest_usage·field_scan·brief SHA·eligible) / Page preview(headline·deck·key_points·sections+종목·테마 태그·watchpoints·disclaimer) / SNS preview / Email preview / Raw JSON 접기.

- 검증 **실패 run도 화면 생성**, `response.json` 없으면 모델 원문 표시
- 실패 run은 **latest 덮어쓰지 않음** (전 게이트 PASS만 latest 후보)
- `runs/` 복제로 `review/` 만 받아도 index 링크 전건 이동
- XSS escape PASS / 외부 자원 0 / noindex

## 8. 배포 전제

```
1) /root/moneyflow/ 에 다음 3종 배치
   brief_contract_v1_1.py · us_macro_brief_v1_1.schema.json · build_review_v2_1.py
2) pip install jsonschema --break-system-packages     ← 신규 의존성 (미설치 시 계약 FAIL)
3) python3 apply_delivery_v71.py                       ← base SHA 게이트 통과해야 적용
4) PROMPT_FILE 은 canary 승인 전까지 v6 유지
```

## 8-1. r3.1 회귀 보정 (이번 차수)

| 감리 지적 | 보정 |
|---|---|
| 정본 파일명 DRIFT (`response.json`) | **`brief.json` 복귀**. 후속 소비자 개정 불필요 |
| 정본 디스크 SHA 미검증 | fsync 후 **디스크 바이트 재해시**를 evidence.brief_sha256 에 기록 |
| 원시↔정본 객체 미대조 | 검수기가 `response.txt` strict parse 결과와 `brief.json` 객체를 **직접 비교** |
| latest 정본 무결성 미검사 | `integrity()` 신설, `eligible()` 이 전건 요구. 화면에 무결성 카드 표시 |
| 통합 테스트 부재 | `test_review_integrity.py` 8건 복원 |

## 9. 미실행 잔여 (canary 시 측정)

- v7 실제 token·cost (v6 실측: input 14,785 / output 2,037 / $0.1249)
- 실제 모델 응답의 계약 통과 여부
- 렌더 화면 실물 캡처
