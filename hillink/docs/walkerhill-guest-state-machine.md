# 워커힐 호텔 고객 State Machine

> 최종 확인일: 2026-09-20
> 출처: walkerhill.com 각 업장 페이지 및 업장별 메뉴 PDF 원문 추출
> 상태: **설계 초안 (state 도출 단계)** — transition/guard 미정의

---

## 0. 모델링 원칙

고객 1명의 상태를 단일 enum으로 표현하면 조합 폭발이 난다. 아래 3계층으로 분리한다.

| 계층 | 정의 | 예 |
|---|---|---|
| **Machine** | 서로 직교(orthogonal)하며 동시에 진행되는 독립 상태 기계 | 예약 / 투숙 / 정산 / 시설세션 |
| **Flag** | 상태 전이와 무관하게 켜지고 꺼지는 속성 | `VIP`, `BLACKLISTED`, `ALLERGY` |
| **Enum (payload)** | 상태가 들고 있는 값. 상태 자체가 아님 | 주문한 **메뉴 항목**, 객실 타입, 회원 등급 |
| **Duration** | 상태 체류 시간 `D`, 전이 지연 `L`, 이동 시간 `T` | §8 — 24시간 타임라인 정합성의 기반 |

**중요 — 메뉴는 state가 아니라 enum이다.**
"칠리새우를 주문했다"는 `ORDER_PLACED` 상태가 `menuItem = 금룡.칠리새우_S` 를 payload로 들고 있는 것이다.
메뉴 항목마다 state를 만들면 워커힐 한 곳에서만 500개 이상의 state가 생긴다.
→ **§4에 전체 메뉴를 enum 도메인으로 수록**한다. 행동(=state)은 §3에 정의한다.

### Machine 목록

| # | Machine | 인스턴스 수 (고객당) | 생명주기 |
|---|---|---|---|
| M1 | `ReservationMachine` | 0..N | 문의 → 확정 → 소멸 |
| M2 | `StayMachine` | 0..N | 도착 전 → 퇴숙 후 |
| M3 | `FolioMachine` | 0..N | 개설 → 정산 |
| M4 | `ComplianceMachine` | 1 | 프로필 생성 시 |
| M5 | `TransportMachine` | 0..N | 편도 단위 |
| M6 | `ServiceRequestMachine` | 0..N | 요청 건별 |
| M7 | `OutletSessionMachine` | 0..N | 업장 방문 건별 ← **§3 핵심** |
| M8 | `IssueMachine` | 0..N | 이슈 건별 |
| M9 | `CrmLifecycleMachine` | 1 | 영구 |
| M10 | `PackageEntitlementMachine` | 0..N | 패키지 특전 건별 ← **§6** |
| M11 | `HourlyStayMachine` | 0..N | 다락휴·트랜짓 시간제 투숙 ← **§5.6** |

---

## 1. 투숙 라이프사이클 축 (M1–M5)

### M1. ReservationMachine
```
INQUIRY · OPTION_HELD · OPTION_EXPIRED · PENDING_PAYMENT · PAYMENT_FAILED
CONFIRMED · GUARANTEED · NON_GUARANTEED · WAITLISTED · WAITLIST_PROMOTED
AMENDED · SPLIT · MERGED
CANCELLED_FREE · CANCELLED_PENALTY · CANCELLED_BY_HOTEL · NO_SHOW · WALKED · DENIED
```
채널 enum: `DIRECT_WEB` `DIRECT_CALL` `WALK_IN` `OTA` `GDS` `CORPORATE` `GROUP_BLOCK` `TRAVEL_AGENT` `COMP` `STAFF_RATE` `WPC_VOUCHER`

### M2. StayMachine
```
PRE_ARRIVAL_D7 · PRE_ARRIVAL_D1 · ONLINE_CHECKIN_AVAILABLE · ONLINE_CHECKIN_DONE · ONLINE_CHECKIN_FAILED
UPSELL_OFFERED · UPSELL_ACCEPTED · SPECIAL_REQUEST_PENDING/CONFIRMED/DENIED · ETA_PROVIDED · FLIGHT_DELAYED
ARRIVED_ON_PROPERTY · AT_FRONT_DESK · IN_CHECKIN_QUEUE · KIOSK_CHECKIN
EARLY_ARRIVAL_ROOM_NOT_READY · LUGGAGE_STORED · LOUNGE_WAITING
REGISTRATION_SIGNED · DEPOSIT_TAKEN · KEY_ISSUED · DIGITAL_KEY_ACTIVATED · ESCORTED_TO_ROOM · CHECKIN_ABORTED
IN_HOUSE · IN_ROOM · OUT_OF_ROOM · DND_ON · MAKE_UP_ROOM_REQUESTED · SERVICE_IN_PROGRESS
ROOM_MOVE_REQUESTED · ROOM_MOVED · ROOM_DOWN
STAY_EXTENDED · STAY_SHORTENED · DUE_OUT
LATE_CHECKOUT_REQUESTED/APPROVED/DENIED · OVERSTAY · SLEEP_OUT
CHECKED_OUT_SETTLED · CHECKED_OUT_UNSETTLED · DEPARTED
SURVEY_SENT · SURVEY_RESPONDED · PUBLIC_REVIEW_POSTED · REBOOK_OFFER_SENT · REBOOKED
```
프로퍼티 enum: `GRAND_WALKERHILL` `VISTA_WALKERHILL` `DOUGLAS_HOUSE`(성인 전용) `VILLA`(장기임대) `ASTON_HOUSE`(연회 전용) `DARAKHYU` `TRANSIT_HOTEL`
객실 타입 enum → **§5** · 패키지 enum → **§6**

### M3. FolioMachine
```
NO_FOLIO · FOLIO_OPEN · AUTH_PENDING · AUTH_APPROVED · AUTH_DECLINED · AUTH_EXPIRED
CREDIT_LIMIT_EXCEEDED · PARTIALLY_SETTLED · SETTLED · CITY_LEDGER · LATE_CHARGE_PENDING
DISPUTED · CHARGEBACK · REFUND_PENDING · REFUNDED · WRITTEN_OFF
TAX_INVOICE_REQUESTED · TAX_INVOICE_ISSUED
```

### M4. ComplianceMachine
```
ID_NOT_VERIFIED · ID_VERIFIED · PASSPORT_SCANNED · FOREIGN_GUEST_REGISTERED
MINOR_WITH_GUARDIAN · MINOR_UNACCOMPANIED_BLOCKED
CONSENT_PENDING · CONSENT_GIVEN · CONSENT_WITHDRAWN · SANCTIONS_FLAGGED
DATA_RETENTION_ACTIVE · DATA_DELETION_REQUESTED · DATA_PURGED
```

### M5. TransportMachine (워커힐은 아차산 중턱이라 실질 비중이 큼)
```
TRANSPORT_UNSET
SHUTTLE_BOOKED · SHUTTLE_BOARDED          (광나루역/강변역 셔틀)
AIRPORT_PICKUP_BOOKED · PICKUP_DRIVER_ASSIGNED · PICKUP_MET · PICKUP_NO_SHOW
LIMOUSINE_EN_ROUTE · SELF_DRIVE_ARRIVING
VALET_RECEIVED · PARKED · CAR_RETRIEVAL_REQUESTED · CAR_RELEASED
```

---

## 2. 횡단 축 (M6, M8, M9 + 플래그)

### M6. ServiceRequestMachine (요청 건별)
```
REQUEST_RECEIVED → ASSIGNED → IN_PROGRESS → FULFILLED → VERIFIED
                                          ↘ FAILED / CANCELLED / ESCALATED
```
요청 타입 enum: `ROOM_SERVICE` `AMENITY` `TURNDOWN` `LAUNDRY` `MINIBAR_REFILL` `ENGINEERING`
`CONCIERGE_BOOKING` `WAKEUP_CALL` `BABY_COT` `EXTRA_BEDDING` `HOUSEKEEPING`

### M8. IssueMachine
```
COMPLAINT_RECEIVED → TRIAGED → IN_SERVICE_RECOVERY → COMPENSATION_OFFERED
  → COMPENSATION_ACCEPTED / COMPENSATION_REJECTED → RESOLVED / UNRESOLVED_ESCALATED
INCIDENT_REPORTED · MEDICAL_ASSISTANCE · SECURITY_INTERVENTION · NOISE_WARNING · EVICTED
LOST_ITEM_REPORTED → LOST_ITEM_FOUND → LOST_ITEM_SHIPPED / LOST_ITEM_DISPOSED
DAMAGE_CHARGED
```

### M9. CrmLifecycleMachine
```
ANONYMOUS → IDENTIFIED → PROSPECT → FIRST_TIME_GUEST → REPEAT_GUEST → LOYAL_ACTIVE
                                                     ↘ AT_RISK → DORMANT → CHURNED
                                                        → WIN_BACK_TARGET → REACTIVATED
```

### 플래그 (머신과 직교)
`VIP` `VVIP` `PRESS_INFLUENCER` `OWNER_GUEST` `BLACKLISTED` `DEBTOR`
`ALLERGY_FLAG` `ACCESSIBILITY_NEEDS` `DND_MARKETING` `MARKETING_OPT_OUT`
`DUPLICATE_PENDING_MERGE` `MERGED_INTO_OTHER`
`PET_ACCOMPANIED` `MINOR_PRESENT` `WPC_MEMBER` `IN_HOUSE_GUEST`(식음 할인 판정용)

### 동반 관계 enum
`PRIMARY_GUEST` `SHARER` `ADDITIONAL_OCCUPANT` `CHILD`(36개월~초등) `INFANT`
`VISITOR_NON_RESIDENT` `GROUP_LEADER` `GROUP_MEMBER`

### 비투숙 고객 타입 enum
`DAY_USE_GUEST` `DINING_ONLY_GUEST` `POOL_DAY_PASS` `EXHIBITION_ONLY`
`BANQUET_ATTENDEE` `CASINO_VISITOR` `WALK_IN_BROWSER` `VENUE_TOUR`

### 혜택 축
```
RATE_LOCKED · PROMO_APPLIED · VOUCHER_HELD · VOUCHER_REDEEMED · VOUCHER_EXPIRED
UPGRADE_WAITLIST · UPGRADE_GRANTED_PAID · UPGRADE_GRANTED_COMP
POINTS_PENDING · POINTS_EARNED · POINTS_REDEEMED · POINTS_CLAWED_BACK · COMP_AUTHORIZED
```

---

## 3. M7. OutletSessionMachine — 업장에서의 행동 = state

한 번의 업장 방문이 하나의 세션 인스턴스. 고객은 동시에 여러 세션을 가질 수 있다.

### 3.1 공통 state (모든 업장)

**예약·착석**
```
NO_RESERVATION · RESERVATION_REQUESTED · RESERVATION_PENDING_CONFIRM · RESERVATION_CONFIRMED
BOOKING_WINDOW_NOT_OPEN        ← 워커힐 전 업장 공통: 2개월 전 1일 10:00 오픈
PREPAYMENT_REQUIRED · PREPAID · DEPOSIT_FORFEITED
RESERVATION_AMENDED · RESERVATION_CANCELLED
WAITLISTED · WAITLIST_CALLED · WAITLIST_EXPIRED
ARRIVED_AT_OUTLET · IN_QUEUE · DRESS_CODE_CHECK · DRESS_CODE_DENIED   ← 슬리퍼·가운 입장 불가
TABLE_ASSIGNED · PDR_ASSIGNED · WINDOW_SEAT_FEE_APPLIED   ← 금룡 창가 PDR ₩50,000
SEATED · PARTIAL_PARTY_SEATED · NO_SHOW · LATE_ARRIVAL_RELEASED
MIN_PARTY_NOT_MET              ← 2인 이상 주문 조건 미충족
```

**주문·서비스**
```
MENU_PRESENTED · ALLERGY_DECLARED · ORIGIN_INQUIRY       ← 원산지 문의
ORDER_TAKEN · COURSE_IN_PROGRESS · COURSE_PACED_HOLD
ADDITIONAL_ORDER · ORDER_MODIFIED · ORDER_VOIDED · ITEM_SOLD_OUT   ← "재료 소진 시 조기 마감"
DIETARY_SUBSTITUTION · CORKAGE_APPROVED · WINE_DECANTING
SERVICE_DELAYED · DISH_REFIRED · DINING · DESSERT_SERVED · CELEBRATION_SERVICE
```

**정산**
```
BILL_REQUESTED · BILL_PRESENTED · SPLIT_BILL · CHARGED_TO_ROOM
PAID_CARD · PAID_CASH · PAID_VOUCHER · PAID_POINTS
WPC_HEADCOUNT_DISCOUNT_APPLIED   ← 인원수별 11~33% (§7 표)
PARTNER_CARD_DISCOUNT_APPLIED · IN_HOUSE_GUEST_DISCOUNT_APPLIED
DISCOUNT_STACK_REJECTED          ← 중복 할인 제한
REWARDS_POINTS_EARNED · REWARDS_EXCLUDED
COMP_APPROVED · SERVICE_CHARGE_WAIVED · PAYMENT_FAILED
LEFT · TABLE_TURNED
```

### 3.2 업장 타입별 추가 state

| 타입 | 추가 state |
|---|---|
| **뷔페** (더뷔페) | `TIME_SLOT_BOOKED` `SLOT_FULL` `SEATING_1BU`/`SEATING_2BU`(1부/2부) `TIME_LIMIT_ACTIVE` `TIME_LIMIT_WARNED` `TIME_LIMIT_EXCEEDED` `CHILD_PRICING_APPLIED`(36개월~초등) `STATION_VISITED` |
| **라운지** (클럽라운지·더글라스 라운지·라이브러리·더파빌리온) | `ENTITLEMENT_CHECK` `ELIGIBLE_BY_ROOM_TYPE` `ELIGIBLE_BY_TIER` `PAID_ACCESS_PURCHASED` `NOT_ELIGIBLE_DENIED` `GUEST_QUOTA_USED` `BREAKFAST_PERIOD` `BRUNCH_PERIOD`(10–14시) `AFTERNOON_TEA_PERIOD` `HAPPY_HOUR_ACTIVE` `CAPACITY_FULL_WAITING` `IN_LOUNGE` `EXITED` |
| **바** (LUX BAR·풀바) | `AGE_VERIFICATION_PENDING` `AGE_VERIFIED` `AGE_DENIED` `BOTTLE_ZONE_SEATED`(LUX 3F) `SET_MENU_MANDATORY`(첫 주문 시 SET 필수) `TAB_OPEN` `TAB_CLOSED` `LAST_ORDER_CALLED` `INTOXICATION_FLAGGED` `SERVICE_REFUSED` |
| **인룸 다이닝** | `ORDER_PLACED` `ORDER_ACCEPTED` `KITCHEN_PREPARING` `OUT_FOR_DELIVERY` `DND_BLOCKED` `DELIVERED` `TRAY_PICKUP_REQUESTED` `TRAY_COLLECTED` `LATE_NIGHT_MENU_ONLY` |
| **리버파크 F&B** | `SEASON_CLOSED` `WEATHER_SUSPENDED` `CABANA_ORDER_PLACED` `POOLSIDE_DELIVERED` `FOOD_TRUCK_QUEUED` `PICKUP_READY` `PICKED_UP` |
| **구르메 스토어** (르 파사쥬) | `BROWSING` `TAKEOUT_ORDER` `PICKUP_SCHEDULED` `PICKED_UP` `GIFT_PACKAGING` `COLD_CHAIN_HOLD` `HMR_VOUCHER_REDEEMED` `UNCLAIMED_DISPOSED` |
| **프라이빗 다이닝** (애스톤하우스·명월관 별채·모에기 PDR·뱅큇) | `INQUIRY` `MENU_TASTING_SCHEDULED` `MENU_CONFIRMED` `BEO_ISSUED` `HEADCOUNT_GUARANTEED` `HEADCOUNT_FINAL` `SETUP_IN_PROGRESS` `EVENT_LIVE` `OVERTIME_APPROVED` `TEARDOWN` `SETTLED` `ADVANCE_BOOKING_REQUIRED`(명월관 별채 최소 2일 전) |
| **테이크아웃** (피자힐·명월관 포장) | `TAKEOUT_ORDERED` `TAKEOUT_DISCOUNT_APPLIED`(피자힐 20%) `PACKAGING` `HANDED_OVER` |

### 3.3 비-식음 시설 세션

| 시설 | state |
|---|---|
| **리버파크** (50m×19m 메인풀, 카바나, 자쿠지) | `SEASON_CLOSED` `TICKETED` `ENTERED` `CABANA_ASSIGNED` `WELLNESS_PROGRAM_JOINED` `EXITED` `CAPACITY_BLOCKED` |
| **포레스트 파크** | `TICKETED` `ADMITTED` `EXITED` |
| **스파·사우나·그랜드피트니스** | `BOOKED` `CHECKED_IN` `IN_TREATMENT` `COMPLETED` `NO_SHOW` |
| **워커힐 골프클럽** (06:00–23:00) | `FACE_REGISTERED`(최초 1회 필수) `SLOT_BOOKED` `PLAYING_60MIN`/`80MIN` `SHORT_GAME_COMPLEX` `WEATHER_CLOSED` `PET_DENIED` |
| **테네즈 파크** | `SLOT_BOOKED`(2시간, 월~금) `PLAYING` `DONE` |
| **빛의 시어터 / 전시** | `TICKETED` `ADMITTED` `IN_SESSION` `EXITED` |
| **마티나 라운지** (인천공항 T1/T2) | `ELIGIBLE` `ADMITTED` `MAX_3H_ACTIVE` `COMPANION_PAID` `EXITED` |
| **파라다이스 카지노** (별도 법인) | `REFERRED` `GUEST_LINKED` `JUNKET_GUEST` `NOT_LINKED` |

---

## 4. 메뉴 Enum — 업장별 전체 목록

`OutletSessionMachine.orderedItems: Set<MenuItem>` 의 도메인.
가격은 2026-09-20 기준 원(₩), 세금 포함 표기 기준.

