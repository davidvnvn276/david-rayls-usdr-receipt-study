"""Draw the article's editable SVG figures from the verified result files."""
from __future__ import annotations

import argparse
import base64
from decimal import Decimal
from html import escape
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
RESULTS=json.loads((ROOT/"expected/review-summary.json").read_text(encoding="utf-8"))
RPC=json.loads((ROOT/"expected/rpc-summary.json").read_text(encoding="utf-8"))
FOLLOWUP=json.loads((ROOT/"expected/followup-summary.json").read_text(encoding="utf-8"))
HERO=RESULTS["hero"]
COUNT=RESULTS["counts"]
ALL=RESULTS["aggregate"]
EXAMPLES={k["case_id"]:k for k in RESULTS["special_wallet_examples"]}
LOGO=base64.b64encode((ROOT/"assets/rayls-mark-original.png").read_bytes()).decode("ascii")
INK="#121219"
PAPER="#f1f2f6"
WHITE="#fcfcff"
GRID="#d6d7e4"
LAV="#bda5ff"
LITE="#eae1ff"
VIOLET="#5132c9"
LIME="#e5ff30"
DIM="#4f505e"
FINE="#b9baca"
SANS="DejaVu Sans"
MONO="DejaVu Sans Mono"


def usdr(n, places=6, plus=False):
    sign="+" if n>0 and plus else ""
    return sign+f"{Decimal(n)/10**18:.{places}f}".replace("-", "−")


def narrow(family,size,s,bold,spacing):
    """Measure layout when Pillow and the reference fonts are available."""
    try:
        from PIL import ImageFont
        p=Path("/usr/share/fonts/truetype/dejavu")/(
            ("DejaVuSansMono" if family==MONO else "DejaVuSans")+("-Bold" if bold else "")+".ttf")
        if p.exists():
            return ImageFont.truetype(str(p),size).getlength(s)+spacing*len(s)
    except ImportError:
        pass


class Poster:
    def __init__(self,w,h,title,alt):
        self.w, self.h, self.title, self.alt = w,h,title,alt
        self.lines=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title description">',
                    f'<title id="title">{escape(title)}</title><desc id="description">{escape(alt)}</desc>',
                    f'''<defs>
  <pattern id="paper-grid" width="42" height="42" patternUnits="userSpaceOnUse"><path d="M42 0H0V42" fill="none" stroke="{GRID}" stroke-opacity="0.66" stroke-width="1.25"/></pattern>
  <marker id="arrow" viewBox="0 0 20 20" refX="18" refY="10" markerHeight="19" markerWidth="19" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0 20 10 0 20z" fill="{INK}"/></marker>
  <marker id="refund" viewBox="0 0 20 20" refX="18" refY="10" markerHeight="19" markerWidth="19" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0 20 10 0 20z" fill="{VIOLET}"/></marker>
  </defs>''']
        self.rect(0,0,w,h,PAPER)
        self.rect(0,0,w,h,"url(#paper-grid)")
        self.shape([(w-615,0),(w,0),(w,356),(w-234,356),(w-615,109)],LAV)
        self.shape([(0,h-154),(202,h-154),(410,h),(0,h)],LIME)
        self.shape([(w-458,h-146),(w,h-146),(w,h-121),(w-480,h-121)],LAV)
        l=151 if h==1000 else 142
        lx=w-89-l
        self.card(lx-20,39,l+40,l+40,INK,cut=24)
        self.lines.append(f'<image x="{lx}" y="59" width="{l}" height="{l}" xlink:href="data:image/png;base64,{LOGO}" />')
        self.path("M54 45H78M66 33V57",FINE,2)

    def rect(self,x,y,w,h,c,stroke="none",sw=1):
        self.lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{c}" stroke="{stroke}" stroke-width="{sw}"/>')

    def shape(self,points,c,stroke="none",sw=1):
        coords=" ".join(f"{x},{y}" for x,y in points)
        self.lines.append(f'<polygon points="{coords}" fill="{c}" stroke="{stroke}" stroke-width="{sw}"/>')

    def card(self,x,y,w,h,c,stroke="none",sw=1,cut=32):
        self.shape([(x,y),(x+w-cut,y),(x+w,y+cut),(x+w,y+h),(x+cut,y+h),(x,y+h-cut)],c,stroke,sw)

    def path(self,d,c,w=3,arrow=None,dash=None):
        attrs=(f' marker-end="url(#{arrow})"' if arrow else "")+(f' stroke-dasharray="{dash}"' if dash else "")
        self.lines.append(f'<path d="{d}" stroke="{c}" stroke-width="{w}" fill="none"{attrs}/>')

    def text(self,x,y,s,size=40,fill=INK,bold=False,mono=False,tracking=0,anchor="start",width=None):
        font=MONO if mono else SANS
        measured=narrow(font,size,s,bold,tracking)
        if measured is not None:
            left=x-{"start":0,"middle":measured/2,"end":measured}[anchor]
            assert left>=-1 and left+measured<=self.w+1, (self.title,s,left,measured)
            assert width is None or measured<=width, (self.title,s,round(measured,1),width)
        assert 0<y<self.h-5,(s,y)
        self.lines.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{font}" font-size="{size}" font-weight="{700 if bold else 400}" letter-spacing="{tracking}" fill="{fill}">{escape(s)}</text>')

    def meta(self,x,y,s,fill=VIOLET,size=31):
        self.text(x,y,s,size,fill,True,True,1.25)

    def footer(self,label,tag):
        self.path(f"M94 {self.h-103}H{self.w-94}",FINE,2)
        self.text(96,self.h-48,label,29,DIM,width=self.w-650)
        x=self.w-544
        self.card(x,self.h-82,451,52,LAV,cut=12)
        self.text(x+226,self.h-47,tag,26,INK,True,True,0.7,"middle",431)

    def save(self,out,name,render):
        path=out/(name+".svg")
        path.write_text("\n".join(self.lines+["</svg>"])+"\n",encoding="utf-8",newline="\n")
        if render:
            subprocess.run(["inkscape",str(path),f"--export-filename={out/(name+'.png')}",f"--export-width={self.w}"],
                           check=True)
        return {"filename":name,"width":self.w,"height":self.h,"title":self.title,"alt":self.alt}


