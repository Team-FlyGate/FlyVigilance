"""Terminal-native block lettering, shaded extrusion and 24-bit color."""
VERSION = '1.0.0'
FONT = {
 'F':['11111','11000','11000','11110','11000','11000','11000'],
 'L':['11000','11000','11000','11000','11000','11000','11111'],
 'Y':['11011','11011','11011','01110','00100','00100','00100'],
 'G':['01111','11000','11000','11011','11001','11001','01111'],
 'A':['01110','11011','11011','11111','11011','11011','11011'],
 'T':['11111','00100','00100','00100','00100','00100','00100'],
 'E':['11111','11000','11000','11110','11000','11000','11111'],
}
WING = ['1100000000011','1110000000111','0111000001110','0011100011100','0001111111000','0000011100000','0000010100000']


def render(width=100, color=True):
    scale = 2 if width >= 80 else 1
    rows = [' '.join(''.join('█'*scale if p=='1' else ' '*scale for p in FONT[c][y]) for c in 'FLYGATE') for y in range(7)]
    if width >= 100:
        rows = [''.join('█' if p=='1' else ' ' for p in WING[y]) + '     ' + row for y,row in enumerate(rows)]
    if width < 44:
        return '\n  FlyGate CLI v'+VERSION+'\n'
    w = len(rows[0])+1
    pixels = [list(row.ljust(w)) for row in rows] + [list(' '*w)]
    # Offset extrusion behind opaque front-face block characters.
    for y,row in enumerate(rows):
        for x,ch in enumerate(row):
            if ch=='█' and pixels[y+1][x+1]==' ': pixels[y+1][x+1]='░'
    out=['']
    for y,row in enumerate(pixels):
        t=y/(len(pixels)-1)
        rgb=tuple(round(a+(b-a)*t) for a,b in zip((55,230,255),(166,228,48)))
        shadow=tuple(round(v*.48) for v in rgb)
        line=' '
        for ch in row:
            if color and ch!=' ':
                r,g,b=shadow if ch=='░' else rgb
                line+=f'\033[38;2;{r};{g};{b}m'+ch
            else:line+=ch
        out.append(line.rstrip()+ ('\033[0m' if color else ''))
    out+=['', ' '+('─'*min(12,width//8))+' FlyGate CLI v'+VERSION+' '+('─'*min(22,max(0,width-42))), '']
    return '\n'.join(out)


def dashboard(root, model, nvidia=False, jev=False, width=100, color=True, session=''):
    """Compact text dashboard with terminal-cell-aware Korean wrapping."""
    import unicodedata
    cyan='\033[38;2;55;230;255m' if color else ''
    lime='\033[38;2;166;228;48m' if color else ''
    reset='\033[0m' if color else ''
    skills={p.parent.name for base in (root/'skills', root/'agent/skills') for p in base.glob('*/SKILL.md')}
    maxw=max(8,min(width-2,116))
    inner=maxw-4
    def cells(text):
        return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in text)
    def wrap(text, limit=inner):
        line=''
        for char in text:
            if cells(line+char)>limit:
                yield line
                line=''
            line+=char
        yield line
    art=[
        '           ▄██▄  ▄██▄           ',
        '          ████████████          ',
        '           ▀████████▀           ',
        '         ▄▄█▌██████▐█▄▄         ',
        '     ███████▌██████▐███████     ',
        ' ██████████▌▄██████▄▐██████████ ',
        '███████████▌████████▐███████████',
        '  ▀▀▀▀▀▀    ████████    ▀▀▀▀▀▀  ',
        '             ▀████▀             ',
    ]
    # Pad the whole emblem, rather than centering each silhouette row separately.
    left=[('', '')]+[(line.ljust(max(map(len, art))), lime) for line in art]+[
        ('', ''),
        ('FlyDiscovery + FlyVigilance', lime),
        (model, lime),
        (f'NVIDIA {"✓" if nvidia else "미설정"} · Jev {"✓" if jev else "선택"}', lime),
    ]
    right=[
        ('SLASH COMMANDS · 7 tools', cyan),
        ('/discover     저장 근거 조회 / 새 도킹 실행', ''),
        ('/signals      이상사례 신호 통계', ''),
        ('/triage       사례 분류', ''),
        ('/grade        근거 등급 평가', ''),
        ('/critic       근거·수치·해석 검토', ''),
        ('/kr-causality 한국형 인과성 평가', ''),
        ('/watch        모니터링·검토 대기열', ''),
        ('', ''),
        ('CHAT COMMANDS', cyan),
        ('/help   명령과 예제 보기', ''),
        ('/login  NVIDIA · Jev 키 설정', ''),
        ('/last   마지막 분석 결과 전체 보기', ''),
        ('/clear  대화와 마지막 결과 지우기', ''),
        ('/exit   종료', ''),
    ]
    if maxw >= 76:
        leftw=min(40,(maxw-7)//2)
        rightw=maxw-7-leftw
        def expand(rows, limit):
            return [(part, shade) for text, shade in rows for part in wrap(text, limit)]
        lrows, rrows=expand(left,leftw), expand(right,rightw)
        def padded(row, limit, center=False):
            text, shade=row
            gap=limit-cells(text)
            before=gap//2 if center else 0
            return shade+' '*before+text+' '*(gap-before)+reset
        out=[' '+cyan+'╭'+'─'*(leftw+2)+'┬'+'─'*(rightw+2)+'╮'+reset]
        for i in range(max(len(lrows),len(rrows))):
            l=lrows[i] if i<len(lrows) else ('','')
            r=rrows[i] if i<len(rrows) else ('','')
            out.append(' '+cyan+'│'+reset+' '+padded(l,leftw,True)+' '+cyan+'│'+reset+' '+padded(r,rightw)+' '+cyan+'│'+reset)
        out.append(' '+cyan+'╰'+'─'*(leftw+2)+'┴'+'─'*(rightw+2)+'╯'+reset)
        return '\n'.join(out)
    rows=left[len(art)+1:]+[('','')]+right
    out=[' '+cyan+'╭'+'─'*(maxw-2)+'╮'+reset]
    for text, shade in rows:
        for line in wrap(text):
            out.append(' '+cyan+'│'+reset+' '+shade+line+' '*(inner-cells(line))+reset+' '+cyan+'│'+reset)
    out.append(' '+cyan+'╰'+'─'*(maxw-2)+'╯'+reset)
    return '\n'.join(out)



def welcome(color=True):
    c='\033[38;2;55;230;255m' if color else ''
    d='\033[38;2;160;175;197m' if color else ''
    r='\033[0m' if color else ''
    lines=['', '  FlyGate와 무엇을 살펴볼까요?', d+'  예: “PARP1 후보 근거를 보여줘” 또는 “이 결과를 설명해 줘”'+r, '']
    return '\n'.join(lines)+'\n'


def input_header(width=100,color=True):
    c='\033[38;2;55;230;255m' if color else ''
    d='\033[38;2;160;175;197m' if color else ''
    r='\033[0m' if color else ''
    line='─'*max(10,min(width-4,112))
    return '\n  '+c+line+r+'\n  '+c+'메시지 입력'+r+d+'  ·  Enter 전송  ·  Ctrl+C 입력 취소  ·  Ctrl+D 종료'+r