---
### 4.1 온달 (Ondal) — 한식 / 그랜드 2F
`96석 · 청실2–4 · 홍실5–10 · 평강8–12 · 금실 · 가온 · 12:00–15:00 / 18:00–21:00 · 스마트캐주얼 · 주말·공휴일 코스만 (2인 이상)`

**궁중음식 코스**
| 메뉴 | 가격 |
|---|---|
| 수라상차림 | 195,000 |
| 궁중상차림 | 165,000 |
| 낮것상 (주중 점심 한정) | 125,000 |
| └ 간장게장 추가 | +60,000 |

**프로모션** (2026.09.01–09.30, 주중 한정)
| 메뉴 | 가격 |
|---|---|
| 자연송이로 가을맞이 | 85,000 |

**반상차림 (Meal Set)**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 전복 돌솥비빔밥 | 50,000 | | 한우 도가니 곰탕 | 68,000 |
| 온달 육개장 | 50,000 | | 한우 불고기 | 72,000 |
| 제주 갈치구이 | 95,000 | | 제주 갈치조림 | 92,000 |
| 소고기 미역국 | 50,000 | | 소고기 김치찌개 | 60,000 |
| 된장찌개 | 50,000 | | 전복내장죽 | 60,000 |
| 평양식 물냉면 | 50,000 | | 어린이반상 (미취학) | 40,000 |

**일품요리**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 모듬어회와 숙회 | 280,000 | | 전복초회 | 150,000 |
| 활전복송이볶음 | 200,000 | | 전복돌구이 | 120,000 |
| 자연송이 돌구이 | 150,000 | | 한우등심구이 / 너비아니 | 200,000 |
| 제주옥돔구이 | 200,000 | | 굴비구이 | 300,000 |
| 인삼튀김과 안동 파산적 | 75,000 | | 송이배추볶음 | 130,000 |
| 민물장어 양념구이와 쌈야채 | 85,000 | | 홍삼양지소스 참민어구이 | 80,000 |
| 자소엽 간장게장 | 75,000 | | 궁중진구절판 | 75,000 |
| 미나리 오징어전·해물완자전·새우전 | 50,000 | | 모둠생야채 | 50,000 |
| 장독 수펙스 김치 | 65,000 | | 신선한 과일 | 싯가 |
| 반상 추가 (죽·진지·반찬·후식) | 15,000 | | | |

**음료·주류**
| 항목 | 가격 |
|---|---|
| 에이드 (청귤라임 / 청사과 / 자두복숭아) | 19,000 |
| 하이볼: 통레몬 수이진 · 레몬 진저 | 19,000 |
| 하이볼: 산토리 라임 | 20,000 |
| 하이볼: 려 청귤 | 25,000 |
| 하이볼: 발렌타인 소다 | 37,000 |
| 막걸리: 붉은 원숭이 / 까망토끼 / 호랑이 (375ml) | 30,000 |
| 서설 청주 13% 375ml | 40,000 |
| 금산 인삼주 수삼 23% 120ml | 25,000 |
| 내장산 복분자주 16호 16% 600ml | 89,000 |
| 류 40 오리진 500ml | 150,000 |
| 류 24 클래식 375ml | 80,000 |
| 서해 25 375ml | 60,000 |
| 려 25% 375ml | 55,000 |
| 키 22% 375ml | 60,000 |
| 화요 41% 200ml / 25% 375ml | 55,000 |
| 화요 17% 375ml | 45,000 |
| Cass · Terra 330ml | 12,000 |
| 스텔라 아르투아 생맥주 330ml | 18,000 |
| A Free Day 페일에일 355ml | 18,000 |
| 제철 과일 주스 | 22,000 |
| 쉔 블루 아스트랄브 / 블랑 | 80,000 |

---
### 4.2 금룡 (Geumryong) — 중식(광동) / 그랜드 1F
`129석 = Hall 30 + PDR 12실 99석 · 한강 I·II(12) 한강 III(10) 금강 I·II(6) 금송 I·II(4) 금산(7) 금봉(10) 금린(5) 금학(8) 금록(14)`
`12:00–15:00 / 18:00–21:00 · 창가 PDR 이용료 ₩50,000 · 2026.01.01 가격 개정`

**코스**
| 코스 | 가격 | 조건 |
|---|---|---|
| 추미진향(秋味珍香) 프로모션 (9.1–10.30) | 150,000 | 2인↑, 주중 Hall 전용, 투숙객 15% |
| 주중 특선 SET ① 게살스프+요리3+식사+후식 | 120,000 | 2인↑, 주중 Hall |
| 주중 특선 SET ② 게살스프+요리4+식사+후식 | 140,000 | 2인↑, 주중 Hall |
| 화룡 코스 | 155,000 | 2인↑ |
| 도원경 — 도 | 195,000 | 2인↑ |
| 만수무강 | 235,000 | 2인↑ |
| 진계도 셰프 스페셜 | 280,000 | 2인↑ |
| 도원경 — 원 | 375,000 | 2인↑ |
| 도원경 — 경 | 500,000 | 사전예약, 2인↑ |
| 어린이 메뉴 (미취학) | — | 유료멤버십 10% |
| 자연송이 프로모션 (소금구이/버터구이/굴소스) | 350,000 | 조기 마감 가능 |

**일품 (번호 = 메뉴판 원번호)**
| # | 메뉴 | 가격 | | # | 메뉴 | 가격 |
|---|---|---|---|---|---|---|
| 1 | 농어 (칭징/사천식) | 300,000 | | 41 | 해물 누룽지탕 | 145,000 |
| 2 | 우럭 (칭징/사천식) | 300,000 | | 42 | 하미 분사 냄비 | 145,000 |
| 3 | 어향갈치구이 | 150,000 | | 43 | 전가복 | 185,000 |
| 4 | 목이버섯 오이 냉채 | 35,000 | | 44 | 양반 양장피 | 225,000 |
| 5 | 마라 건두부 해파리 냉채 | 60,000 | | 45 | 피망 고추 잡채 (S) | 85,000 |
| 6 | 3품 냉채 | 85,000 | | 46 | 북경식 탕수육 | 105,000 |
| 7 | 금룡 특품 냉채 | 110,000 | | 47 | 광동식 탕수육 | 110,000 |
| 8 | 광동식 바비큐 전채 | 130,000 | | 48 | 조염 돼지갈비 | 110,000 |
| 9 | 산라 장육냉채 | 100,000 | | 49 | 흑후추 안심 철판 | 160,000 |
| 10 | 제비집 스프 | 300,000 | | 50 | 사천식 안심 요리 | 160,000 |
| 11 | 제비집 게살 스프 | 300,000 | | 51 | 북경오리 | 230,000 |
| 12 | 동충하초 게살 제비집 | 350,000 | | └ | 오리탕/오리볶음 추가 | +30,000 |
| 13 | 금화관연 해호츠 | 450,000 | | 52 | 채끝살 철판구이 (한우) | 380,000 |
| 14 | 산라탕 | 50,000 | | 53 | 어향 가지 볶음 | 80,000 |
| 15 | 게살 스프 | 50,000 | | 54 | 마파두부 | 85,000 |
| 16 | 대게살 코코넛 스프 | 100,000 | | 55 | 전복 마파두부 | 110,000 |
| 17 | 게살 금화어치 스프 | 150,000 | | 56 | 바닷가재 마파두부 | 300,000 |
| 18 | 금룡 불도장 | 180,000 | | 57 | 청경채 (굴소스/마늘) | 90,000 |
| 19 | 황궁 노호탕 | 180,000 | | 58 | 공심채 (굴소스/마늘) | 90,000 |
| 20 | 홍삼 불도장 | 300,000 | | 59 | 흰배추 건관자 소스 | 185,000 |
| 21 | 홍소 금화어치 | 350,000 | | 60 | 금화어치회반 | 260,000 |
| 22 | 위두우 해호츠 찜 | 400,000 | | 61 | 잡탕밥 | 59,000 |
| 23 | 금사오룡 | 180,000 | | 62 | 파인애플 바베큐 볶음밥 | 59,000 |
| 24 | 산라통해삼 | 180,000 | | 63 | 게살 볶음밥 | 45,000 |
| 25 | 해삼 전복 굴소스 | 230,000 | | 64 | 조리장 특선 볶음밥 (XO) | 68,000 |
| 26 | 길품 건전복 해황통해삼 | 450,000 | | 65 | 팔진미 탕면 | 59,000 |
| 27 | 깐풍 전복 | 95,000 | | 66 | 삼선 초면 | 59,000 |
| 28 | 전복 관자 소스 (XO/노간마) | 180,000 | | 67 | 우육 탕면 | 59,000 |
| 29 | 사천식 전복 찜 | 200,000 | | 68 | 완탕면 | 30,000 |
| 30 | 송이 전복 굴소스 | 200,000 | | 69 | 기스면 | 25,000 |
| 31 | 통전복 화로구이 | 200,000 | | 70 | 삼선 특 해물 짬뽕 | 39,000 |
| 32 | 칠리 새우 S (8pc) | 85,000 | | 71 | 갑오징어 짬뽕 | 39,000 |
| 33 | 망고 크림 새우 S (8pc) | 85,000 | | 72 | 차돌 짬뽕 | 37,000 |
| 34 | 마요네즈 새우 S (8pc) | 85,000 | | 73 | 삼선 자장면 | 29,000 |
| 35 | 깐풍 새우 S (8pc) | 85,000 | | 74 | 은사권 튀김 | 18,000 |
| 36 | 활 바닷가재 전복 | 500,000 | | 75 | 꽃빵 | 2,000 |
| 37 | 메이라치즈 활 바닷가재 구이 | 500,000 | | 76 | 물만두 | 35,000 |
| 38 | 유린기 (S) | 85,000 | | 77 | 스페셜 수제 군만두 | 35,000 |
| 39 | 깐풍기 (S) | 85,000 | | 78 | 멘보샤 | 50,000 |
| 40 | 류산슬 (S) | 95,000 | | 79 | 캐비어 멘보샤 | 90,000 |
| | | | | 80 | 계절 과일 (1인) | 50,000 |
| | | | | 81 | 코코넛 제비집 탕수 | 230,000 |

**주류 — 고량주·백주**
| 항목 | 용량 | 가격 |
|---|---|---|
| 고월용산 소흥주 20년 (15%) | 500ml | 1,500,000 |
| 귀주 마오타이 (53%) | 500ml | 1,300,000 |
| 우량예 (52%) | 500ml | 900,000 |
| 수정방 (52%) | 500ml | 830,000 |
| 시주 교장1988 (53%) | 500ml | 650,000 |
| 시주 금찬 (53%) | 500ml | 500,000 |
| 천지람 | 500ml | 400,000 |
| 해천몽 SET (몽지람M6·크리스탈·천지람·해지람 각 100ml) | — | 300,000 |
| 연태1930 노장골드 (52%) | 500ml | 250,000 |
| 금문고량주 58 | 600ml | 200,000 |
| 금문고량주 38 | 600ml | 180,000 |
| 해지람 (42%) | 480ml | 180,000 |
| 사려 (33%) | 500ml | 160,000 |
| 연태고량주 블루 (42%) | 500ml | 150,000 |
| 연태고량주 레드 (38.8%) | 500ml | 130,000 |
| 몽지람 M6 플러스 (52%) | 100ml | 120,000 |
| 고월용산 소흥주 10년 (15%) | 500ml | 120,000 |
| 연태고량주 블랙 (38%) | 500ml | 90,000 |
| 몽지람 크리스탈 (52%) | 100ml | 90,000 |
| 띠디 (38%) / 명냥 (40.8%) / 천진 고량주 (49%) 280ml | — | 80,000 |
| 천지람 (42%) | 100ml | 70,000 |
| 해지람 (42%) | 100ml | 50,000 |
| 천진 고량주 (49%) | 140ml | 24,000 |
| 죽엽청주 (45%) | 125ml | 20,000 |

**주류 — 전통주·일본소주·기타**
| 항목 | 가격 |
|---|---|
| 도한 청명소주 51 오크 에디션 500ml | 300,000 |
| 청명주 20 750ml | 100,000 |
| 키소주 38 375ml | 80,000 / 키소주 22 375ml 60,000 |
| 화요 25 375ml | 55,000 / 화요 17 375ml 45,000 |
| 세키토바 (25%) 720ml | 230,000 (glass 80ml 30,000) |
| 료후 (25%) 720ml | 220,000 (glass 80ml 30,000) |
| 도한 오크 51 하이볼 | 33,000 |
| 시그니처 에이드 (시트러스 / 레모네이드) | 18,000 |
| 연태 하이볼 | 19,000 |
| 생맥주 150ml | 10,000 |
| Fresh Orange Juice | 16,000 |
| 우롱차 / 콜라 / 제로콜라 / 스프라이트 / 진저엘 / 토닉워터 / 에비앙 / 산펠레그리노 | 9,000 |

**주류 — 위스키·코냑·와인**
| 항목 | 병 | 글라스 |
|---|---|---|
| Ballantine's 30Y | 2,500,000 | 150,000 |
| Ballantine's 21Y | 850,000 | 51,000 |
| Ballantine's 17Y | 500,000 | 37,000 / 28,000 |
| Royal Salute 21Y | 850,000 | — |
| Johnnie Walker Blue | 900,000 | — |
| Johnnie Walker Platinum | 500,000 | — |
| Johnnie Walker Black | 310,000 | — |
| Hennessy X.O | 780,000 | — |
| Hennessy V.S.O.P / Remy Martin V.S.O.P | 410,000 | — |
| Dom Perignon | 560,000 | — |
| Laurent Perrier Grand Siecle | 480,000 | — |
| Silver Oak Cabernet Sauvignon (Napa) | 480,000 | — |
| Chablis Grand Cru Les Preuses | 300,000 | — |
| Mollydooker Carnival of Love | 260,000 | — |
| Veuve Clicquot Brut | 150,000 | — |
| Raymond Reserve Selection (Napa) | 150,000 | — |
| Laurent Perrier | 120,000 | — |
| The Printmaker Cabernet Sauvignon (Napa) | 120,000 | — |
| Marbaumont Brut NV / 쉔 블루 아스트랄브 / 블랑 / Bellavista Alma Assemblage 1 | 80,000 | — |
| Roche de Bellene Bourgogne Chardonnay / Pinot Noir | 80,000 | 23,000 |
| Pascal Jolivet Attitude Sauvignon Blanc | 60,000 | — |

---
### 4.3 더 뷔페 (THE BUFFET) — 뷔페 / 비스타 1F
`홀 288석 + 테라스 50석 + PDR 2실(10–24인) · 2023.11.03 그랜드→비스타 이전`

| 식사 | 요일 | 시간 | 성인 | 소인(36개월~초등) |
|---|---|---|---|---|
| 조식 | 화–금 | 07:00–10:00 | 85,000 | 43,000 |
| 조식 | 토–월·공휴일 | 1부 06:30–08:10 / 2부 08:30–10:00 | 85,000 | 43,000 |
| 중식 | 월–금 | 12:00–14:30 | 176,000 | 88,000 |
| 중식 | 토·일·공휴일 | 1부 11:00–13:00 / 2부 13:30–15:30 | 198,000 | 98,000 |
| 석식 | 월–금·일 | 18:00–21:00 | — | — |
| 석식 | 토·공휴일 | 1부 17:30–19:30 / 2부 20:00–22:00 | — | — |

시그니처 스테이션: 프리미엄 랍스터 · 킹크랩 (그릴 테일, 파스타, 콜드/핫)
> ⚠️ 스테이션 단위 전체 품목은 웹에 미공개. 현장 실사 필요 (§10)

---
### 4.4 명월관 (Myongwolgwan) — 한우 숯불구이 / 비스타
`본관 168석 = 홀 88 + PDR 9실 80석(2–36인) · 별채 16석 = PDR 3실(2–8인)`
`12:00–15:00 / 17:30–21:00 · ZAGAT 2010 서울 한식 1위`

**별채 — 한우 맡김차림** (금·토·일·공휴일 점심 / 연중무휴 저녁, 사전예약 최소 2일 전, 13세 미만 불가)
| 코스 | 가격(1인) |
|---|---|
| 온새미로 | 350,000 |
| 진진미 | 500,000 |
| 안다미로 | 700,000 |

**현담 (파인다이닝 룸)**
| 코스 | 가격(1인) |
|---|---|
| 미담 | 260,000 |
| 도담 | 280,000 |
| 현담 | 350,000 |

**프로모션**
| 메뉴 | 가격 | 기간·조건 |
|---|---|---|
| 능이버섯 등심 불고기 한상 (죽·등심불고기180g·냉면or된장찌개·과일차) | 91,000 | 9.1–10.30, 주중 점심만, 2인↑ |
| 자연송이 모둠구이 한상 (죽·자연송이 한우육회·모둠구이 소750g/송이130g) | 770,000 | 9.1–10.10, WPC·투숙객 20% |

**모둠·명품 한우**
| 메뉴 | 중량 | 가격 | 100g당 |
|---|---|---|---|
| 명월관 스페셜 모둠 특선 (등심·안심·업진살·부채살·양념구이, 2인 식사 포함) | 510g | 350,000 | 64,700 |
| 한우 특선 모둠 (안창살·등심·치마살·살치살·특양념갈비) | 880g | 770,000 | 87,500 |
| 한우 SUPEX 통갈비 | 500g | 370,000 | 74,000 |
| 한우 "병풍" 갈비 | 450g | 370,000 | 82,200 |

**구이류 (1인분)**
| 메뉴 | 중량 | 가격 | 100g당 |
|---|---|---|---|
| 생갈비 | 160g | 118,000 | 73,750 |
| 생등심 | 180g | 103,000 | 57,200 |
| 치마살 숙성 육회 | 150g | 99,000 | 82,500 |
| 특 양념갈비 | 180g | 97,000 | 53,800 |
| 한우 모둠 주물럭 | 160g | 86,000 | 53,750 |
| 양념갈비 | 200g | 78,000 | 39,000 |
| 한우 육회 | 150g | 60,000 | 40,000 |
| 숯불 불고기 (점심 한정) | 200g | 53,000 | 26,500 |