def cover():
    t=Poster(2500,1000,"What did the wallet spend in USDr?",
        "One Rayls receipt: 3.356290 USDr Value, 10.068869 USDr across four transfer logs, and 2.603706 USDr wallet debit after refund and gas.")
    t.meta(96,105,"RAYLS PUBLIC CHAIN  •  RECEIPT STUDY")
    t.text(90,296,"What did the wallet",111,bold=True,tracking=-2.5,width=1280)
    t.text(86,450,"spend in USDr?",143,bold=True,tracking=-4,width=1270)
    t.path("M96 503H1124",VIOLET,6)
    t.path("M1124 503H1311",LIME,6)
    t.text(96,584,"One receipt can show three different amounts.",38,DIM,width=1230)
    t.text(96,646,"Follow the refund to find the actual debit.",38,DIM,width=1230)
    t.card(96,713,1237,123,INK,cut=23)
    t.rect(120,739,13,68,LIME)
    t.text(154,764,"THE WALLET CALCULATION",25,LIME,True,True,1.2)
    t.text(154,811,"Value − refund + gas",36,WHITE,True,width=1060)
    cards=[
        ("TOP-LEVEL VALUE",HERO["gross_value_units"],WHITE,INK,VIOLET),
        ("TOTAL OF FOUR TRANSFER LEGS",HERO["transfer_leg_sum_units"],LITE,INK,VIOLET),
        ("ACTUAL WALLET DEBIT",HERO["net_debit_units"],INK,WHITE,LIME),
    ]
    for i,(label,value,fill,fg,k) in enumerate(cards):
        x,y,w,h=1441,258+201*i,963,174
        t.card(x+9,y+9,w,h,LAV if i<2 else VIOLET,cut=26)
        t.card(x,y,w,h,fill,VIOLET if i<2 else INK,3,26)
        t.rect(x+26,y+26,9,122,k)
        t.text(x+61,y+54,label,27,k,True,True,0.7,width=815)
        t.text(x+57,y+140,usdr(value),75,fg,True,False,-1.5,width=680)
        t.text(x+w-49,y+133,"USDr",35,fg,True,True,0,"end",120)
    t.footer("Block 14,723,934  ·  Amounts rounded  ·  Wallet debit checked against mainnet RPC","USDr RECEIPT ACCOUNTING")
    return t


