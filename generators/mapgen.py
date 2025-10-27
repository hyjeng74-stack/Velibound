import random

W, H = 24, 18

def _empty_map():
    m = [["#" for _ in range(W)] for _ in range(H)]
    for y in range(1, H-1):
        for x in range(1, W-1):
            m[y][x] = "."
    return m

def _rect(m, x0,y0,x1,y1, ch="."):
    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            m[y][x] = ch

def _place(m, x, y, ch): m[y][x] = ch

def gen_room_graph(seed=None):
    """
    4개 룸 (2x2) + 복도. 한 경로는 잠긴 문(D)로 막고, 다른 방에 열쇠(K) 배치. 
    중앙에 아레나(A/T), 좌하단 시작(@), 우상단 골(G), 좌상단 상점(S).
    """
    if seed is not None: random.seed(seed)
    m = _empty_map()

    #룸 영역
    rooms = {
        "SW": (2, 8, 10, 15),
        "SE": (13, 8, 21, 15),
        "NW": (2, 2, 10, 7),
        "NE": (13, 2, 21, 7),
        "CTR": (9, 7, 14, 10),
    }
    for (x0,y0,x1,y1) in rooms.values():
        _rect(m, x0, y0, x1, y1, '.')
    
    #중앙 아레나 도어(A) 와 트리거(T)
    for x in range(rooms["CTR"][0], rooms["CTR"][2]+1):
        _place(m, x, rooms["CTR"][1], 'A')
        _place(m, x, rooms["CTR"][3], 'A')
    cx = (rooms["CTR"][0]+rooms["CTR"][2])//2
    cy = (rooms["CTR"][0]+rooms["CTR"][3])//2
    _place(m, cx, cy, 'T')

    #통로(바닥)
    for x in range(rooms["SW"][2], rooms["SE"][0]+1):
        _place(m, x, rooms["SW"][1], '.')
    for y in range(rooms["NW"][3], rooms["SW"][1]+1):
        _place(m, rooms["NW"][2], y, '.')
    
    #문(D) 하나 설치 (NE 가는 길)
    _place(m, rooms["NW"][2], rooms["NW"][1]+1, 'D')

    #기호 배치
    _place(m, rooms["SW"][0]+1, rooms["SW"][3]-1, '@')  #시작
    _place(m, rooms["NE"][2]-1, rooms["NE"][1]+1, 'G')  #골
    _place(m, rooms["NW"][0]+2, rooms["NW"][1]+2, 'K')  #키
    _place(m, rooms["NW"][0]+3, rooms["NW"][1]+3, 'S')  #상점
    #적/코인/포션/샘플
    for _ in range(3): _place(m, random.randint(rooms["SE"][0]+1, rooms["SE"][2]-1), random.randint(rooms["SE"][1]+1, rooms["SE"][3]-1), 'E')
    for _ in range(2): _place(m, random.randint(rooms["NW"][0]+1, rooms["NW"][2]-1), random.randint(rooms["NW"][1]+1, rooms["NW"][3]-1), 'e')
    for _ in range(3): _place(m, random.randint(2, W-3), random.randict(2, H-3), 'C')
    for _ in range(2): _place(m, random.randint(2, W-3), random.randint(2, H-3), 'P')

    return ["".join(row) for row in m]

def generate_level_set(n=3, seed=None):
    out = []
    for i in range(n):
        mp = gen_room_graph(seed=(None if seed is None else seed+1))
        out.append({"map":mp, "elite_rate":0.2 + 0.05*i})
    return out