**특수 부위 (1인분)**
| 메뉴 | 가격 | 100g당 |
|---|---|---|
| 안창살 | 130,000 | 130,000 |
| 안심 | 110,000 | 110,000 |
| 치마살 | 85,000 | 85,000 |
| 양깃머리 (150g, 뉴질랜드산) | 80,000 | 53,300 |
| 살치살 | 80,000 | 80,000 |
| 우설 | 79,000 | 79,000 |
| 차돌박이 | 75,000 | 75,000 |

**정식 / 상차림** (2인 이상)
| 메뉴 | 가격 |
|---|---|
| 한우 등심 정식 (죽·샐러드·육회·등심180g or 양념갈비200g·전복버터구이·식사·과일차) | 179,000 |
| 한우 양념갈비 정식 | 179,000 |
| 소담 상차림 (U.S. 생갈비250g / 장향갈비200g / 죽염갈비200g 택1, 점심 한정) | 120,000 |

**단품·식사**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 굴비 (국내산) | 220,000 | | SUPEX 김치 | 20,000 |
| 양송이 | 30,000 | | 자연송이 | 싯가 |
| 한우 갈비탕 | 45,000 | | 한우 차돌박이 김치찌개 | 39,000 |
| 갈비탕 (미국산) | 39,000 | | 한우 갈비 국밥 | 39,000 |
| 한우 차돌박이 꽃게 된장찌개 | 39,000 | | └ + 영양돌솥밥 | 55,000 |
| 물냉면 / 비빔냉면 | 26,000 | | 냉면(S)·된장찌개(S) 구이 주문 시 | 17,000 |

**포장 선물세트** (유료멤버십·제휴 할인 가능, 적립 제외)
| 메뉴 | 1kg(5인분) | 2kg(10인분) | 100g당 |
|---|---|---|---|
| 한우 불고기 | 238,500 | 477,000 | 23,850 |
| 한우 양념 갈비 | 351,000 | 702,000 | 35,100 |

**주류 — 샴페인**
| 항목 | 가격 |
|---|---|
| Louis Roederer Cristal Rose 2014 | 2,300,000 |
| Louis Roederer Cristal 2015 | 860,000 |
| Moet & Chandon Dom Pérignon 2015 | 560,000 |
| Laurent Perrier Millésime Brut 2018 | 280,000 |
| Charles Heidsieck Brut Rose Réserve NV | 240,000 |
| Bollinger Special Cuvee Brut NV | 230,000 |
| Charles Heidsieck Brut Réserve NV | 160,000 |
| Drappier Carte d'or Brut NV | 140,000 |
| Taittinger Brut Réserve NV | 120,000 |
| Bellavista Alma Assemblage 1 (Italy) NV | 80,000 |
| Juve Camps Essential Purpura Reserva NV | 70,000 |

**주류 — 화이트**
| 항목 | 가격 |
|---|---|
| Roche de Bellene Bienvenues Batard Montrachet Grand Cru 2019 | 1,500,000 |
| Alex Gambal Chassagne Montrachet 1er Cru 2021 | 380,000 |
| Hyde de Villaine Le Debut California 2023 | 300,000 |
| Flowers Sonoma Coast 2024 | 160,000 |
| Domaine Servin Chablis 2023 | 100,000 (glass 25,000) |
| Chene Bleu "Astralabe Blanc" Provence 2023 | 80,000 |

**주류 — 레드**
| 항목 | 가격 | | 항목 | 가격 |
|---|---|---|---|---|
| Chateau Latour 1er GCC Pauillac 2012 | 2,800,000 | | Barolo Baudana, Luigi 2021 | 350,000 |
| Chateau Mouton Rothschild 1er GCC 2014 | 2,300,000 | | Chateau Montrose 2er GCC 2013 | 350,000 |
| Napa Valley 2021 | 1,800,000 | | Hyde de Villaine 계열 300,000 | — |
| Sassicaia DOC Bolgheri 2022 | 750,000 | | Mollydooker Carnival of Love 2023 | 260,000 |
| Brunello di Montalcino, Biondi Santi 2017 | 660,000 | | Jean Claude Boisset Gevrey Chambertin 2021 | 260,000 |
| Chateau Leoville Las Cases 2er GCC 2019 | 620,000 | | Walter Hansel Cuvee Alyce Pinot Noir 2021 | 250,000 |
| Chateau Cos d'Estournel 2er GCC 2021 | 580,000 | | Dana Estates Vaso Napa 2021 | 240,000 |
| Almaviva Maipo Valley 2021 | 550,000 | | Barolo Pio Cesare 2021 | 230,000 |
| Napa Valley 2018 / 2017 | 480,000 | | Brunello di Montalcino, Casanova di Neri 2021 | 230,000 |
| SOM Napa Valley 2023 | 440,000 | | Domaine Lecheneaut Nuits Saint Georges 2018 | 220,000 |
| Pascal Clement Vosne Romanée 2023 | 430,000 | | Barolo Pichemei, Marrone 2021 | 180,000 |
| Geantet Pansiot Chambolle Musigny VV 2023 | 420,000 | | Flowers 계열 160,000 | — |
| Domaine Coudray Bizot Vosne Romanee 1er 2019 | 800,000 | | Raymond Reserve Selection Napa 2021 | 150,000 |
| Laurent Ponsot Chambolle Musigny 1er Cru 2019 | 800,000 | | Guidalberto Toscana 2023 | 140,000 |
| | | | Girard Napa Valley 2021 | 120,000 |
| | | | Kalleske Greenock Barossa 2024 | 120,000 |
| | | | I Greppi Greppicante Bolgheri 2020 | 120,000 |
| | | | Chris Ringland Barossa Valley 2022 | 100,000 |
| | | | Lucente Toscana Montalcino 2018 | 100,000 |
| | | | Sons of Eden Zephrus Barossa 2023 | 90,000 (glass 24,000) |
| | | | Maison Roche de Bellene Cuvee Reserve 2022 | 80,000 |
| | | | Hedges CMS Columbia Valley 2021 | 80,000 |
| | | | Chene Bleu "Astralabe" Provence 2019 | 80,000 |
| | | | Emiliana Coyam Colchagua 2022 | 70,000 |

**주류 — 위스키·소주·맥주·음료**
| 항목 | 용량 | 병 | 글라스 |
|---|---|---|---|
| 발렌타인 30년 | 750ml | 2,500,000 | 150,000 |
| 조니워커 블루라벨 | 750ml | 900,000 | — |
| 글렌리벳 18년 | 700ml | 600,000 | 32,000 |
| 발렌타인 17년 | 750ml | 500,000 | 28,000 |
| 아벨라워 12년 | 700ml | 410,000 | — |
| 글렌리벳 15년 | 700ml | 350,000 | — |
| 쿠보타 만쥬 | 720ml | 350,000 | — |
| 글렌리벳 12년 | 700ml | 250,000 | — |
| 류 소주 오리진 (40도) | 500ml | 150,000 | — |
| 류 소주 클래식 (24도) / 키 소주 (38도) | 375ml | 80,000 | — |
| 서해 (25도) / 키 (22도) | 375ml | 60,000 | — |
| 려 (25도) / 해랑 (28도) / 화요 (25도) | 375ml | 55,000 | — |
| 화요 (17도) | 375ml | 45,000 | — |
| 호랑이 막걸리 (7도) | 375ml | 30,000 | — |
| 키 소맥 | 500ml | 25,000 | — |
| 히타치노 네스트 데이지 에일 | 330ml | 20,000 | — |
| 스텔라 아르투아 생맥주 | 330ml | 18,000 | — |
| 어프리데이 페일에일 (0.5%) | 355ml | 18,000 | — |
| 아사히 | 330ml | 17,000 | — |
| 카스 / 테라 | 330ml | 12,000 | — |
| 제철 과일 쥬스 | — | 25,000 | — |
| 오렌지주스 | — | 18,000 | — |
| 콜라·제로콜라 355ml / 스프라이트 350ml / 토닉·클럽소다·진저엘 250ml / 네이키드워터 500ml / 산펠레그리노 250ml / 우롱차 340ml | — | 9,000 | — |

---
### 4.5 MOEGI — 일식 / 비스타
`103석 = 스시바 12 + 홀 40 + 철판 13 + PDR 5실 38석(4–30인)`
`12:00–15:00 / 18:00–21:00 · 조리장 김승찬 · 요비모도시 장어소스(1983~)`

**코스**
| 코스 | 가격 | 비고 |
|---|---|---|
| 나츠료우미사이 (여름 프로모션) | 98,000 | 주중 점심, 2인↑ |
| 런치 모에기 코스 | 210,000 | 2인↑ |
| 마코토 코스 | — | 2인↑ |
| 미야비 코스 | 250,000 | 2인↑ |
| 모미지 코스 | 320,000 | 2인↑ |
| 어린이 메뉴 (초등까지) | 70,000 | |

**정식 (한상차림)**
| 메뉴 | 가격 |
|---|---|
| 요비모도시 장어 정식 | 170,000 |
| 모에기 스시와 소바 정식 | 160,000 |
| 생선회 정식 부출 | — |
| 전복 냄비 우동 정식 부출 | — |

**철판 요리** (사전예약, 1부 12:00–13:30 / 2부 13:45–15:15, 1부 18:00–20:30 / 2부 18:30–21:00)
| 메뉴 | 가격 |
|---|---|
| 철판코스 DINNER TOKIMEKI | 350,000 |
| 철판코스 LUNCH SASAYAKI | 210,000 |
| 스페셜 한우 안심 (160g) | 170,000 |
| 스페셜 한우 등심 (160g) | 160,000 |

**스시 카운터 오마카세** (사전예약, 카운터 전용, 최소 1시간 30분, 2인↑)
| 메뉴 | 가격 |
|---|---|
| TSUKI | 300,000 |
| EDO | 210,000 |

**생선회**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 바닷가재회 (1.3kg) | 400,000 | | 특모둠 생선회 | 300,000 |
| 참치 뱃살회 (7pcs) | 270,000 | | 모둠 흰살 생선회 | 200,000 |
| 엷은 흰살 생선회 | 150,000 | | 전복회 | 135,000 |

**구이**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 바닷가재 버터구이 (1.3kg) | 500,000 | | 생 옥돔구이 | 200,000 |
| 갈치구이 | 150,000 | | 전복 버터구이 | 145,000 |
| 모에기 특제소스 장어구이 | 120,000 | | 은대구 유안구이 | 85,000 |

**튀김 / 냄비·조림**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 모둠 튀김 | 90,000 | | 모에기 스페셜 스끼야끼 냄비 (2인↑) | 190,000 |
| 새우 튀김 | 65,000 | | └ 고기 추가 100g / 1인분 120g | 100,000 / 120,000 |
| 닭고기 튀김 | 60,000 | | 도미머리 조림 | 115,000 |
| 야채 튀김 | 50,000 | | 생선 지리 냄비 | 115,000 |
| 가츠오향 두부 튀김 | 35,000 | | | |

**진미**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 캐비어 벨루가 | 500,000 | | 대게 한 마리 | 400,000 |
| 캐비어 오세트라 | 350,000 | | 대게 반 마리 | 200,000 |
| 성게알 | 100,000 | | 연어알 / 청어알 | 80,000 |
| 은행 튀김 | 50,000 | | 해초 초회 | 40,000 |
| 산마즙 | 30,000 | | 일본식 계란찜 / 쯔케모노 | 20,000 |

**식사 / 면류 / 국류**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 모에기 특선 회덮밥 | 150,000 | | 모에기 특제소스 장어 덮밥 (한마리) | 130,000 |
| 스끼야끼 덮밥 | 95,000 | | 새우 튀김 덮밥 | 75,000 |
| 공기밥 | 5,000 | | | |
| 냄비우동 (HOT) | 75,000 | | 튀김 자루소바 (COLD) | 65,000 |
| 튀김소바 (HOT) / 튀김우동 (HOT) | 65,000 | | 차 소바 (COLD) | 60,000 |
| 가케소바 (HOT) | 45,000 | | 가케우동 (HOT) | 40,000 |
| 야꾸미 & 다시 추가 | 5,000 | | | |
| 계란 적 된장국 / 대합 적 / 바지락 적 / 생선살 된장국 | 35,000 | | 대합 맑은국 / 대합 된장국 / 바지락 된장국 / 적 된장국 | 30,000 |

**생선초밥 (貫당)**
| # | 종목 | 가격 | | # | 종목 | 가격 |
|---|---|---|---|---|---|---|
| 14 | (生)보리새우 | 60,000 | | 20 | 전복 | 20,000 |
| 9 | 성게알 (RUS) | 50,000 | | 26 | 문어 | 20,000 |
| 9 | 성게알 (CAN/KOR) | 35,000 | | 30 | 민물장어 | 20,000 |
| 1 | 오도로 | 35,000 | | 31 | 바다장어 | 20,000 |
| 2 | 쥬도로 | 35,000 | | 8 | 광어 지느러미 | 20,000 |
| 11 | 연어알 | 30,000 | | 13 | 꽃새우 | 20,000 |
| 16 | 도화새우 | 30,000 | | 23 | 키조개 | 20,000 |
| 14-1 | 보리새우 | 30,000 | | 4 | 도미 | 17,000 |
| 21 | 피조개 | 30,000 | | 6 | 방어 | 17,000 |
| 22 | 왕우럭조개 | 30,000 | | 7 | 광어 | 17,000 |
| 24 | 북방조개 | 30,000 | | 17 | 학꽁치 | 17,000 |
| 25 | 새조개 | 30,000 | | 18 | 한치 | 17,000 |
| 3 | 참치 | 27,000 | | 27 | 고등어 | 17,000 |
| 5 | 능성어 | 25,000 | | 28 | 전어 | 17,000 |
| 10 | 청어알 | 25,000 | | 29 | 전갱이 | 17,000 |
| 15 | 새우 | 12,000 | | 32 | 도다리 | 17,000 |
| 19 | 계란 | 10,000 | | | | |

**김초밥 / 프리미엄 스시**
| 메뉴 | 가격 |
|---|---|
| 조리장 프리미엄 스시 | 170,000 |
| 모에기 후토마키 | 80,000 |
| 참치 도로 & 실파 김초밥 | 65,000 |
| 참치 김초밥 | 50,000 |
| 우메시소 김초밥 | 30,000 |
| 단무지 / 오이 / 박속 김초밥 | 20,000 |

**음료·주류**
| 항목 | 가격 |
|---|---|
| 한라봉 에이드 | 18,000 |
| 우메소다 / 레몬사와 / 복숭아사와 | 17,000 |
| 히비콕 / 핑크레몬에이드 | 15,000 |
| Ballantine's 17years (glass) | 37,000 |
| Japanese (Hujisanroku) (glass) | 34,000 |
| 더 글렌리벳 트리플 스펙트럼 세트 (12Y/15Y/18Y + 클럽소다) | 49,000 |
| Fresh Orange Juice | 18,000 / Café Latte 18,000 / Espresso 15,000 / Iced Americano 12,000 / Americano 10,000 |
| Suntory / Asahi (draft) 380ml | 25,000 |
| Hitachino nest DAISY ALE 330ml | 20,000 / Asahi 330ml 17,000 / Cass 330ml 12,000 |
| 화요 25% / 일품진로 25% / 화요 41% 200ml | 55,000 / 화요 17% 45,000 |

**사케 (SAKE)**
| 등급 | 항목 | 지역 | 도수 | 용량 | 가격 |
|---|---|---|---|---|---|
| 다이긴죠 | 사토노 호마레 카쿤코 | 이바라키 | 16.0% | 720ml | 1,200,000 |
| 다이긴죠 | 토우코우 후쿠로추리 | 야마가타 | 16.0% | 720ml | 390,000 |
| 다이긴죠 | 쿠보타 만쥬 | 니이가타 | 15.5% | 720ml | 350,000 |
| 다이긴죠 | 키쿠사카리 다이긴죠 | 이바라키 | 16.0% | 720ml | 320,000 |
| 다이긴죠 | 닷사이 39 | 야마구치 | 16.0% | 720ml | 260,000 |
| 다이긴죠 | 다카시미즈 준마이 다이긴죠 | 아키타 | 15.5% | 720ml | 160,000 |
| 다이긴죠 | 미야칸바이 준마이다이긴죠 45 | 미야기 | 15% | 720ml | 150,000 |
| 다이긴죠 | 사카마이 기쿠스이 | 니이가타 | 15.0% | 720ml | 150,000 |
| 다이긴죠 | 아마노토 준마이 다이긴죠 | 아키타 | 16.5% | 720ml | 120,000 |
| 긴죠 | 료제키 스이교쿠 준마이긴죠 | 아키타 | 15.0% | 720ml | 140,000 |
| 긴죠 | 죠젠미즈노고토시 준마이긴죠 50 | 니이가타 | 14.5% | 720ml | 130,000 |
| 긴죠 | 미야칸바이 준마이긴죠 55 | 미야기 | 15.0% | 720ml | 110,000 |
| 긴죠 | 키쿠스이 무칸테이 긴죠 | 니이가타 | 15.0% | 300ml | 50,000 |
| 준마이 | 키쿠사카리 야마하이 겐슈 | 이바라키 | 17.0% | 720ml | 210,000 |
| 준마이 | 간기 스파클링 준마이 활성니고리 나마 | 야마구치 | 14.0% | 720ml | 190,000 |
| 준마이 | 키쿠사카리 준마이 슈 | 이바라키 | — | — | 100,000 |
| 준마이 | 다카시미즈 준마이 겐테이 | 아키타 | 15.3% | 720ml | 90,000 |