def refund():
    t=Poster(2400,1350,"Follow the USDr refund",
        "Caller sends 3.356290 USDr to CreditMessaging, which forwards it to EndpointV2. EndpointV2 sends 2.581761 to the send library and refunds 0.774528 to the caller. Adding 0.021944 gas produces a wallet debit of 2.603706 USDr.")
    t.meta(96,92,"SOURCE RECEIPT  •  FOUR TRANSFER LEGS")
    t.text(89,225,"Follow the USDr refund",104,bold=True,tracking=-2,width=1950)
    t.text(96,295,"Block 14,723,934   ·   Stargate credit message on Rayls Public Chain",39,DIM,width=1980)
    xs=[96,664,1240,1824]
    ws=[393,427,397,480]
    cards=[("ORIGIN","Caller",INK,WHITE,LIME,52),("FORWARD","CreditMessaging",WHITE,INK,VIOLET,38),
           ("FORWARD + REFUND","EndpointV2",LITE,INK,VIOLET,47),("TERMINAL LEG","Send library",WHITE,INK,VIOLET,48)]
    for i,(x,w,(role,name,fill,fg,accent,size)) in enumerate(zip(xs,ws,cards)):
        t.card(x+8,487,w,166,LAV,cut=22)
        t.card(x,479,w,166,fill,INK,3,22)
        t.rect(x+22,509,7,92,accent)
        t.text(x+49,536,role,22,accent,True,True,.4,width=w-75)
        t.text(x+46,603,name,size,fg,True,False,-1,width=w-72)
    for i,(val,leg) in enumerate(zip([HERO["gross_value_units"],HERO["gross_value_units"],HERO["message_fee_units"]],
                                      ["01  ENTERS","02  FORWARDED","03  MESSAGE FEE"])):
        lx=xs[i]+ws[i]+1
        rx=xs[i+1]-7
        mid=(lx+rx)/2
        t.path(f"M{lx} 565H{rx}",INK,5,"arrow")
        t.text(mid,399,leg,23,VIOLET,True,True,.6,"middle",260)
        t.text(mid,445,usdr(val)+" USDr",33,INK,True,False,0,"middle",330)
    t.path("M1438 647V792H292V655",VIOLET,6,"refund")
    t.card(732,696,517,76,LITE,VIOLET,2,15)
    t.text(990,743,"04  REFUND  "+usdr(HERO["refund_units"])+" USDr",27,VIOLET,True,True,0,"middle",487)
    for x in [292,1438]:
        t.path(f"M{x-12} 805H{x+12}",VIOLET,2)
    t.card(95,882,1283,286,INK,cut=30)
    t.rect(131,921,10,185,LIME)
    t.meta(169,939,"EXACT WALLET CALCULATION  •  DISPLAY ROUNDED",LIME,25)
    calc=" − ".join([usdr(HERO["gross_value_units"]),usdr(HERO["refund_units"])])+" + "+usdr(HERO["gas_units"])
    t.text(169,1001,calc,41,WHITE,True,True,width=1090)
    t.text(162,1102,usdr(HERO["net_debit_units"])+" USDr",78,WHITE,True,False,-2,width=1110)
    t.card(1405,882,899,286,LITE,VIOLET,3,30)
    t.meta(1449,938,"INSIDE THE MESSAGE FEE",VIOLET,25)
    t.text(1444,1024,usdr(HERO["message_fee_units"])+" USDr",61,INK,True,False,-1,width=820)
    t.text(1449,1093,"Executor "+usdr(HERO["executor_fee_units"])+" + DVN fees "+usdr(HERO["dvn_fee_units"]),
           31,INK,False,width=812)
    t.footer("Network gas is charged to the caller separately. All amounts shown in USDr.","REFUND + GAS")
    return t


def value():
    t=Poster(2400,1440,"What moved in the receipt?",
        "A four-USDr native send is reflected in both Value and one log. At zero Value, observed examples include a 0.03 USDr direct transfer, a swap credit, a gas-only approval, and a local gas funding mint.")
    t.meta(96,92,"WALLET VIEW  •  READING VALUE AND EVENTS")
    t.text(89,222,"What moved in the receipt?",98,bold=True,tracking=-2,width=1960)
    t.text(96,290,"Four zero-Value examples and a native send for comparison.",39,DIM,width=2010)
    t.card(96,342,2209,76,INK,cut=15)
    for x,name in [(128,"TRANSACTION EXAMPLE"),(728,"TOP-LEVEL VALUE"),(1230,"OBSERVED USDr MOVEMENT")]:
        t.meta(x,392,name,LIME,27)
    m=[
        ("Native send","Recipient view","case-25", "Same 4 USDr in Value and in one transfer log."),
        ("Direct ERC-20 transfer","Caller view","control-transfer","Gas was paid separately by the caller."),
        ("RLS swap","Trader view","case-17","USDr in; RLS moved out separately."),
        ("Allowance approval","Caller view","control-approve","Only "+usdr(EXAMPLES["control-approve"]["wallet_fee_units"])+" USDr in gas."),
        ("Gas funding","Local mint recipient","case-26","USDC.e to escrow; another address paid local gas."),
    ]
    for i,(title,small,key,note) in enumerate(m):
        y=431+i*164
        e=EXAMPLES[key]
        color=LITE if i in (0,4) else WHITE
        t.card(96,y,2209,148,color,FINE,2,20)
        t.rect(97,y+4,11,138,LAV if i!=3 else LIME)
        t.text(130,y+63,title,41,INK,True,False,-.5,width=551)
        t.text(132,y+114,small,30,DIM,width=550)
        t.text(725,y+81,usdr(e["top_value_units"],0)+" USDr",53,INK,True,False,0,width=430)
        move="0 USDr transferred" if key=="control-approve" else usdr(e["asset_movement_units"],6,True)+" USDr"
        t.text(1228,y+60,move,48,VIOLET,True,False,-1,width=1020)
        t.text(1230,y+113,note,30,DIM,width=1020)
    t.footer("Movement is shown before gas unless labeled. Examples use Rayls Public Chain records.","FIVE RECEIPT EXAMPLES")
    return t


