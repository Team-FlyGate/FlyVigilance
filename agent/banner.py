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
    """Two-column terminal dashboard, sourced from the actual repository skills."""
    import textwrap
    cyan='\033[38;2;55;230;255m' if color else ''
    lime='\033[38;2;166;228;48m' if color else ''
    reset='\033[0m' if color else ''
    skills=sorted({p.parent.name for base in (root/'skills', root/'agent/skills') for p in base.glob('*/SKILL.md')})
    tools=['discover    saved evidence / live docking','signals     disproportionality statistics','triage      case routing','grade       labels / literature / PV class','critic      evidence / numbers / interpretation','kr-causality Korean report assessment','watch       monitoring / review queue']
    art=[
        '                              ',
        '   ▄▄▄                  ▄▄▄   ',
        '   █████▄            ▄█████   ',
        '    ▀██████▄      ▄██████▀    ',
        '       ▀█████    █████▀       ',
        '          ▀██    ██▀          ',
        '           ██    ██           ',
        '           ██    ██           ',
        '           ██    ██           ',
        '           ▀▀    ▀▀           ',
        '       DISCOVER  /  REVIEW    ',
        '                              ',
    ]
    right=['AVAILABLE TOOLS',*tools,'','PROJECT SKILLS',*skills,'',f'7 tools / {len(skills)} skills', '/help commands /login credentials']
    maxw=min(width-2,116)
    if maxw < 76:
        out=[f' {cyan}┌'+ '─'*max(1,maxw-2)+'┐'+reset]
        lines=['FlyGate / NVIDIA Nemotron',f'NVIDIA: {"configured" if nvidia else "not connected"}',f'Jev: {"configured" if jev else "optional"}','',*right]
        for line in lines:
            for part in textwrap.wrap(line,max(10,maxw-4)) or ['']:
                out.append(' '+cyan+'│'+reset+' '+part.ljust(maxw-4)+' '+cyan+'│'+reset)
        out.append(' '+cyan+'└'+'─'*(maxw-2)+'┘'+reset)
        return '\n'.join(out)
    leftw=40;rightw=maxw-leftw-7
    left=art+['','FlyDiscovery + FlyVigilance','',*textwrap.wrap(model,leftw),f'NVIDIA: {"configured" if nvidia else "not connected"}',f'Jev: {"configured" if jev else "optional / skip"}','',*textwrap.wrap(str(root),leftw),f'Session: {session}']
    rlines=[]
    for line in right:rlines.extend(textwrap.wrap(line,rightw) or [''])
    out=[' '+cyan+'╭'+'─'*(maxw-2)+'╮'+reset]
    for i in range(max(len(left),len(rlines))):
        l=left[i] if i<len(left) else '';r=rlines[i] if i<len(rlines) else ''
        out.append(' '+cyan+'│'+reset+' '+lime+l.center(leftw)+reset+' '+cyan+'│'+reset+' '+r.ljust(rightw)+' '+cyan+'│'+reset)
    out.append(' '+cyan+'╰'+'─'*(maxw-2)+'╯'+reset)
    return '\n'.join(out)