**일본 소주**
| 항목 | 지역 | 도수 | 용량 | 가격 |
|---|---|---|---|---|
| 만젠 | 가고시마 | 25.0% | 720ml | 360,000 |
| 료후 | 가고시마 | 25.0% | 720ml | 220,000 |
| 마로야카 | 쿠마모토 | 25.0% | 720ml | 190,000 |
| 우스키 우사기 | 쿠마모토 | 20.0% | 600ml | 120,000 |
| 하쿠스이 무기 | 쿠마모토 | 25.0% | 720ml | 100,000 |

**위스키 / 와인**
| 항목 | 병 | 글라스 |
|---|---|---|
| Ballantine's 30Y | 2,500,000 | 150,000 |
| THE GLENLIVET 18Y | 600,000 | 32,000 |
| Chivas Regal 18Y | 500,000 | — |
| Ballantine's 17Y | 500,000 | 28,000 |
| Huji Sanroku | 450,000 | — |
| HINOMARU Signature 1823 | 380,000 | — |
| THE GLENLIVET 15Y | 350,000 | 23,000 |
| THE GLENLIVET 12Y | 250,000 | 13,000 |
| Dom Perignon 2015 | 560,000 | — |
| Domaine de La Riviere Next Door Neighbor 2019 | 360,000 | — |
| Innovatus Napa Valley 2018 | 280,000 | — |
| Bollinger Special Cuvee Brut NV | 200,000 | — |
| Château Branaire Ducru Saint-Julien 2012 | 200,000 | — |
| Famille Perrin Chateauneuf-du-Pape Les Sinards 2023 | 170,000 | — |
| Charles Heidsieck Brut Réserve NV | 160,000 | — |
| Taittinger Prestige Rosé Brut NV | 140,000 | — |
| Taittinger Brut Réserve NV | 120,000 | — |
| Textbook Sonoma County Pinot Noir 2023 | 110,000 | — |
| Chris Ringland Shiraz 2022 | 100,000 | 25,000 |
| Domaine Servin Chablis 2022 | 100,000 | — |
| Charles Heidsieck Brut Réserve (half) NV | 90,000 | — |
| Levert Frères Crémant de Bourgogne Brut NV | 90,000 | — |
| Chene Bleu Astrolabe / Astrolabe Blanc | 80,000 | — |
| Dough Chardonnay 2022 | 70,000 | 22,000 |
| Drylands Sauvignon Blanc 2024 | 70,000 | — |

---
### 4.6 피자힐 (PIZZA HILL) — 이탈리안 / 비스타 별관
`96석 · 11:30–22:30 (7타임, 타임당 2시간) · L.O 21:00 · 테이크아웃 20% 할인 · 도우·파스타면 계란 무첨가`

**세트 메뉴**
| 세트 | 구성 | 가격 |
|---|---|---|
| Couple SET | 커플샐러드 + 피자(S) + 파스타 1종 + 음료 2잔 | 184,000 |
| Triple SET | 커플샐러드 + 피자(L) + 파스타 2종 + 음료 3잔 | 251,000 |
| Quattro SET | 패밀리샐러드 + 콰트로피자 + 파스타 2종 + 음료 4잔 | 316,000 |
| SEIS SET | 패밀리샐러드 + 세이스피자 + 파스타 2종 + 음료 6잔 | 351,000 |
> 음료 아메리카노 ICE 변경 +2,000 / 에이드 3종(블루레몬·자몽·오렌지) 변경 +8,000 / 기타 음료·주류 변경 불가

**샐러드**
| 메뉴 | 커플(2인) | 패밀리(4인) | 테이크아웃 |
|---|---|---|---|
| 홈메이드 훈제 연어 샐러드 | 49,000 | 58,000 | 39,200 |
| 모둠치즈 & 과일 샐러드 | 49,000 | 58,000 | 39,200 |
| 페스토 소스 해산물 샐러드 | 49,000 | 58,000 | 39,200 |

**피자**
| 메뉴 | S | L | 테이크아웃 S / L |
|---|---|---|---|
| 콤비네이션 피자 | 73,000 | 83,000 | 58,400 / 66,400 |
| 페퍼로니 피자 | 73,000 | 83,000 | 58,400 / 66,400 |
| 한우 불고기 피자 | 79,000 | 89,000 | 63,200 / 71,200 |
| 갈릭 새우 피자 | 79,000 | 89,000 | 63,200 / 71,200 |
| 모둠 해산물 피자 | 79,000 | 89,000 | 63,200 / 71,200 |
| 마르게리타 피자 | 69,000 | 79,000 | 55,200 / 63,200 |
| Half & Half (L) — 콤비네이션 + 해산물/마르게리타/페퍼로니/한우불고기/갈릭새우 | — | 92,000 | 73,600 |
| QUATTRO PIZZA (해산물·한우불고기·콤비네이션·마르게리타) | — | 126,000 | 100,800 |
| SEIS PIZZA (6종 전부) | — | 143,000 | 114,400 |

**파스타·리조또** (전부 매운맛 주문 가능 / 면 al dente)
| 메뉴 | 가격 |
|---|---|
| 랍스터 로제 파스타 | 53,000 |
| 크랩 파스타 | 49,000 |
| 모둠 버섯 트러플 크림 파스타 | 49,000 |
| 봉골레 파스타 | 49,000 |
| 해산물 토마토 파스타 | 48,000 |
| 해산물 크림 파스타 | 48,000 |
| 전복 해산물 리조또 | 48,000 |

**토핑 & 디핑**
| 항목 | 가격 | | 항목 | 가격 |
|---|---|---|---|---|
| 치즈 토핑 (S / L) | 7,000 / 9,000 | | 콰트로 치즈토핑 | 17,000 |
| 세이스 치즈토핑 | 19,000 | | 후레쉬 모짜렐라 치즈 | 13,000 |
| 디핑소스 세트 | 13,000 | | 불고기 (100g) | 15,000 |
| 갈릭새우 10마리 | 12,000 | | 고르곤졸라 치즈 / 루꼴라 | 10,000 |
| 페퍼로니 / 블랙올리브 | 7,000 | | 파인애플 | 6,000 |
| 체다 치즈 / 치폴레 디핑 / 갈릭 | 5,000 | | 피클 추가 2,000 / 할라피뇨 포장 5,000 | — |
> 피자 데움(Re-heat) 서비스 무료

**음료**
| 항목 | 가격 | 식사 주문 시 |
|---|---|---|
| 아이스 아메리카노 | 20,000 | 12,000 |
| 아메리카노 | 18,000 | 10,000 |
| 아이스 카페라떼 | 22,000 | 15,000 |
| 카페라떼 | 20,000 | 13,000 |
| 캐모마일 / 페퍼민트 / 진저레몬티 | 18,000 | 10,000 |
| 에이드 (오렌지·블루레몬·자몽·진저레몬) | 17,000 | — |
| 콜라·제로콜라·스프라이트·산펠레그리노·진저엘 | 10,000 | — (리필 불가) |
| 레몬/얼그레이/진저 하이볼, 잭콕 | 20,000 | — |
| 스텔라 아르투아 생맥주 / 호가든 | 18,000 | — |

---
### 4.7 더 파빌리온 (The Pavilion) — 로비 라운지 / 그랜드 로비
`81석 · 09:00–21:00 연중무휴 · L.O 20:00 · 라이브 공연 · 02-450-4534`

**시즌 프로모션**
| 항목 | 기간 | 가격 |
|---|---|---|
| 가을 애프터눈 티 (2인 기준) | 2026.09.01–11.30, 11:00–20:00 | 98,000 (1인 추가 49,000) |
| 시그니처 빙수 / 초코 브라우니 빙수 | 2026.05.01–10.11, 10:00–20:00 | 55,000 |
| └ 빙수 추가: 가래떡(1ea) / 호두곶감말이(1ea) 4,000, 마카롱(2ea) 5,000, 빙수 팥 5,000 | | |
| 아보카도 셰이크 & 코코넛 셰이크 | 시즌 한정 | 25,000 |
| 타코 & 칩스 (2pc) | — | 39,000 |

**애프터눈 티 구성** — SWEETS: 트로피칼 가든 · 밤 만주 · 미니 블루베리 · 복숭아 케이크 · 메론 버블 케이크 · 한라봉 타르트 · 솔트 러스크 / SAVORIES: 미니 관자 까나페 · 수제 소시지 키쉬 · 파인애플 샌드위치

**커피**
| 메뉴 | HOT | ICE |
|---|---|---|
| 아포카토 | 25,000 | — |
| 아보카도 커피(디카페인) / 코코넛 커피 | 27,000 | — |
| 아몬드 크림 라테 / 더치 라테 | 24,000 | — |
| 더치 아메리카노 | 23,000 | 24,000 |
| 카페 모카 / 레드벨벳 바닐라 라테 | 23,000 | 24,000 |
| 애슬로우 더치 | 23,000 | — |
| 오곡 라테 / 말차 라테 | 23,000 | 24,000 |
| 카페 라테 / 카푸치노 / 비엔나 | 21,000 | 22,000 |
| 리얼 초코 / 얼그레이 밀크티 | 21,000 | 22,000 |
| 아메리카노 | 19,000 | 20,000 |
| 에스프레소 / 마끼아또 / 콘파냐 | 19,000 | — |
> 샷 추가 +2,000 / 오트 우유 +2,000 / 디카페인 변경·추가 +2,000
> 원두 판매: 시그니처 70,000 · 디카페인 80,000

**티 / 음료**
| 메뉴 | HOT | ICE |
|---|---|---|
| 유자차 / 오미자차 / 생강차 / 대추차 / 쌍화차 | 22,000 | 23,000 |
| 워커힐 브리즈 / 얼그레이 / NYC 브렉퍼스트 / 녹차 / 캐머마일 / 쿨민트 / 히비스커스 / 루이보스 슈프림 | 19,000 | 20,000 |
| 인삼 주스 / 아보카도 셰이크 / 코코넛 셰이크 | 25,000 | — |
| 레몬스쿼시 / 오렌지주스 / 자몽주스 / 망고·블루베리 요거트 스무디 | 22,000 | — |
| 바닐라 / 벨지안 초코 | 22,000 | — |
| 스프라이트 / 코카콜라 / 코카콜라 제로 / 산펠레그리노 / 에비앙 | 9,000 | — |
| 스텔라 draft | 18,000 | — |
| 버드와이저 (bottle) | 17,000 | — |

**푸드**
| 메뉴 | 시간 | 가격 |
|---|---|---|
| 더파빌리온 브런치 (signature) | 10:00–14:00 | 28,000 |
| 오늘의 수프 | — | 17,000 |
| 부라타 치즈 샐러드 | — | 25,000 |
| 토스트 | — | 12,000 |
| 화이트 갈릭 모짜렐라 피자 | 11:00–19:30 | 45,000 |
| 포테이토 베이컨 피자 | 11:00–19:30 | 45,000 |
| 마르게리타 페퍼로니 피자 | 11:00–19:30 | 40,000 |
| 브리오슈 치즈버거와 감자튀김 | 10:00–19:30 | 44,000 |
| 클럽샌드위치와 감자튀김 | 10:00–19:30 | 41,000 |

**베이커리·디저트**
| 메뉴 | 가격 | | 메뉴 | 가격 |
|---|---|---|---|---|
| 샤인머스켓 수제트 | 20,000 | | 바스크 치즈케이크 | 18,000 |
| 녹차 파운드 | 18,000 | | 아몬드 플로랑틴 데니쉬 | 13,000 |
| 허니 크림치즈 데니쉬 | 13,000 | | 마들렌 (피스타치오/코코넛/플레인 마카다미아/흑임자 무화과/초코) | 7,000 |

**플래터 세트** (2026.01.01–12.31)
| 세트 | 구성 | 가격 |
|---|---|---|
| BEER Platter | 스텔라 생맥주 2잔 + 플래터 1종 | 49,000 |
| WINE Platter | 와인 1병 + 플래터 1종 | 99,000 |
| └ 단품 | 플래터 39,000 / 와인 70,000 | |
> 플래터1 치즈 구이 · 플래터2 모둠 소시지(컨츄리·카레·그릴·매운맛·페퍼)

**와인 (하프/보틀)**
| 항목 | 가격 |
|---|---|
| 일레븐스 아워 셀러 샤도네이 750ml / 라 빅벨티 까베르네 소비뇽 750ML | 70,000 |
| 도멘 루 부르고뉴 피노누아 무통니에 375ML | 50,000 |
| 실레니 셀라 셀렉션 쇼비뇽 블랑 375ML | 45,000 |
| 호메세라 브륏 네이처 375ML | 35,000 |

---
### 4.8 LUX BAR — 프리미엄 소셜 바 / 그랜드 16F
`120석 · 20:00–01:00 (추석 연휴 21:00–01:00) · 3층 전 좌석 Bottle Zone, 첫 주문 시 SET MENU 필수 · 02-2022-0333 · WPC 식음 5% 적립`

**하이볼 / 칵테일**
| 메뉴 | 가격 |
|---|---|
| 프리미엄 하이볼 — 로열하이볼(발렌타인 21년) / 복분자 하이볼 | 49,000 |
| 하이볼 — 허니볼 / 클래식 / 얼그레이 / 진저 | 25,000 |
| 칵테일 (Alc) — 캄파리 스프리츠 / 복분자 위스키 사워 / 모나코 맥주 | 25,000 |
| 칵테일 (Non-Alc) — 레몬 스프리츠 / 석류 스프리츠 / 셜리 템플 | 25,000 |
| Classic Mojito / Colada | 29,000 |

**푸드**
| 메뉴 | 가격 |
|---|---|
| 활랍스터 구이와 전복구이 | 390,000 |
| 모둠 치즈와 계절과일 | 160,000 |
| 워커힐 수제 훈제연어 | 160,000 |
| 소고기 꽃등심 스테이크 (미국산) | 130,000 |
| 양갈비 스테이크 (호주산) | 110,000 |
| 워커힐 수제 소시지와 후라이드 치킨 | 85,000 |
| 마른안주 | 75,000 |
| 한우 차돌박이와 해산물 매콤한 짬뽕 | 68,000 |
| 하몽 세라노와 메론 / 체리 쥬빌레와 바닐라 아이스크림 | 65,000 |
| 콤비네이션 피자 | 58,000 |
| 브리오슈 치즈버거와 감자튀김 | 50,000 |

**Bottle Zone SET MENU** (3F 전용, 첫 주문 필수)
| 세트 | 가격 |
|---|---|
| SCOTCH WHISKEY SET2 | 620,000 |
| SINGLE MALT WHISKEY SET / BRANDY SET | 520,000 |
| VODKA SET2 / GIN SET2 / SCOTCH WHISKEY SET1 | 420,000 |
| VODKA SET1 / GIN SET1 / TEQUILA SET1 | 360,000 |
| Moet & Chandon Dom Pérignon | 1,010,000 |
| Laurent Perrier Grand Siècle | 890,000 |
| Gevrey Chambertin | 530,000 |
| Flowers Sonoma Chardonnay | 500,000 |
| Louis Michel et Fils Chablis | 460,000 |
| Laurent Perrier Brut | 410,000 |
| Veuve Clicquot Yellow | 390,000 |
| Clos du Val Cabernet Sauvignon | 380,000 |
| Moet & Chandon Brut Imperial | 370,000 |
| Girard Sauvignon Blanc / Château de Pez | 325,000 |

**스피릿 (glass / bottle)**
| 항목 | glass | bottle |
|---|---|---|
| Macallan Sherry Oak 30Y | — | 13,000,000 |
| Royal Salute 62 Gun | — | 9,900,000 |
| Macallan Sherry Oak 25Y | — | 6,500,000 |
| Ballantine's 30Y | 150,000 | 2,500,000 |
| Glengrant 21Y | 75,000 | 1,500,000 |
| Somos Añejo | — | 1,200,000 |
| Macallan Sherry Oak 18Y | — | 1,150,000 |
| Glenmorangie Signet | 55,000 | 950,000 |
| Johnnie Walker Blue | 50,000 | 900,000 |
| Royal Salute 21Y | 42,000 | 850,000 |
| Glengrant 18Y | 40,000 | 800,000 |
| Hennessy X.O | 47,000 | 780,000 |
| Aberlour A'bunadh | 30,000 | 590,000 |
| Patron Silver | 28,000 | 500,000 |
| (스카치) | 28,000 | 500,000 |
| Macallan Sherry Oak 12Y | 27,000 | 480,000 |
| Hennessy V.S.O.P / Woodford Reserve / Aberlour Double Cask 12Y | 25,000 | 410,000 |
| Jose Cuervo 1800' Añejo | 25,000 | 410,000 |
| Diplomatico Reserva / Glengrant 10Y | 21,000 | 340,000 |
| Grey Goose / Espolon Reposado / (진) | 20,000 | 310,000 |
| Johnnie Walker Black | 20,000 | 310,000 |
| Gordon's / Absolut / Jose Cuervo / Bacardi Light / Jack Daniel's Black | 18,000 | 280,000 |
| Heineken / Stella Artois | 20,000 | — |
| Kloud | 17,000 | — |

**샴페인 (bottle)**
| 항목 | 가격 |
|---|---|
| Armand de Brignac Brut Gold | 2,000,000 |
| L334 Louis Roederer Cristal | 1,850,000 |
| L321 Moet & Chandon Dom Pérignon Rosé | 1,650,000 |
| Krug Grande Cuvee | 1,100,000 |
| Moet & Chandon Dom Perignon | 900,000 |
| L330 Laurent Perrier Grand Siècle | 750,000 |
| Veuve Clicquot Yellow Label Brut | 600,000 |
| L327 Laurent Perrier Brut Rosé | 580,000 |
| L323 Bollinger Spécial Cuvée | 360,000 |
| M371 Charles Heidsieck Brut Réserve | 305,000 |
| Moet & Chandon Impérial Rosé | 300,000 |
| L337 Mailly Grand Cru Brut | 280,000 |
| L348 Laurent Perrier Brut | 275,000 |
| Veuve Clicquot Yellow | 260,000 |
| Moet & Chandon Brut Imperial | 255,000 (glass 45,000) |
| L336 Taittinger Brut Réserve | 220,000 |