def scope():
    t=Poster(2400,1410,"How far did the check go?",
        "23 original calls from one sending wallet reconciled, and four original direct wallet balance pairs matched. A separate follow-up added eight exact balance pairs on two later same-route calls and four exact fee debits from four different zero-Value payers.")
    t.meta(96,94,"EVIDENCE COVERAGE  •  EXPLORER AND NODE")
    t.text(90,222,"How far did the check go?",100,bold=True,tracking=-2,width=1950)
    t.text(96,291,"The original receipt sample and the separate wallet follow-up.",40,DIM,width=2020)
    t.card(96,356,1193,888,INK,cut=36)
    t.meta(140,423,"ORIGINAL FEE ROUTE RECONCILIATION",LIME,29)
    t.text(131,564,f'{COUNT["credit_calls"]} of {COUNT["credit_calls"]}',116,WHITE,True,False,-4,width=980)
    t.text(139,624,"Same payer and route · 9 destination EIDs",39,WHITE,width=1086)
    t.path("M140 671H1244","#676374",3)
    t.text(140,770,usdr(ALL["transfer_leg_sum_units"])+" USDr",62,WHITE,True,False,-1,width=1050)
    t.meta(140,815,"SUM OF TRANSFER LEGS",LAV,27)
    t.text(140,933,usdr(ALL["net_debit_units"])+" USDr",62,WHITE,True,False,-1,width=1050)
    t.meta(140,982,"CALCULATED DEBITS AFTER REFUNDS AND GAS",LAV,26)
    t.card(141,1046,1101,142,LIME,cut=22)
    t.text(170,1135,f'{Decimal(ALL["aggregate_leg_sum_to_net_debit"]):.2f}×',68,INK,True,False,-1,width=265)
    t.text(432,1107,"Recorded movement includes",30,INK,True,width=750)
    t.text(433,1149,"forwarding and refunds.",32,INK,width=750)
    t.card(1332,356,973,888,LITE,VIOLET,3,36)
    t.meta(1376,422,"ORIGINAL DIRECT MAINNET RPC",VIOLET,27)
    total=RPC["transaction_reads_verified"]
    n=RPC["receipts_verified"]
    t.text(1376,516,f'{n} of {total} receipts matched · {RPC["event_logs_verified"]} logs',37,INK,True,width=874)
    a=RPC["complete_native_balance_pairs"]
    b=RPC["account_block_pairs"]
    t.text(1376,581,f"{a} of {b} balance pairs available and exact",36,INK,width=875)
    t.path("M1377 643H2260",VIOLET,2)
    t.meta(1376,713,"SEPARATE FOLLOW-UP",VIOLET,28)
    new=FOLLOWUP["six_new_cases_complete_native_comparisons"]
    t.text(1367,839,str(new),103,bold=True,tracking=-3,width=270)
    t.text(1561,820,"exact balance comparisons",37,INK,True,width=692)
    credits=sum(len(e["balances"]) for e in FOLLOWUP["separate_recent_routes"])
    zero=len(FOLLOWUP["zero_value_cases"])
    t.text(1376,932,f"{credits}  ·  Two later calls on the same bridge route",32,INK,width=880)
    t.text(1376,999,f"{zero}  ·  Four zero-Value calls, four other payers",32,INK,width=880)
    t.card(1376,1061,881,108,WHITE,FINE,2,18)
    t.text(1402,1126,"One RPC endpoint. No state-root proof.",30,INK,True,width=827)
    t.footer("Original indexed balances: 34 of 37 matched. The three exceptions remain unresolved.","SAMPLE BOUNDARY")
    return t


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True,help="Existing or new output folder")
    p.add_argument("--render",action="store_true",help="Also use Inkscape to export PNG files")
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    figures=[fig.save(a.out,name,a.render) for fig,name in [
        (cover(),"00-cover-usdr"),
        (refund(),"01-usdr-refund-route"),
        (value(),"02-usdr-value-examples"),
        (scope(),"03-usdr-evidence-coverage"),
    ]]
    for row,section in zip(figures,["Binance Square cover field",
        "After: How did 3.356290 USDr become a 2.603706 USDr debit?",
        "After: What can move when the Value field is zero?",
        "After: Which balance evidence was available?"]):
        row["placement"]=section
    (a.out/"figures.json").write_text(json.dumps(figures,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":
    main()
