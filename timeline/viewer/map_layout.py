# 바탕 그림(1564 × 1006 · 10/17 v3 · 초록 · 배경 투명)의 장소 · 길 · 이름표 좌표 (그림 좌표). python3 map_layout.py > coords.json 으로 내보내 map.js 의 LOC · NODE · EDGES · ANCHOR · BUILDING_LABELS 에 넣는다.
IMG_W, IMG_H = 1564, 1006
LOC = {
    "HOTEL_GATE": (362, 840), "VALET_DESK": (745, 690),
    "PARKING_TOWER_B1": (715, 500), "PARKING_TOWER_4F": (737, 478),
    "GRAND_LOBBY": (760, 668), "GRAND_FRONT_DESK": (782, 674), "GRAND_ROOM": (760, 590), "GRAND_CLUB_LOUNGE": (766, 560),
    "GRAND_LIBRARY": (726, 658), "THE_PAVILION": (712, 650), "GEUMRYONG": (802, 650), "LE_PASSAGE": (742, 692),
    "LUX_BAR": (812, 624), "GRAND_POOL": (660, 630), "FITNESS": (990, 664), "WELLNESS_SAUNA": (1012, 680), "ONDAL": (786, 640),
    "THEATRE_OF_LIGHT": (772, 726), "THEATRE_ART_SHOP": (742, 742), "CU_THEATRE": (806, 746), "CONVENTION": (700, 672),
    "RIVERPARK": (1086, 764),
    "VISTA_LOBBY": (666, 776), "VISTA_ROOM": (640, 690), "VISTA_POOL": (590, 760), "VISTA_FITNESS": (606, 782), "SKYARD": (652, 716),
    "THE_BUFFET": (692, 790), "MOEGI": (712, 770),
    "ANNEX": (700, 618), "PIZZA_HILL": (352, 402), "MYONGWOLGWAN": (222, 626),
    "DOUGLAS_LOBBY": (802, 422), "DOUGLAS_ROOM": (842, 400), "DOUGLAS_LOUNGE": (770, 432), "DOUGLAS_LIBRARY": (872, 436),
    "FOREST_PARK": (1120, 382), "GOLF_CLUB": (1410, 562), "TENNEZ_PARK": (990, 722),
}
for k in ("GWANGNARU_STN", "GANGBYEON_STN", "ICN_T1", "ICN_T2"): LOC[k] = LOC["HOTEL_GATE"]
ROADS = {
    "s": [(100, 295), (160, 303), (230, 325), (300, 348), (370, 372), (430, 392), (480, 402), (520, 405)],
    "d": [(520, 405), (560, 335), (620, 320), (680, 325), (740, 345), (800, 375), (850, 405), (900, 432), (960, 452), (1020, 472), (1080, 490), (1140, 520), (1204, 552)],
    "p": [(520, 405), (526, 445), (526, 488), (506, 524), (474, 546), (440, 556), (402, 574), (386, 620), (400, 665), (432, 700), (472, 716)],
    "k": [(160, 303), (135, 345), (120, 400), (118, 470), (128, 520), (145, 560), (178, 594), (225, 618), (275, 652), (330, 688), (385, 710), (440, 716), (472, 716), (500, 720), (530, 725), (560, 730)],
    "e": [(365, 835), (427, 783), (467, 743), (507, 724)],
    "n": [(474, 546), (540, 545), (600, 540), (660, 530), (720, 522), (780, 515), (836, 512), (900, 508), (964, 512), (1040, 545), (1110, 580), (1160, 580), (1204, 552)],
    "f": [(600, 545), (588, 600), (600, 640), (635, 665), (690, 680), (730, 690), (760, 712), (800, 722), (850, 720), (900, 712), (940, 700)],
    "w": [(836, 512), (870, 560), (900, 600), (935, 635), (980, 655), (1015, 660), (1055, 690), (1100, 720), (1140, 758), (1180, 790), (1220, 800), (1270, 790)],
    "g": [(1204, 552), (1196, 576), (1204, 640), (1212, 688), (1228, 720), (1260, 744), (1324, 760), (1388, 776)],
    "q": [(720, 522), (712, 486), (730, 445), (760, 410), (800, 375)],   # 그랜드 북쪽 → 주차타워 옆 → 더글라스
    "h": [(1204, 552), (1260, 592), (1324, 640), (1380, 696), (1404, 752), (1396, 768), (1388, 776)],
}
JOINS = [(("s", 7), ("d", 0)), (("s", 7), ("p", 0)), (("s", 1), ("k", 0)), (("p", 10), ("k", 12)), (("e", 3), ("k", 14)), (("p", 4), ("n", 0)),
         (("n", 2), ("f", 0)), (("n", 6), ("w", 0)), (("n", 12), ("d", 12)), (("n", 12), ("g", 0)), (("n", 12), ("h", 0)), (("g", 7), ("h", 6)),
         (("f", 10), ("w", 5)), (("w", 11), ("g", 6)), (("q", 0), ("n", 4)), (("q", 4), ("d", 5))]