**와인 (bottle)**
| 항목 | 가격 | | 항목 | 가격 |
|---|---|---|---|---|
| A015 Opus One | 1,450,000 | | D101 Sassicaia | 1,250,000 |
| Chene Bleu "Heloise" / "Abelard" | 400,000 | | B060 Gevrey Chambertin | 395,000 |
| 380,000 (화이트) | 380,000 | | Acumen Mountainside Cabernet | 370,000 |
| Chateau Maillet | 350,000 | | Lucia by Pisoni Soberanes Pinot Noir | 330,000 |
| B045 Errazuriz Don Maximiano Founder's | 305,000 | | Small Vines Sonoma Coast Chardonnay | 290,000 |
| Mollydooker Blue Eyed Boy Shiraz | 290,000 | | Brunel de la Gardine Condrieu | 250,000 |
| Clos du Val Cabernet Sauvignon | 245,000 | | D117 Barbaresco | 240,000 |
| Cascina Adelaide Barolo | 220,000 | | Raymond Reserve Selection Merlot | 220,000 |
| Pasetti Testarossa Trebbiano / Passo Bianco / Salomon Undhof Riesling | 200,000 | | Kalleske Moppa Shiraz | 200,000 |
| Girard Cabernet Sauvignon | 200,000 | | A017 Château de Pez | 190,000 |
| Poupille / Girard Sauvignon Blanc / Silver Spur Napa Cabernet / A027 Morande | 180,000 | | Louis Michel et Fils Chablis | 300,000 / 340,000 |
| D124 Gigondas / A028 Reserva / 160,000 계열 | 160,000 | | Chateau Grand Abord / M370 Dr Pauly Noble House Riesling | 150,000 |
| H285 Andeluna Altitud / A009 Chocolate Box Shiraz | 150,000 | | Arboleda Syrah / D098 Montgras Antu Cabernet / Montgras Antu Syrah / C069 Emiliana Coyam | 150,000 |
| Couly Dutheil Les Chanteaux (glass) | 30,000 | | Chene Bleu "Astralable" (glass) | 25,000 |

---
### 4.9 르 파사쥬 (Le Passage) — 구르메 스토어·델리 / 그랜드 1F
프리미엄 델리, 와인, 치즈, 피자, 샤퀴테리, 베이커리, 홀케이크, 워커힐 HMR(갈비탕·곰탕 팩)
> ⚠️ 가격표 미공개 — 현장 확인 필요 (§10)

### 4.10 클럽 라운지 (Grand Club by Walkerhill) — 그랜드 16F
복층 스카이 라운지, 최대 120석, 한강 전망. BAR 운영 20:00–01:00.
> ⚠️ 라운지 F&B 구성표 미공개 — 현장 확인 필요 (§10)

### 4.11 더글라스 라운지 / 라이브러리 — 더글라스 하우스 (성인 전용)
조식·올데이 라운지 및 북라운지.
> ⚠️ 메뉴 미공개 — 현장 확인 필요 (§10)

### 4.12 리버파크 풀바 / 푸드트럭 / F&B 딜리버리 — 계절
메인풀 50m×19m, 프리미엄 카바나, 온수 자쿠지, 웰니스 프로그램.
> ⚠️ 메뉴 미공개 — 현장 확인 필요 (§10)

### 4.13 애스톤 하우스 / 인룸 다이닝 / 뱅큇
프라이빗 다이닝(단독동) · 룸서비스(식음 금액이용권 사용 가능) · 연회 케이터링(BEO 기반).
> ⚠️ 메뉴 미공개 — 현장 확인 필요 (§10)

---

## 5. 객실 · 공간 Enum — `RoomType` / `VenueType`

`ReservationMachine.roomType` / `StayMachine.assignedRoomType` 의 도메인.
요금은 2026-09-20 기준 **표준 요금(Rack Rate, 세금·봉사료 포함)** — 실판매가 아님.

### 직교 속성 축 (RoomType과 별개로 조합됨)

| 축 | enum |
|---|---|
| `View` | `ACHASAN_MOUNTAIN`(아차산 뷰) · `HANGANG_RIVER`(한강/리버 뷰) · `CITY` · `NONE` |
| `BedType` | `DOUBLE_KING` · `DOUBLE_QUEEN` · `TWIN_SINGLE2` · `TWIN_QUEEN2` · `TWIN_DOUBLE2` · `ROUND` · `BUNK`(2층 싱글) · `MIXED` |
| `LoungeAccess` | `NONE` · `GRAND_CLUB`(16F) · `DOUGLAS_LOUNGE` |
| `ExtraBed` | `NOT_AVAILABLE` · `AVAILABLE_PAID`(비스타 KRW 60,500/박) |
| `RoomFeature` | `BALCONY` · `BATHTUB` · `WHIRLPOOL` · `KITCHEN` · `DINING_ROOM` · `STUDY` · `DRESSROOM` · `PRIVATE_BAR` · `LIVING_ROOM` · `MINI_LIVING` |
| `ConceptRoom` | `NONE` · `KIDS` · `BARBIE` · `VEGAN` · `TRADITIONAL` · `HONEYMOON` · `PET`(비스타) |
| `SmokingPolicy` | `NON_SMOKING_ALL` (더글라스 위반 시 벌금 KRW 250,000) |

### 5.1 그랜드 워커힐 서울 — `GRAND_*` (16종)
체크인 15:00 / 체크아웃 11:00

| RoomType | 위치 | 크기 | 수용 | 침대 | 전망 | 구성 | 표준 요금 |
|---|---|---|---|---|---|---|---|
| `GRAND_STANDARD` | 본관 3·5F | 30㎡ | 2인 | 트윈(싱글2) | — | 침실·욕실·화장실 | 798,600 |
| `GRAND_DELUXE` | 본관 | 30㎡ | 2인 | 더블(퀸1) / 트윈(싱글2) | 아차산·한강 | 침실·욕실·화장실 | 아차산 810,700 / 한강 871,200 |
| `GRAND_DELUXE_SUITE` | 본관 14F | 57㎡ | 성인 3인 | 트윈(퀸1+싱글1) | 아차산·한강 | +거실 | 아차산 1,004,300 / 한강 1,064,800 |
| `GRAND_KIDS_DELUXE_SUITE` | 본관 14F | 57㎡ | — | 퀸1+싱글1+2층싱글1 | 아차산 | +거실 | 아차산 1,004,300 |
| `GRAND_FAMILY_DELUXE_SUITE` | 8F (17실) | 54㎡ | 성인 3인 | 트윈(더블2) | 아차산·한강 | +거실 | 아차산 1,040,600 / 한강 1,101,100 |
| `GRAND_VEGAN_SUITE` | 8F (3실) | 54㎡ | 성인 3인 | 트윈(더블2) | 아차산 | +거실 | 아차산 1,040,600 |
| `GRAND_CLUB_DELUXE` | 8–15F (21실) | 30㎡ | 2인 | 더블(퀸1) / 트윈(싱글2) | 아차산·한강 | 침실·욕실·화장실 | 아차산 1,040,600 / 한강 1,101,100 |
| `GRAND_CLUB_SUITE` | 9·10F(34실), 15·16F(22실) | 54㎡ | 2인 | 더블(킹1) / 트윈(더블2) | 아차산·한강 | +거실 | 아차산 1,270,500 / 한강 1,343,100 |
| `GRAND_CLUB_BARBIE_SUITE` | 16F (2실) | 54㎡ | 미표기 | 더블(킹1) | 아차산 | +거실 | **미표기** (렌더링 확인: 표준요금 필드 없음. 패키지 689,000~ 로만 판매) |
| `GRAND_CLUB_TRADITIONAL_SUITE` | 9·10F (6실) | 54㎡ | — | 트윈(더블2) | 한강 | +거실 | 1,343,100 |
| `GRAND_CLUB_HONEYMOON_SUITE` | 8F (3실) | 54㎡ | 2인 | 더블(킹1) | 한강 | +거실 | 1,343,100 |
| `GRAND_SUITE` | 17F (4실) | 81–96㎡ | 2인 | 더블(킹1) | 아차산·한강 | +거실 | 아차산 2,904,000 / 한강 2,976,600 |
| `GRAND_FAMILY_SUITE` | 15·16F (6실) | 82㎡ | 4인 | 더블(킹1)+트윈(싱글2) | 아차산·한강 | +거실 | 아차산 3,339,600 / 한강 3,412,200 |
| `GRAND_ROYAL_SUITE` | 17F (1실) | 110㎡ | 4인 | 더블(킹1)+더블(퀸1) | 아차산 | +거실 | 4,356,000 |
| `GRAND_PREMIER_SUITE` | 17F (1실) | 133㎡ | 4인 | 더블(킹1)+더블(퀸1) | 한강 | +거실 | 10,164,000 |
| `GRAND_PRESIDENTIAL_SUITE` | 17F (1실) | 274㎡ | 미표기 | 더블(킹1) | 아차산·한강 | +거실·집무실 | **미표기** (렌더링 확인) |

클럽 라운지 접근권(`LoungeAccess = GRAND_CLUB`) 보유: `GRAND_CLUB_*`, `GRAND_SUITE`, `GRAND_FAMILY_SUITE`, `GRAND_ROYAL_SUITE`, `GRAND_PREMIER_SUITE`, `GRAND_PRESIDENTIAL_SUITE`

### 5.2 비스타 워커힐 서울 — `VISTA_*` (11종)
체크인 15:00 / 체크아웃 11:00 · 엑스트라 베드 KRW 60,500/박 · 무료 미니바(맥주2·탄산1·에이드1·칩스1)

| RoomType | 크기 | 침대 | 전망 | 구성 | 표준 요금 |
|---|---|---|---|---|---|
| `VISTA_DELUXE` | 42㎡ | 더블(킹1) / 트윈(퀸2) | 마운틴·리버 | 침실·욕실·화장실 | 마운틴 1,028,500 / 리버 1,089,000 |
| `VISTA_DELUXE_BALCONY` | 42㎡ | 더블(킹1) | 리버 | +발코니 | 1,089,000 |
| `VISTA_SPA_DELUXE` | 42㎡ | 더블(킹1) | 리버 | +욕조 | 1,089,000 |
| `VISTA_JUNIOR_CORNER_SUITE` | 56㎡ | 라운드(1) | 마운틴·리버 | 침실·욕실·화장실 | 마운틴 1,355,200 / 리버 1,415,700 |
| `VISTA_JUNIOR_SPA_SUITE` | 56㎡ | 더블(킹1) | 리버 | +욕조 | 1,415,700 |
| `VISTA_STUDIO_SUITE` | 70㎡ | 라운드(1) | 마운틴 | 침실·욕실·화장실 | 1,657,700 |
| `VISTA_CORNER_SUITE` | 98㎡ | 라운드(1) | 마운틴·리버 | +거실 | 마운틴 2,541,000 / 리버 2,613,600 |
| `VISTA_SPA_SUITE` | 98㎡ | 더블(킹1) | 리버 | +거실·월풀 | 2,613,600 |
| `VISTA_AMBASSADOR_SUITE` | 118㎡ | 더블(킹1) | 리버 | +거실 | 4,356,000 |
| `VISTA_SUPER_SPA_SUITE` | 158㎡ | 더블(킹1) | 리버 | +거실·다이닝룸·월풀·주방 | 10,164,000 |
| `VISTA_PRESIDENTIAL_SUITE` | 237㎡ | 더블(킹1) | 리버·마운틴·시티 | +거실·다이닝룸·서재·드레스룸·프라이빗바·화장실2·월풀 | 문의 |

### 5.3 더글라스 하우스 — `DOUGLAS_*` (3종)
**성인 전용 (Adults-Only)** · 13세 이하·반려동물 동반 불가 · 기준 2인 · 추가 침대 없음 · 전 객실 금연(위반 시 25만원) · 체크인 15:00 / 체크아웃 11:00 · 프런트 02-450-4653

| RoomType | 크기 | 수용 | 침대 | 구성 | 표준 요금 |
|---|---|---|---|---|---|
| `DOUGLAS_DELUXE` | 27㎡ | 2인 | 더블(킹1) / 트윈(싱글2) | 침실·욕실·화장실·발코니 | 895,400 |
| `DOUGLAS_TRADITIONAL_SUITE` | 53㎡ | 2인 | 더블(킹1) | 침실·미니거실·욕실·화장실 | 1,101,100 |
| `DOUGLAS_SUITE` | 72㎡ | 2인 | 더블(킹1) | 침실·미니거실·욕실·화장실·발코니 | 1,185,800 |

공통 특전 → `PackageEntitlementMachine` 자동 부여:
더글라스 라운지 Light Breakfast · Douglas Hour · 무료 미니바(생수2·탄산수1) · 비대면 모바일 체크인/아웃 · 그랜드 피트니스 & 실내 수영장 · 워커힐 리무진 셔틀 24시간 · 그랜드 발렛 1회 무료 · 라이브러리·멀티룸 이용
※ 추가 침구 유료 제공은 `DOUGLAS_TRADITIONAL_SUITE` 한정

### 5.4 빌라 — `VILLA`
숲 속 별장, 한강 전망. 독립 공간.

> **핵심: 빌라는 일반 객실 재고가 아니다.**
> 공식 안내 원문 — *"빌라는 **장기 임대형 주거 공간**으로 운영되며, **단기 예약은 어려울 수 있습니다**. 빌라 예약 문의는 전화로 부탁 드립니다."* (1670-0005)
> 객실 상세 정보 블록은 렌더링 후에도 **비어 있음** — 면적·수용인원·침대·표준요금 모두 비공개.

따라서 `ReservationMachine`에서 빌라는 일반 예약 플로우를 타지 않는다. 별도 전이가 필요하다:
```
VILLA_INQUIRY_PHONE_ONLY → LONG_TERM_LEASE_NEGOTIATION → LEASE_CONTRACTED
                         ↘ SHORT_TERM_REQUEST → SHORT_TERM_DECLINED / SHORT_TERM_EXCEPTION_APPROVED
```
단, 패키지 `GRAND_PKG_VILLA_ONE_STAY`(KRW 899,000~)는 단기 상품으로 판매 중 → 예외 경로가 실재함.

### 5.5 애스톤 하우스 — `ASTON_HOUSE`
**객실 페이지가 존재하지 않는다.** `/grandwalkerhillseoul/room/Aston-House` 및 `/room/Aston-House` 모두 에러 페이지로 응답 (2026-09-20 확인).
실제 애스톤 하우스는 **객실 카테고리가 아니라 연회 공간**으로 운영되며, 그 안에 **VIP 스위트 객실**이 부대시설로 포함된다 (§5.7 참조).

- Wilson & Associates 디자인, 유럽풍 대저택 형태의 별관
- 실내 연회 공간 330㎡ + 야외 가든 510㎡
- 수용 50~150명
- 부대시설: 4개 소규모 실내 연회 공간 · **프라이빗 다이닝룸** · **VIP 스위트 객실**

→ `ASTON_HOUSE_VIP_SUITE`는 온라인 예약 불가, 연회 계약에 부속되는 객실. `PrivateDiningMachine` / `BanquetMachine` 경유로만 도달.

### 5.6 다락휴 & 인천공항 트랜짓 호텔 — `HourlyStayMachine` (M11)

숙박이 **박(night)이 아니라 시간 블록** 단위라 `StayMachine`과 전이 구조가 다르다. 별도 머신으로 분리.

```
SLOT_SEARCHED · SLOT_BOOKED · DAY_USE_BLOCK_ACTIVE · OVERNIGHT_BLOCK_ACTIVE
TIME_BLOCK_RUNNING · EXTENSION_REQUESTED · EXTENSION_GRANTED_ONSITE · EXTENSION_DENIED
BLOCK_EXPIRING_WARNED · BLOCK_EXPIRED · OVERSTAY_CHARGED · CHECKED_OUT
```
가드 조건:
- 다락휴 Day Use: 08–20시 내 최대 3블록(9시간). 이 범위를 벗어나면 Overnight 요금 적용
- 다락휴 Overnight 연장은 당일 객실 상황에 따라 **현장에서만** 가능 → `EXTENSION_GRANTED_ONSITE`
- 트랜짓 호텔: 20:00 이후 투숙은 12시간 사용이 기본. 4시간은 6시간 요금 적용

**다락휴 (캡슐 호텔)** — 인천공항 T1 / T2 / 여수엑스포

| RoomType | 위치 | 면적 | 침대 | 기본 3시간 | 12시간 | 추가 시간당 |
|---|---|---|---|---|---|---|
| `DARAKHYU_T1_SINGLE` | T1 | 4.3㎡ | 2000×950 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T1_SINGLE_SHOWER` | T1 | 5.8㎡ | 2000×950 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T1_DOUBLE` | T1 | 5.3㎡ | 2000×1500 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T1_DOUBLE_SHOWER` | T1 | 7.3㎡ | 2000×1500 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T2_SINGLE` | T2 | 4.39㎡ | 2000×950 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T2_DOUBLE` | T2 | 5.56㎡ | 2000×1500 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T2_DOUBLE_SHOWER` | T2 | 8.80㎡ | 2000×1500 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_T2_DOUBLE_HUB` | T2 | 8.81㎡ | 2000×1500 | 32,000~48,000 | 69,000~94,000 | 10,000 |
| `DARAKHYU_YEOSU_*` | 여수엑스포 D동 3F | — | — | — | — | 061-661-5400 |

**인천공항 트랜짓 호텔** — T1 / T2

| RoomType | 6시간 | 12시간 | 16–24시간 | 추가 1시간 |
|---|---|---|---|---|
| `TRANSIT_T1_STANDARD` | 90,000 (D/T) | 180,000 | 220,000 | 15,000 |
| `TRANSIT_T1_DELUXE` | 83,490(S) / 98,010(D) | 166,980 / 196,020 | 217,800 / 242,000 | 12,100 |
| `TRANSIT_T1_FAMILY` | 105,000(D/T) / 125,000(TRPL) | 210,000 / 250,000 | 260,000 / 290,000 | 15,000 |
| `TRANSIT_T1_SUITE` | 114,950(S) / 129,470(D) | 229,900 / 258,940 | 278,300 / 302,500 | 12,100 |
| `TRANSIT_T2_STANDARD` | 90,000 (D/T) | 180,000 | 220,000 | 15,000 |
| `TRANSIT_T2_FAMILY` | 105,000(D/T) / 125,000(TRPL) | 210,000 / 250,000 | 260,000 / 290,000 | 15,000 |

### 5.7 연회·미팅 공간 Enum — `VenueType`

`OutletSessionMachine`(프라이빗 다이닝·뱅큇) 및 `BanquetMachine`의 공간 도메인.
컨벤션 센터 10곳 + 애스톤 하우스 + 명월관 가든 등 야외 연회장 + 소규모 회의실.
수용인원은 **배치 형태(Setup)별로 달라진다** → `SetupType` enum: `ROUND` · `BUFFET` · `CLASSROOM` · `THEATER` · `U_SHAPE`

#### 비스타홀 — 비스타 워커힐 서울 B2
1,305㎡ / 천고 6m / 400~800명 / 3개 독립 공간 분리 가능 / 한강 조망
부대: 개별 대기실 · VIP 전용룸 · 휴대품 보관소 / 장비: LED · 전동 스크린 · LCD Projector · 초고속 인터넷 · Wi-Fi

| Venue | Round | Buffet | Classroom | Theater | U-Shape | ㎡ | W×L×C (m) |
|---|---|---|---|---|---|---|---|
| `VISTA_HALL_1` | 280 | 200 | 252 | 400 | 75 | 461 | 20.5×22.5×6 |
| `VISTA_HALL_2` | 120 | 90 | 112 | 200 | 60 | 256 | 17×15.2×6 |
| `VISTA_HALL_3` | 180 | 130 | 144 | 250 | 66 | 312 | 20.5×15.2×6 |
| `VISTA_HALL_1_2` | 600 | 400 | 560 | 900 | 255 | 844 | 37.5×22.5×6 |
| `VISTA_HALL_2_3` | 320 | 230 | 320 | 500 | 90 | 570 | 37.5×15.2×6 |
| `VISTA_HALL_1_2_3` | 1,000 | 650 | 960 | 1,500 | 395 | 1,305 | 58×22.5×6 |
| `IDA_1` | — | — | — | — | 16 | 53 | 8.3×6.4×2.85 |
| `IDA_2` | — | — | — | — | 11 | 40.8 | 7.7×5.3×2.85 |

#### 워커홀 — 컨벤션센터 1F (2018.09 오픈)
819㎡ / 천고 6m / 300~400명 / 2개 독립 공간 분리 가능 / 전용 로비·프리펑션
부대: 개별 대기실 · VIP 전용룸 / 장비: 전동 스크린 · LCD Projector · 초고속 인터넷 · Wi-Fi

| Venue | Round | Buffet | Classroom | Theater | U-Shape | ㎡ | W×L×C (m) |
|---|---|---|---|---|---|---|---|
| `WALKER_HALL_1` | 200 | 150 | 220 | 400 | 60 | 407.2 | 14.3×28×6 |
| `WALKER_HALL_2` | 200 | 150 | 220 | 400 | 60 | 412.1 | 14.5×28×6 |
| `WALKER_HALL_1_2` | 420 | 300 | 440 | 800 | 120 | 819.3 | 28.8×28×6 |
| `AMBER_1` | 10 | — | 20 | 35 | 12 | 35.5 | 5.2×7.1×3 |
| `AMBER_2` | 10 | — | 24 | 40 | 12 | 37.5 | 6.7×5.5×3 |

#### 그랜드 홀 — 그랜드 워커힐 서울 B1
1,061.8㎡ / 대연회장 250~550명, 소연회장 20~140명 / 6개 홀 + Breakout room / 1개 대연회장을 4개로 분리·통합
부대: 전용 Foyer · 리셉션/등록데스크 전용 로비 / 장비: LED · 전동 스크린 · LCD Projector · 최신 조명·A/V · Wi-Fi

| Venue | Round | Buffet | Classroom | Theater | U-Shape | ㎡ | W×L×C (m) |
|---|---|---|---|---|---|---|---|
| `GRAND_HALL_1` | 300 | 250 | 256 | 512 | 56 | 533.2 | 24.8×21.5×3.1 |
| `GRAND_HALL_2` | 60 | — | 48 | 96 | 32 | 119.3 | 14.2×8.4×3.1 |
| `GRAND_HALL_3` | 40 | — | 44 | 88 | 24 | 88.2 | 10.5×8.4×3.1 |
| `GRAND_HALL_2_3` | 100 | 80 | 92 | 184 | 56 | 208 | 24.7×8.4×3.1 |
| `GRAND_HALL_1_2_3` | 500 | 450 | 328 | 696 | — | 741 | 24.8×29.87×3.1 |
| `GRAND_HALL_4` | 50 | — | 76 | 140 | 32 | 135.7 | 10.7×12.9×2.9 |
| `GRAND_HALL_5` | 50 | — | 76 | 140 | 20 | 113.9 | 9×12.9×2.9 |
| `GRAND_HALL_4_5` | 100 | 80 | 152 | 280 | 52 | 250 | 19.7×12.9×2.9 |
| `GRAND_HALL_6` | 40 | — | 32 | 56 | 20 | 70.1 | 7.8×9×2.9 |

#### 아트홀 / 파인 / 오크 — 컨벤션센터 4F
아트홀 320㎡ 60~150명 (자연채광) / 파인·오크 69·66㎡ 30~40명
부대: 넓은 Foyer · 파인·오크룸을 대기 장소 및 VIP Room으로 활용

| Venue | Round | Buffet | Classroom | Theater | U-Shape | ㎡ | W×L×C (m) |
|---|---|---|---|---|---|---|---|
| `ART_HALL` | 170 | 140 | 160 | 320 | 48 | 320 | 14.25×19.25×3.8 |
| `PINE_ROOM` | 40 | — | 48 | 80 | 30 | 69 | 6×11.5×2.4 |
| `OAK_ROOM` | 30 | — | 28 | 56 | 28 | 66 | 5.5×12×2.8 |

#### 애스톤 하우스 — 별관
실내 330㎡ + 야외 가든 510㎡ / 50~150명 / Wilson & Associates 디자인

| Venue | Round | Classroom | Theater | U-Shape | ㎡ | W×L×C (m) |
|---|---|---|---|---|---|---|
| `ASTON_LAVENDER` | 60 | 64 | 80 | 24 | 142 | 17.5×8.1×1.9 |
| `ASTON_JASMINE` | 40 | — | — | — | 113 | 18.8×3.7×1.9 |
| `ASTON_ANGELICA` | 20 | — | — | — | 75 | 7.6×10.5×1.9 |
| `ASTON_GARDEN` (야외) | 280 | 200 | 300 | — | — | 34×15 |

#### 야외 연회 / 소규모 회의

| Venue | 위치 | 수용 | 비고 |
|---|---|---|---|
| `MYONGWOLGWAN_GARDEN` | 명월관 별관 | 60~400명 | 아차산·한강 조망 야외. 50명 미만은 명월관 본당·별관 이용 |
| `DOUGLAS_MEETING_ROOM` | 더글라스 하우스(별관) 2F | 최대 12명 | 숲속 소규모 회의 |

#### 웨딩 전용 조합
`WEDDING_VISTA_HALL`(측면 통유리 한강·도심 뷰) · `WEDDING_WALKER_HALL` · `WEDDING_ASTON_HOUSE`(유러피언 프라이빗 하우스 웨딩) · `WEDDING_SMALL`(스몰 웨딩)
가족 연회(`FAMILY_BANQUET`): 결혼식·약혼식·돌잔치·은혼식·금혼식·회갑·칠순·팔순 → 식음료 5% 할인 (§7)

---

## 6. 패키지 Enum — `PackageType` + M10 `PackageEntitlementMachine`

### M10. PackageEntitlementMachine (특전 1건 = 인스턴스 1개)
```
ENTITLEMENT_GRANTED → ELIGIBLE_WINDOW_OPEN → REDEEM_REQUESTED → REDEEMED
                                            ↘ SUBSTITUTED       (대체 상품 제공)
                                            ↘ BLACKOUT_BLOCKED  (제외 일자)
                                            ↘ WEATHER_BLOCKED   (우천·기상)
                                            ↘ CAPACITY_BLOCKED
                                            ↘ AGE_RESTRICTED    (17세/12세 제한)
                                            ↘ EXPIRED_UNUSED · FORFEITED
```
공통 가드: `BLACKOUT_DATE` = 7/21–8/15, 12/24, 12/25, 12/31, 토요일(일부 쿠폰)

### 6.1 그랜드 워커힐 서울 패키지 (9종)

| PackageType | 기간 | 최저가 | 구성 |
|---|---|---|---|
| `GRAND_PKG_CAMCNIC_IN_THE_FOREST` (8829)<br>[가을] 캠크닉 인더 포레스트 | 2026.08.24–11.30 | 247,000~ | 포레스트 파크 전용 운영(08/24–09/27 11–21시, 모닥불 17:00–20:30 / 09/28–11/30 11–20시, 모닥불 16:00–19:30) · 숲속 책방(땡스북스 큐레이션, 외부 반출 불가) · LIGHTREE 소파 라운지 · 트래블 파우치<br>대체일 10/10–11, 10/17–18, 10/24–25 → 콤비네이션 피자(S) To-go (르파사쥬 11:00–19:30) |
| `GRAND_PKG_WINE_FOREST` (8837)<br>Wine Forest | 2026.08.24–10.25 | 267,000~ | 스탠다드 룸~ · 2026 Autumn Wine Fair '구름 위의 산책' 입장권 2매(110,000원 상당) |
| `GRAND_PKG_SEONGSU_V2` (8797)<br>두근두근 성수 Ver.2 | 2026.05.18–12.31 | 290,000~ | 딜럭스 룸 · 웰니스 사우나 1회(2인) · 성수 향수공방 '닷노트' 원데이 클래스(2인) · 올리브영 기프트카드 · 폴라로이드 대여(선착순) · 1박 or 2박 |
| `GRAND_PKG_MEMORABLE_FAMILYCATION` (8587) | 2024.01.01–2026.12.31 | 457,000~ | 키즈 딜럭스 스위트 · 인룸 키즈 텐트 · 르 파사쥬 콤비네이션 피자(L) To-go |
| `GRAND_PKG_BEGIN_VEGAN` (8388) | 2024.01.01–2026.12.31 | 459,000~ | 국내 최초 비건룸(그랜드 비건 스위트) · 비건 미니바(레몬에이드 플러스 라임, 비건콜라, 헌터스 비건 트러플 포테이토칩, 젤러스스위트 그리즐리베어 비건젤리) · 웰컴 와인 ANDELLUNA White (100% Vegan Friendly) · 더뷔페 조식 |
| `GRAND_PKG_THE_TRIPLE_STAY` (8625) | 2025.03.10–2026.12.31 | 659,000~ | 3인 패키지 · 클럽 스위트 트윈 or 허니문 스위트 · 클럽라운지 혜택(3인) · 주중 한정 Late Check Out 12:00 · 기프트 |
| `GRAND_PKG_BARBIE_SUITE` (8588) | 2024.02.29–2026.12.31 | 689,000~ | 바비 콘셉트 스위트 · 클럽 라운지 혜택 · 바비 인형 기프트 |
| `GRAND_PKG_VILLA_ONE_STAY` (5181)<br>[빌라] One Stay, Only Yours | 2025.03.24–2026.12.31 | 899,000~ | 프라이빗 빌라 · 룸서비스 · 웰컴 플래터 |
| `GRAND_PKG_EARLY_BIRD_SALE` (6141) | 2024.01.01–2026.12.31 | 247,000 | 홈페이지 사전 예약 특가 |

그랜드 공통 특전(전 패키지): 포레스트 파크 입장 · 실내 수영장 & 피트니스 무료(피트니스 17세 이상) · 호텔 레스토랑 10% 할인 · 객실 무선인터넷 · 객실 미니바 무료(주류·음료·스낵)

### 6.2 비스타 워커힐 서울 패키지 (9종)

| PackageType | 기간 | 최저가 | 구성 |
|---|---|---|---|
| `VISTA_PKG_AUTUMN_CAMCNIC` (8830)<br>[가을] 어텀 캠크닉 | 2026.08.24–11.30 | 307,000~ | 그랜드 캠크닉과 동일 포레스트 파크 운영·모닥불·숲속 책방·LIGHTREE 라운지 |
| `VISTA_PKG_EARLY_BIRD_SALE` (6143) | 2024.01.01–2026.12.31 | 307,000~ | 사전 예약 특가 |
| `VISTA_PKG_WINE_FOREST` (8838) | 2026.08.24–10.25 | 327,000~ | 딜럭스 룸~ · Autumn Wine Fair 입장권 2매 |
| `VISTA_PKG_ALL_THAT_WELLNESS` (8744) | 2026.01.01–12.31 | 337,000~ | 딜럭스~주니어 스위트 · 웰니스 사우나 · 골프 VIP 타석 60분 · 숏게임 콤플렉스 이용권 2매 · 오렌지 베이글 할인 · 테네즈 파크 2시간(체크인 당일 16:00–18:00) |
| `VISTA_PKG_KIDS_PLAY_FOREST_PARK` (8745) | 2026.01.01–12.31 | 419,000~ | 딜럭스~주니어 스위트 · PLAY Kit & 아메리카노 2잔 · 더뷔페 조식 · 주중 투숙 추가 혜택 |
| `VISTA_PKG_VISTA_X_THE_BUFFET` (8486) | 2025.12.01–2026.11.30 | 537,000~ | 딜럭스~주니어 스위트 · 더뷔페 중식 2인 or 석식 2인 · 12PM Late Check Out |
| `VISTA_PKG_OH_MY_PET` (3268) | 2024.01.01–2026.12.31 | 589,000~ | 비스타 펫 컨셉 룸 · 룸서비스 크레딧 10만원 · O.M.P 웰컴 키트(장난감·비스타 펜던트·배변봉투) · 펫 비치용품(전용 침대·베개·식탁&식기·Bathrobe&Towel) |
| `VISTA_PKG_VERY_SUITE_STAY` (8771)<br>[스위트] | 2026.03.27–2026.12.31 | 787,000~ | 스튜디오 스위트~앰버서더 스위트 · 더뷔페 조식 · 해피 아워(그랜드 16F, 17:30–19:30) · 웰니스 사우나 |
| `VISTA_PKG_MY_LITTLE_STAR` (8456)<br>[돌잔치] | 2025.12.11–2026.11.30 | 2,000,000~ | 비스타 슈퍼 스파 스위트 · 더뷔페 디너 4인 · 객실 내 프라이빗 돌잔치(비용 별도) |

비스타 공통 특전: 포레스트 파크 입장 · 시그니처 보타닉 가든 SKYARD 입장 · 객실 미니바 무료 · 워커힐 레스토랑 10% 할인 · 피트니스 & 실내 수영장 무료(17세 이상) · 무선인터넷

### 6.3 더글라스 하우스 패키지 (3종)

| PackageType | 기간 | 최저가 | 구성 |
|---|---|---|---|
| `DOUGLAS_PKG_SOLO_REST` (8770)<br>[1인] 나홀로 쉼 | 2026.03.30–2026.12.31 | 259,000~ | 1인 전용 · 더글라스 딜럭스 더블룸 · 라운지 Light Breakfast & Douglas Hour · 웰컴 기프트(스테이 가이드+필사 도서+아로마 리추얼 키트) · 아이 필로우 · 웰니스 사우나 1회 · 객실 상황에 따른 리버뷰 업그레이드 |
| `DOUGLAS_PKG_CHECKIN_BULMEONG` (8831)<br>[가을] 체크인 불멍 | 2026.08.24–11.30 | 319,000~ | 포레스트 파크 모닥불·숲속 책방·LIGHTREE 라운지 |
| `DOUGLAS_PKG_REST_TOGETHER` (3262) | 2024.01.01–2026.12.31 | 387,000~ | 2~3인 · 딜럭스: 피자힐 콤비네이션 피자 To-go / 트레디셔널 스위트: 콰트로 피자 To-go · 라운지 Light Breakfast & Douglas Hour · Late Check Out 13:00 |

더글라스 공통: 포레스트 파크 입장 · 무료 발렛 1회 · 라이브러리·멀티룸 무료 · 그랜드 실내 수영장 & 피트니스 무료
모바일 체크인 플로우 → `ONLINE_CHECKIN_*` 전이: 투숙 전일 10:00 사전 등록(등록카드·주차등록·요금결제) → 당일 객실 준비 완료 시 QR 알림톡 → 로비 키오스크 QR로 키 수령 → 모바일 체크아웃(키는 객실 테이블에 비치)

### 6.4 프로모션 (`PromotionType` — 객실 미포함, 식음·상품 단독)

| PromotionType | 기간 | 가격 |
|---|---|---|
| `PROMO_AUTUMN_HOLIDAY_AT_WALKERHILL` (추석) | 2026.09.24–10.04 | — |
| `PROMO_ONDAL_WILD_PINE_MUSHROOM` [온달] 자연송이 가을맞이 | 2026.09.01–09.30 | 85,000 |
| `PROMO_GEUMRYONG_CHUMIJINHYANG` [금룡] 추미진향 | 2026.09.01–10.30 | 150,000 |
| `PROMO_CHUSEOK_GIFT_2026` 2026 워커힐 추석 선물 특선 | 2026.09.07–09.27 | 48,000~ |
| `PROMO_SIGNATURE_LIQUEUR` 워커힐을 담다: 시그니처 리큐어 | 2026.07.01–11.30 | 45,000 |

---

## 7. 할인·정산 규칙 (state guard 조건)

`WPC_HEADCOUNT_DISCOUNT_APPLIED` 의 전이 가드. 대상 업장: 온달 · 금룡 · 더뷔페 · 명월관 · MOEGI · 금룡(삼일빌딩점)

| 인원 | 할인 | 인원 | 할인 | 인원 | 할인 |
|---|---|---|---|---|---|
| 1–2인 | 20% | 7인 | 14% | 13인 | 15% |
| 3인 | 33% | 8인 | 25% | 14인 | 14% |
| 4인 | 25% | 9인 | 22% | 15인 | 13% |
| 5인 | 20% | 10인 | 20% | 16인 | 12% |
| 6인 | 16% | 11인 | 18% | 17인↑ | 11% |
| | | 12인 | 16% | | |

기타 식음 할인:
| 업장 | 혜택 |
|---|---|
| 피자힐 | 10% |
| CLUB LOUNGE & BAR (BAR 20:00–01:00 한정) | 20% |
| 르 파사쥬 (베이커리류) | 20% |
| 더파빌리온 | 10% |
| 공통 음료·주류 / Side Dish | 10% (와인 제외) |
| 가족 연회 (결혼·약혼·돌·은혼·금혼·회갑·칠순·팔순) | 식음료 5% |

**할인 배제 조건 → `DISCOUNT_STACK_REJECTED`**
- 테이블당 회원카드 1개만 적용, 테이블 분할·2카드 중복 불가
- 포장 주문, 상차림 등 외부 아이템, **명월관 별채**, 기업연회, **룸서비스** 제외
- 제휴카드 중복 할인 제한
- 명월관 오마카세 메뉴는 할인·쿠폰 사용 제한
- 12/24 및 프로모션·이벤트 건 제한

**식음료 금액 이용권** 사용 가능 업장: 온달, 금룡, 더뷔페, 명월관, MOEGI, CLUB LOUNGE & BAR(BAR 한정), 룸서비스, 금룡(삼일빌딩점), 피자힐, 더파빌리온, 르 파사쥬
- 1회 최대 2~4매 중복 (등급별)
- 룸 후불 룸서비스는 체크아웃 시 프런트 제시, 모바일 체크아웃 시 사용 불가

**WPC 등급 enum**: 연회비 기준 50/55만원 · 120만원 · 170만원 · 450만원 (OAK / MAPLE / NOBLE PINE 등)

---

## 8. 시간 모델 — Transition Duration & Travel Time

지금까지 §1–§7은 **어떤 상태가 있는가**만 정의했다. 여기서는 **상태 사이를 이동하는 데 걸리는 시간**을 붙여, 24시간 타임라인 위에서 정합하게 시뮬레이션할 수 있게 한다.

### 8.0 출처 표기

| 기호 | 의미 |
|---|---|
| ◎ | walkerhill.com 공식 게시 수치 (2026-09-20~21 확인) |
| ○ | 공식 게시된 운영시간·정책에서 논리적으로 확정되는 값 |
| △ | **추정치** — 공식 미공개. 현장 실측으로 교체해야 함 |

> ⚠️ 구내 이동 시간(객실↔로비↔업장)은 워커힐이 공개하지 않는다. △ 표시 값은 부지 규모·층수에서 역산한 **설계용 기본값(placeholder)** 이며, 실측 전에는 SLA·고객 안내에 쓰면 안 된다.

### 8.1 시간의 3종류

하나의 전이에 걸리는 시간을 한 덩어리로 다루면 스케줄러가 틀린다. 세 가지로 분해한다.

| 종류 | 정의 | 기호 |
|---|---|---|
| **Dwell** | 그 상태에 **머무는** 시간 (식사, 투숙, 시술) | `D(state)` |
| **Latency** | 전이 자체의 처리 시간 (수속, 조리, 승인) | `L(transition)` |
| **Travel** | 물리적 위치 이동 시간 | `T(locA → locB)` |

추가로 **대기(Wait)** 는 Travel과 분리한다. 셔틀은 연속이 아니라 배차이므로:

```
T_effective(A→B, t) = W_headway(t) + T_ride(A→B)
W_headway(t) = 배차간격(t) / 2        (균등 도착 가정, 기댓값)
             = 배차간격(t)            (최악, p100)