ANCHOR = {
    "HOTEL_GATE": "e0", "VALET_DESK": "f5", "PARKING_TOWER_B1": "q2", "PARKING_TOWER_4F": "q2",
    **{k: "f5" for k in ("GRAND_LOBBY", "GRAND_FRONT_DESK", "GRAND_ROOM", "GRAND_CLUB_LOUNGE", "GRAND_LIBRARY", "THE_PAVILION", "GEUMRYONG", "LE_PASSAGE", "LUX_BAR", "ONDAL", "ANNEX")},
    "GRAND_POOL": "f2", "FITNESS": "w4", "WELLNESS_SAUNA": "w4",
    "THEATRE_OF_LIGHT": "f7", "THEATRE_ART_SHOP": "f6", "CU_THEATRE": "f7", "CONVENTION": "f4",
    "RIVERPARK": "w8", "TENNEZ_PARK": "w6",
    "VISTA_LOBBY": "k15", "VISTA_ROOM": "k15", "VISTA_POOL": "k14", "VISTA_FITNESS": "k14", "SKYARD": "k15", "THE_BUFFET": "k15", "MOEGI": "f6",
    "PIZZA_HILL": "p2", "MYONGWOLGWAN": "k8",
    "DOUGLAS_LOBBY": "d6", "DOUGLAS_ROOM": "d6", "DOUGLAS_LOUNGE": "d5", "DOUGLAS_LIBRARY": "d7",
    "FOREST_PARK": "d10", "GOLF_CLUB": "h2", "GWANGNARU_STN": "e0", "GANGBYEON_STN": "e0", "ICN_T1": "e0", "ICN_T2": "e0",
}
LABELS = [
    ("피자힐", 352, 356), ("명월관", 222, 586), ("주차타워", 725, 452), ("더글라스 하우스", 822, 372), ("포레스트 파크", 1120, 330),
    ("힐링 포레스트", 810, 108), ("더글라스 가든", 672, 318), ("그랜드 워커힐", 766, 528), ("빛의 시어터 · 컨벤션", 776, 784), ("비스타 워커힐", 600, 824),
    ("테네즈 파크", 990, 688), ("리버파크", 1086, 806), ("골프클럽", 1410, 520), ("애스톤 하우스", 1472, 700), ("South Gate", 110, 280), ("East Gate", 322, 866),
]
def export():
    NODE = {}; EDGES = []
    for k, pts in ROADS.items():
        for i, p in enumerate(pts): NODE[f"{k}{i}"] = p
        EDGES += [(f"{k}{i}", f"{k}{i + 1}") for i in range(len(pts) - 1)]
    for (a, i), (b, j) in JOINS: EDGES.append((f"{a}{i}", f"{b}{j}"))
    return NODE, EDGES
if __name__ == "__main__":
    import json
    NODE, EDGES = export()
    bad = [v for v in ANCHOR.values() if v not in NODE] + [n for e in EDGES for n in e if n not in NODE]
    assert not bad, bad
    print(json.dumps({"LOC": LOC, "NODE": NODE, "EDGES": EDGES, "ANCHOR": ANCHOR, "LABELS": LABELS}, ensure_ascii=False))