```

### 8.2 Location 그래프 — 노드

```
[외부]   ICN_T1 · ICN_T2 · GMP · GWANGNARU_STN(5호선) · GANGBYEON_STN(2호선) · SEONGSU
[진입]   HOTEL_GATE · PARKING_TOWER_B1 · PARKING_TOWER_4F · VALET_DESK
[그랜드] GRAND_LOBBY · GRAND_FRONT_DESK · GRAND_ROOM(3–17F) · GRAND_CLUB_LOUNGE(16F)
         ONDAL(2F) · GEUMRYONG(1F) · LE_PASSAGE(1F) · THE_PAVILION(lobby) · LUX_BAR(16F)
[비스타] VISTA_LOBBY · VISTA_ROOM · THE_BUFFET(1F) · MOEGI · PIZZA_HILL(별관) · MYONGWOLGWAN(별관)
[더글라스] DOUGLAS_LOBBY · DOUGLAS_ROOM · DOUGLAS_LOUNGE · DOUGLAS_LIBRARY · DOUGLAS_MEETING(2F)
[시설]   RIVERPARK · FOREST_PARK · SKYARD · FITNESS · POOL · WELLNESS_SAUNA · GOLF_CLUB · TENNEZ_PARK
[연회]   CONVENTION_1F(워커홀) · CONVENTION_4F(아트홀/파인/오크) · GRAND_B1(그랜드홀) · VISTA_B2(비스타홀)
         ASTON_HOUSE · ASTON_GARDEN · MYONGWOLGWAN_GARDEN
[기타]   VILLA · CASINO(파라다이스)
```

### 8.3 외부 → 워커힐 이동 (◎ 공식)

| From → To | 수단 | Ride | 배차 | 첫차 | 막차 | 요금 |
|---|---|---|---|---|---|---|
| `ICN_T1` → `HOTEL_GATE` | 6705번 K공항리무진 | **90분** ◎ | 20~40분 ◎ | 05:20 ◎ | 23:15 ◎ | 18,000 ◎ |
| `ICN_T2` → `HOTEL_GATE` | 6705번 | 90분 ◎ | 20~40분 ◎ | 05:00 ◎ | 22:55 ◎ | 18,000 ◎ |
| `HOTEL_GATE` → `ICN_T1/T2` | 6705번 | 90분 ◎ | 20~40분 ◎ | 04:05 ◎ | 18:50 ◎ | 18,000 ◎ |
| `GWANGNARU_STN` → `HOTEL_GATE` | 무료 셔틀 | **8분** ◎ | 15분(예외 10분) ◎ | 06:00 ◎ | 23:30 ◎ | 무료 |
| `GANGBYEON_STN` → `HOTEL_GATE` | 무료 셔틀 | **15분** ◎ | 15분(예외 10분) ◎ | 06:00 ◎ | 23:30 ◎ | 무료 |

**무료셔틀 10분 배차 구간** ◎ : 06:00–07:00 / 08:00–09:00 / 10:00–13:00 / 18:00–18:30 / 21:00–21:30 / 22:00–22:30
그 외 시간대는 15분 배차. 첫·막차는 **무료셔틀 승차장 출발 기준** ◎

```
W_shuttle(t) = 5분  (10분 배차 구간)
             = 7.5분 (15분 배차 구간)
T(GWANGNARU → GATE, 08:30) = 5 + 8  = 13분
T(GANGBYEON  → GATE, 14:00) = 7.5+15 = 22.5분
T(ICN_T1 → GATE, 09:00)     = 15 + 90 = 105분   (배차 30분 가정)
```

> **막차 절벽**: `HOTEL_GATE → ICN` 막차가 **18:50**이다 ◎. 19시 이후 공항행은 리무진 셔틀·택시로만 가능하므로, 저녁 일정 뒤 공항 이동을 넣는 타임라인은 `LAST_BUS_MISSED` 분기를 반드시 가져야 한다.

### 8.4 구내 이동 (그랜드 ↔ 더글라스는 ◎, 나머지 △)

**더글라스 하우스는 차량 진입 불가** ◎. 경로가 3개뿐이며 각각 제약이 다르다.

| 경로 | 수단 | 시간 | 운영 | 제약 |
|---|---|---|---|---|
| `GRAND_LOBBY` → `DOUGLAS_LOBBY` | 전기차 셔틀 (현관 직원에게 요청) ◎ | 6분 △ + 호출대기 5분 △ | 24시간 ◎ (리무진 셔틀) | 요청 기반 (on-demand) |
| `PARKING_TOWER_4F` → `DOUGLAS_LOBBY` | 계단 ◎ | 5분 △ | **06:00–22:00, 동절기 제외** ◎ | 짐 많으면 불가 |
| `GRAND_LOBBY` → `DOUGLAS_LOBBY` | 산책로 B·D 코스 ◎ | 15분 △ | 주간 권장 △ | 우천·야간 비권장 |
| `PARKING_TOWER_B1` → `GRAND_LOBBY` | 호텔 연결통로 ◎ | 4분 △ | 24시간 △ | 짐 많을 때 권장 경로 ◎ |

**구내 이동 매트릭스 (분, △ 추정)** — 대각선 위쪽만 표기, 역방향 동일 가정

| From \ To | GRAND_LOBBY | GRAND_ROOM | CLUB_LOUNGE 16F | VISTA_LOBBY | VISTA_ROOM | 별관(피자힐·명월관) | DOUGLAS | RIVERPARK | FOREST_PARK | CONVENTION |
|---|---|---|---|---|---|---|---|---|---|---|
| `GRAND_LOBBY` | — | 4 | 5 | 8 | 12 | 7 | 11* | 9 | 10 | 6 |
| `GRAND_ROOM` | 4 | — | 3 | 12 | 16 | 11 | 15* | 13 | 14 | 10 |
| `GRAND_CLUB_LOUNGE` | 5 | 3 | — | 13 | 17 | 12 | 16* | 14 | 15 | 11 |
| `VISTA_LOBBY` | 8 | 12 | 13 | — | 4 | 5 | 19* | 6 | 12 | 10 |
| `VISTA_ROOM` | 12 | 16 | 17 | 4 | — | 9 | 23* | 10 | 16 | 14 |
| `별관` | 7 | 11 | 12 | 5 | 9 | — | 18* | 8 | 13 | 9 |
| `DOUGLAS` | 11* | 15* | 16* | 19* | 23* | 18* | — | 20* | 14 | 17* |
| `RIVERPARK` | 9 | 13 | 14 | 6 | 10 | 8 | 20* | — | 11 | 12 |
| `FOREST_PARK` | 10 | 14 | 15 | 12 | 16 | 13 | 14 | 11 | — | 13 |
| `CONVENTION` | 6 | 10 | 11 | 10 | 14 | 9 | 17* | 12 | 13 | — |

`*` = 셔틀 호출 대기 5분 포함. 셔틀 미이용(도보) 시 `GRAND_LOBBY ↔ DOUGLAS` 15분.

**같은 건물 내 수직 이동** △: 엘리베이터 대기 1.5분 + 층당 0.2분. 피크(체크인 15–17시, 조식 07–09시) `×2`.

### 8.5 Transition Latency — 머신별

#### M2 StayMachine
| Transition | L (p50) | L (p90) | 출처 |
|---|---|---|---|
| `ARRIVED_ON_PROPERTY → AT_FRONT_DESK` | 3분 | 6분 | △ |
| `AT_FRONT_DESK → IN_CHECKIN_QUEUE` (피크) | 8분 | 25분 | △ |
| `IN_CHECKIN_QUEUE → REGISTRATION_SIGNED` | 5분 | 10분 | △ |
| `REGISTRATION_SIGNED → DEPOSIT_TAKEN → KEY_ISSUED` | 3분 | 7분 | △ |
| `KEY_ISSUED → IN_ROOM` | = T(로비→객실) | | 8.4 |
| `ONLINE_CHECKIN_DONE → DIGITAL_KEY_ACTIVATED` | **15:00 이후 객실 정비 완료 시점** | 주말·공휴일 대기 장기화 | ◎ |
| `KIOSK_CHECKIN → KEY_ISSUED` (더글라스 QR) | 2분 | 5분 | △ |
| `DUE_OUT → CHECKED_OUT_SETTLED` (프런트) | 6분 | 15분 | △ |
| `DUE_OUT → CHECKED_OUT_SETTLED` (모바일) | 2분 | 3분 | △ |
| `LATE_CHECKOUT_REQUESTED → APPROVED/DENIED` | 10분 | 60분 | △ |

**하드 타임스탬프** ◎
- 체크인 가능 시각 **15:00**, 체크아웃 **11:00** (전 프로퍼티 공통)
- 더글라스 모바일 체크인 사전등록 오픈: **투숙 전일 10:00** ◎
- 더글라스 QR 발급: **당일 15:00 이후 객실 정비 완료 순차** ◎
- 예약 변경·취소 마감: **체크인 전일 18:00** ◎ / 당일 예약은 변경·취소 불가 ◎

#### M7 OutletSessionMachine (식음)
| Transition | L (p50) | 비고 |
|---|---|---|
| `ARRIVED_AT_OUTLET → SEATED` (예약有) | 3분 △ | |
| `ARRIVED_AT_OUTLET → IN_QUEUE → SEATED` (워크인) | 20분 △ | 피크 40분 |
| `SEATED → ORDER_TAKEN` | 8분 △ | |
| `ORDER_TAKEN → DINING` (단품) | 15분 △ | |
| `ORDER_TAKEN → COURSE_IN_PROGRESS` (코스) | 12분 △ | |
| `BILL_REQUESTED → LEFT` | 7분 △ | 룸차지 4분 |
| `DISH_REFIRED` 추가 | +18분 △ | |

**Dwell — 업장별 체류 시간**
| 업장 / 상품 | D (p50) | 근거 |
|---|---|---|
| 온달 궁중음식 코스 (수라상·궁중상) | 120분 △ | 8코스 구성 |
| 온달 반상차림 | 60분 △ | |
| 금룡 코스 (화룡·도원경·만수무강) | 110분 △ | |
| 금룡 단품 | 70분 △ | |
| 명월관 구이 | 90분 △ | |
| 명월관 별채 맡김차림 | 150분 △ | |
| MOEGI 스시 오마카세 | **90분 이상** ◎ | "최소 1시간 30분 소요" |
| MOEGI 철판 코스 | **90분** ○ | 1부 12:00–13:30 슬롯 = 90분 |
| MOEGI 철판 디너 1부 | **150분** ○ | 18:00–20:30 |
| 더뷔페 조식 (주말 1부) | **100분** ○ | 06:30–08:10 |
| 더뷔페 중식 (주말) | **120분** ○ | 11:00–13:00 |
| 더뷔페 석식 (토·공휴일 1부) | **120분** ○ | 17:30–19:30 |
| 피자힐 | **120분** ◎ | "타임당 2시간 좌석 회전" |
| 더파빌리온 애프터눈티 | 90분 △ | |
| LUX BAR | 100분 △ | |
| 클럽라운지 해피아워 | **120분** ○ | 17:30–19:30 |
| 인룸 다이닝 (주문→배달) | 35분 △ | |

#### M5 TransportMachine
| Transition | L | 출처 |
|---|---|---|
| `VALET_RECEIVED → PARKED` | 5분 △ | |
| `CAR_RETRIEVAL_REQUESTED → CAR_RELEASED` | 12분 △ | 피크 25분 |
| `SHUTTLE_BOOKED → SHUTTLE_BOARDED` | = W_headway | 8.3 |
| 구내 셔틀 호출 → 탑승 | 5분 △ | on-demand |

#### M6 ServiceRequestMachine
| 요청 타입 | `RECEIVED → FULFILLED` | 출처 |
|---|---|---|
| 룸서비스 | 35분 △ | 운영 06:00–24:00 ◎ (더글라스) |
| 어메니티 | 12분 △ | |
| 하우스키핑 (메이크업룸) | 40분 △ | |
| 엔지니어링 | 25분 △ | |
| 턴다운 | 15분 △ | |
| 발렛 출차 | 12분 △ | |

#### M10 PackageEntitlementMachine
| 특전 | D | 출처 |
|---|---|---|
| 웰니스 사우나 1회 | 60분 △ | |
| 골프 VIP 타석 | **60분** ◎ | WPC 연 이용권 1일 1회 60분 |
| 골프 20회 이용권 1회 | **80분** ◎ | |
| 숏게임 콤플렉스 1회 | **60분** ◎ | |
| 테네즈 파크 | **120분** ◎ | 2시간 이용권, 월–금 |
| 향수 공방 원데이 클래스 (성수) | 120분 △ | + 왕복 이동 (성수 편도 30분 △) |
| 포레스트 파크 모닥불 | 60분 △ | 운영창 §8.6 |

### 8.6 Operating Window — 전이 가드

전이는 **목적지 상태의 운영 창 안에서 시작하고 끝나야** 한다. 시작만 검사하면 L.O.를 넘긴다.

| Venue | 운영 창 | L.O. | 출처 |
|---|---|---|---|
| 온달 | 12:00–15:00 / 18:00–21:00 | 주중 14:30·20:30 / 주말 14:00·20:00 | ◎ |
| 금룡 | 12:00–15:00 / 18:00–21:00 | — | ◎ |
| 명월관 | 12:00–15:00 / 17:30–21:00 | — | ◎ |
| MOEGI | 12:00–15:00 / 18:00–21:00 | 철판·스시 1부/2부 슬롯 고정 | ◎ |
| 피자힐 | 11:30–22:30 (7타임) | 21:00 | ◎ |
| 더파빌리온 | 09:00–21:00 | 20:00 | ◎ |
| └ 브런치 | 10:00–14:00 | | ◎ |
| └ 샌드위치·버거 | 10:00–19:30 | | ◎ |
| └ 피자 | 11:00–19:30 | | ◎ |
| └ 빙수 | 10:00–20:00 | | ◎ |
| └ 애프터눈티 | 11:00–20:00 | | ◎ |
| LUX BAR | 20:00–01:00 | — | ◎ |
| 클럽라운지 BAR | 20:00–01:00 | — | ◎ |
| 클럽라운지 해피아워 | 17:30–19:30 | 17시 이후 12세 이하 입장 제한 | ◎ |
| 더뷔페 | §4.3 슬롯표 | 슬롯 고정 | ◎ |
| 인룸 다이닝 | 06:00–24:00 (더글라스) | — | ◎ |
| 워커힐 골프클럽 | 06:00–23:00 | 반려동물 불가, 기상 제한 | ◎ |
| 포레스트 파크 (캠크닉) | 08/24–09/27 11:00–21:00 · 09/28–11/30 11:00–20:00 | 모닥불 17:00–20:30 · 16:00–19:30 | ◎ |
| 르 파사쥬 피자 To-go 픽업 | 11:00–19:30 | | ◎ |
| 무료 셔틀 | 06:00–23:30 | | ◎ |
| 주차타워 4F → 더글라스 계단 | 06:00–22:00 (동절기 제외) | | ◎ |
| 피트니스 | — | **17세 이상** | ◎ |

---

## 9. 24시간 정합성 — Timeline 검증

### 9.1 자료구조

```
Timeline := [ Segment ]
Segment  := { machine, state, location, t_in, t_out, payload }

불변식:
  t_out(s_n) ≤ t_in(s_{n+1})
  t_in(s_{n+1}) − t_out(s_n) ≥ T(loc(s_n) → loc(s_{n+1}), t_out(s_n))
  t_out(s_n) − t_in(s_n) = D(s_n)
```

### 9.2 불변식 6개

| # | 불변식 | 위반 시 |
|---|---|---|
| **I1 단조성** | 시계는 되감기지 않는다. `t_in(s_{n+1}) ≥ t_out(s_n)` | `TIMELINE_REWIND` |
| **I2 이동 가능성** | 두 세그먼트 사이 간격 ≥ 이동 시간. 순간이동 금지 | `TELEPORT` |
| **I3 운영 창** | `[t_in, t_out] ⊆ window(venue)` 이고 `t_in ≤ L.O.` | `OUTSIDE_WINDOW` |
| **I4 물리적 배타성** | 한 시점에 고객의 물리적 위치는 하나. `OutletSession`은 여러 개가 `OPEN`일 수 있으나 `SEATED/DINING`은 동시 1개 | `DOUBLE_BOOKED` |
| **I5 전제 상태** | `DINING`은 `SEATED` 이후에만. `KEY_ISSUED` 없이 `IN_ROOM` 불가 | `PRECONDITION_VIOLATED` |
| **I6 호텔 하루 경계** | 투숙일은 00:00–24:00이 아니라 **15:00 → 익일 11:00** (20시간). 체크인 전/체크아웃 후 구간은 `LUGGAGE_STORED`·`POST_STAY`로만 존재 | `DAY_BOUNDARY_VIOLATED` |

> **I6이 핵심이다.** "24시간 정합"을 자정 기준으로 잡으면 투숙객 하루가 두 날짜에 걸쳐 잘린다. `StayDay = [15:00, +1d 11:00]` 로 두고, 그 바깥의 구내 체류는 별도 상태로 명시해야 한다.

### 9.3 검증 알고리즘 — 실행 가능 구현

`timeline/walkerhill_timeline_validator.py` 에 구현되어 있다. 아래는 그 요약.

```
validate(timeline):
  for n in 0 .. len-2:
      a, b = timeline[n], timeline[n+1]

      if b.t_in < a.t_out:                      → I1  TIMELINE_REWIND
      need = T(a.location, b.location, a.t_out)
      if b.t_in - a.t_out < need:               → I2  TELEPORT (부족분 = need - gap)

  for s in timeline:
      w = window(s.location, date(s.t_in))
      if s.t_in < w.open or s.t_out > w.close:  → I3  OUTSIDE_WINDOW
      if s.t_in > w.last_order:                 → I3  PAST_LAST_ORDER
      if s.state in PHYSICAL and overlaps(s, other PHYSICAL):
                                                → I4  DOUBLE_BOOKED
      if not preconditions_met(s, timeline):    → I5  PRECONDITION_VIOLATED
      if not in_stay_day(s):                    → I6  DAY_BOUNDARY_VIOLATED
```

**T(a,b,t) 계산**
```
T(a, b, t):
    if a == b: return 0
    if external_leg(a,b):  return W_headway(mode, t) + T_ride(a,b)     # §8.3
    if involves(DOUGLAS):  return 5 + T_shuttle(a,b)                    # 호출 대기
    return T_matrix[a][b]                                               # §8.4
    # 피크(07–09, 15–17) 구내 수직이동 ×2
```

### 9.4 검증된 24시간 예시 — 그랜드 투숙객 1박

`StayDay = [D 15:00, D+1 11:00]`

| t_in | t_out | State | Location | Δ이동 | 검사 |
|---|---|---|---|---|---|
| 13:30 | 15:00 | `ICN_T1 출발` | ICN_T1 | — | 막차 23:15 이내 ◎ |
| 15:00 | 15:00 | `ARRIVED_ON_PROPERTY` | HOTEL_GATE | ride 90 + wait 15 = 105분 | I2 OK (13:15 출발 필요 → 13:30 탑승은 15:15 도착) |
| 15:15 | 15:18 | `AT_FRONT_DESK` | GRAND_FRONT_DESK | 3 | 15:00 이후 ◎ I6 OK |
| 15:18 | 15:34 | `IN_CHECKIN_QUEUE → KEY_ISSUED` | GRAND_FRONT_DESK | 0 | 피크 대기 8+5+3 |
| 15:34 | 15:42 | `IN_ROOM` | GRAND_ROOM | 4×2(피크) = 8 | I2 OK |
| 15:42 | 17:20 | `IN_ROOM` (휴식) | GRAND_ROOM | — | |
| 17:20 | 17:23 | 이동 | → CLUB_LOUNGE 16F | 3 | |
| 17:30 | 19:30 | `HAPPY_HOUR_ACTIVE` | GRAND_CLUB_LOUNGE | — | 창 17:30–19:30 ◎ 정확히 일치 |
| 19:30 | 19:42 | 이동 | → ONDAL 2F | 12 | |
| 19:42 | — | ❌ **위반** | ONDAL | — | **I3: 온달 디너 L.O. 20:30, 코스 D=120분 → 21:42 종료 > 마감 21:00** |

**수정안** — 해피아워를 1시간만 쓰고 온달을 18:40에 시작:

| t_in | t_out | State | Location | 검사 |
|---|---|---|---|---|
| 17:30 | 18:25 | `HAPPY_HOUR_ACTIVE` | CLUB_LOUNGE | 창 내 ◎ |
| 18:25 | 18:37 | 이동 | → ONDAL | T=12 |
| 18:40 | 20:40 | `COURSE_IN_PROGRESS` (수라상차림 195,000) | ONDAL | 시작 ≤ L.O. 20:30 ◎, 종료 20:40 ≤ 21:00 ◎ |
| 20:40 | 20:52 | 이동 | → LUX_BAR 16F | T=12 |
| 20:52 | 22:32 | `TAB_OPEN → DINING` | LUX_BAR | 창 20:00–01:00 ◎ |
| 22:32 | 22:36 | 이동 | → GRAND_ROOM | T=4 |
| 22:36 | D+1 07:30 | `IN_ROOM` / `DND_ON` | GRAND_ROOM | |
| 07:30 | 08:30 | 이동 + 슬롯 대기 | → THE_BUFFET (비스타 1F) | T=12, 피크 ×2 = 24 |
| 08:00 | 09:40 | `TIME_LIMIT_ACTIVE` 조식 1부 | THE_BUFFET | 창 06:30–08:10 ❌ → **2부 08:30–10:00 선택** |
| 08:30 | 10:00 | 조식 2부 | THE_BUFFET | ◎ |
| 10:00 | 10:12 | 이동 | → GRAND_ROOM | T=12 |
| 10:12 | 10:50 | 짐 정리 | GRAND_ROOM | |
| 10:50 | 10:54 | 이동 | → FRONT_DESK | T=4 |
| 10:54 | 11:00 | `CHECKED_OUT_SETTLED` | GRAND_FRONT_DESK | 마감 11:00 ◎ I6 경계 |

→ 전 구간 I1–I6 통과. **총 이동 시간 합 = 71분 / 20시간 StayDay의 5.9%** (검증기 실측)

### 9.5 정합성이 깨지는 대표 패턴

| 패턴 | 원인 | 방어 |
|---|---|---|
| **막차 절벽** | 공항행 6705 막차 18:50 ◎. 저녁 식사 후 공항 이동 불가 | `LAST_BUS_MISSED` → 리무진/택시 분기 강제 |
| **L.O. 오버런** | 시작 시각만 검사. 코스 120분이 마감을 넘김 | I3에 `t_out ≤ close` 포함 |
| **더글라스 셔틀 누락** | 차량 진입 불가인데 직행으로 계산 ◎ | `involves(DOUGLAS)` → 호출 대기 5분 강제 |
| **계단 야간 폐쇄** | 주차타워 4F 계단 06:00–22:00, 동절기 제외 ◎ | 시각·계절 가드 |
| **슬롯 불일치** | 뷔페·철판·오마카세는 자유 착석이 아니라 1부/2부 고정 ◎ | 슬롯 enum으로만 진입 허용 |
| **QR 대기** | 더글라스 QR은 15:00 이후 **순차** 발급, 주말 지연 ◎ | `ONLINE_CHECKIN_DONE` → `DIGITAL_KEY_ACTIVATED` 는 확정 latency가 아님 |
| **자정 절단** | StayDay를 00:00 기준으로 잡음 | I6 |
| **동시 착석** | 두 업장에 동시 `SEATED` | I4 |

### 9.6 검증기 실행 결과

```
$ cd timeline && python3 walkerhill_timeline_scenarios.py

=== §9.4 초안 (온달 L.O. 초과 예상) ===
FAIL — 위반 1건
  총 이동 시간: 19분 (투숙 기간 20시간 중 1.6%)
  [I3 OUTSIDE_WINDOW] 09-21 19:45  ONDAL: 영업시간 외 이용 (운영 18:00~21:00 / 요청 19:45~21:45) · 운영 슬롯 2개 중 맞는 구간 없음

=== §9.4 수정안 ===
PASS — 불변식 I1~I6 모두 충족
  총 이동 시간: 71분 (투숙 기간 20시간 중 5.9%)

=== §9.5 뷔페 슬롯 불일치 ===
FAIL — 위반 1건
  총 이동 시간: 32분 (투숙 기간 20시간 중 2.7%)
  [I3 OUTSIDE_WINDOW] 09-22 08:00  THE_BUFFET: 영업시간 외 이용 (운영 08:30~10:00 / 요청 08:00~09:40) · 운영 슬롯 6개 중 맞는 구간 없음

=== §9.5 더글라스 셔틀 누락 ===
FAIL — 위반 1건
  총 이동 시간: 36분 (투숙 기간 20시간 중 3.0%)
  [I2 TELEPORT] 09-21 15:40  GRAND_FRONT_DESK→DOUGLAS_LOUNGE 필요 36분, 확보 6분 (부족 30분)

=== §9.5 동시 착석 (비투숙 고객) ===
FAIL — 위반 2건
  총 이동 시간: 0분 (투숙 기간 20시간 중 0.0%)
  [I1 TIMELINE_REWIND] 09-21 13:30  TIME_LIMIT_ACTIVE 이 DINING 종료(14:00) 전에 시작
  [I4 DOUBLE_BOOKED] 09-21 13:30  DINING@ONDAL 과 TIME_LIMIT_ACTIVE@THE_BUFFET 구간이 겹침 — 동시에 두 장소를 점유할 수 없음

=== §9.5 막차 절벽 ===
  저녁 종료 20:40 / 공항행 막차 18:50 (◎) → LAST_BUS_MISSED → 리무진·택시 분기 필요

=== 이동 시간 샘플 (§8.3 / §8.4) ===
  08:30   GWANGNARU_STN → HOTEL_GATE        13.0분
  14:00   GANGBYEON_STN → HOTEL_GATE        22.5분
  09:00          ICN_T1 → HOTEL_GATE       105.0분
  16:00     GRAND_LOBBY → GRAND_ROOM         8.0분 (피크 ×2)
  22:00     GRAND_LOBBY → GRAND_ROOM         4.0분
  19:00     GRAND_LOBBY → DOUGLAS_LOBBY     16.0분
```

6개 불변식이 전부 실제로 발화하는 것을 확인했다.

| 시나리오 | 잡힌 불변식 | 의미 |
|---|---|---|
| §9.4 초안 | I3 OUTSIDE_WINDOW | 온달 코스 120분이 마감 21:00을 넘김 — **시작 시각만 검사했으면 통과했을 버그** |
| §9.4 수정안 | — (PASS) | 20시간 StayDay 중 이동 71분(5.9%) |
| 뷔페 슬롯 | I3 OUTSIDE_WINDOW | 08:00 착석은 6개 슬롯 어디에도 안 맞음. 자유 착석이 아님 |
| 더글라스 셔틀 | I2 TELEPORT | 차량 진입 불가 → 셔틀 호출 5분 포함 36분 필요한데 6분만 확보 |
| 동시 착석 | I1 + I4 | 온달 식사 중 뷔페 입장. 되감기와 이중 점유가 동시에 잡힘 |
| 막차 절벽 | (외부 검사) | 저녁 20:40 종료 > 공항행 막차 18:50 → LAST_BUS_MISSED |

**구현 메모** — 구내 이동은 매트릭스 직접 조회가 아니라 **그래프 최단경로(Dijkstra)** 로 계산한다.
워커힐은 동·층이 나뉘어 있어 임의의 두 지점이 직결되지 않는다. 미등록 쌍을 에러로 처리하면
타임라인 자체가 검증 불가가 되므로, 등록된 간선으로 실제 경유 동선(대개 로비 경유)을 구한다.
예: `GRAND_FRONT_DESK → DOUGLAS_LOUNGE` = 프런트→로비 1 + 로비→더글라스로비 11 + 로비→라운지 1 + 셔틀 호출 5 = 18분,
여기에 체크인 피크(15–17시) ×2 가 걸려 36분.

---

## 10. 미확보 데이터 (현장·내부 시스템 확인 필요)

| 항목 | 사유 |
|---|---|
| 더 뷔페 스테이션별 품목 | 웹 미공개, 일자별 변동 |
| 르 파사쥬 가격표 | 메뉴 파일 미제공 |
| 클럽 라운지 F&B 구성 | 투숙객 전용, 미공개 |
| 더글라스 라운지 / 라이브러리 메뉴 | 미공개 |
| 리버파크 풀바·푸드트럭 메뉴 | 계절 운영, 미공개 |
| 애스톤하우스 / 인룸다이닝 / 뱅큇 메뉴 | 사전 협의 기반 |
| 명월관 별채 맡김차림 세부 구성 | "당일 현장 확인" 방식 |
| 모에기 마코토 코스 가격 | PDF 추출 누락 |
| 빌라 객실 상세 (면적·수용·요금) | ✅ 해결 — 호텔이 비공개. 장기 임대형이라 객실 스펙 자체가 게시되지 않음 (§5.4) |
| 애스톤 하우스 객실 상세 | ✅ 해결 — 객실 카테고리가 아니라 연회 공간. VIP 스위트는 연회 계약 부속 (§5.5) |
| 바비 스위트 표준 요금 | ✅ 해결 — 표준요금 필드 자체가 없음. 정적 스크랩 시 숨은 블록을 잘못 읽었던 것 |
| 그랜드 / 비스타 프레지덴셜 스위트 요금 | 미표기 (문의 전용) |
| 빌라 단기 예약 가능 조건 | '어려울 수 있음' — 실제 판정 룰은 내부 정책 |
| 애스톤 하우스 VIP 스위트 객실 스펙 | 미공개 |
| 연회장 대관료 / F&B 최저 보증 금액 | 전 공간 '별도 문의' |
| **구내 이동 시간 실측치** | 워커힐 미공개. §8.4 매트릭스는 전부 △ 추정치 — 현장 실측 필요 |
| 업장별 평균 체류 시간(실측) | §8.5 D값 중 △ 표시분. POS 테이블 회전 데이터로 교체 필요 |
| 프런트 체크인 대기 시간 분포 | 피크/오프피크 실측 필요 |
| 구내 전기차 셔틀 배차·호출 대기 | 운영 방식만 공개, 시간 미공개 |
| 김포공항 ↔ 워커힐 소요 시간 | 탭 존재하나 미수집 |
| 다락휴 여수엑스포점 객실 타입 | 별도 사이트, 미조사 |
| 객실 타입별 총 재고(실 수) | 일부만 공개 (그랜드 위주) |
| 스파·피트니스 프로그램 세부 | 미조사 |

---

## 11. 다음 단계

1. **§8.4 구내 이동 시간 실측** — 현재 전부 △ 추정치. 검증기 결과의 신뢰도가 여기에 달려 있다
2. 구현 대상 Machine 선정 (PMS / CRM / 운영 대시보드 / AI 컨시어지 중)
3. 선정된 Machine의 transition table + guard 조건 정의
4. 이벤트(event) 정의 — 무엇이 전이를 일으키는가
5. 상태 영속화 스키마 설계
6. §10 미확보 데이터 보완

### 검증기 사용

```bash
cd timeline && python3 walkerhill_timeline_scenarios.py
```

새 타임라인 검증:
```python
from walkerhill_timeline_validator import TimelineSegment, validate_walkerhill_timeline

segments = [TimelineSegment("SEATED", "ONDAL", t_in, t_out, venue="ONDAL"), ...]
print(validate_walkerhill_timeline(segments).render())
```
