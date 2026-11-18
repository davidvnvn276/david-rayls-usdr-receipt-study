#!/usr/bin/env python3
"""Regenerate publication figures from the calculated results (optional: Pillow and DejaVu fonts)."""
from pathlib import Path
from decimal import Decimal
import csv
import json
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"visuals"
S=json.loads((ROOT/"results"/"summary.json").read_text())
TX={r["case_id"]:r for r in csv.DictReader((ROOT/"results"/"transactions.csv").open(encoding="utf-8"))}
CHECKS=list(csv.DictReader((ROOT/"results"/"balance_checks.csv").open(encoding="utf-8")))
H=S["hero_case"]
BG="#111929"
INK="#F5F6FE"
MUT="#B8C2D8"
EDGE="#36415B"
CARD="#1D2940"
LIME="#DBF686"
LAV="#CFBFFF"
TEAL="#97EAD5"
BRIGHT="#FAF9FF"
DARK="#12192D"
SUB="#525E7C"
PAPER="#F1F2F9"
WHITE="#FFFFFF"
STROKE="#D9DDEE"
ACCENT="#432B91"
GREEN="#17624F"


def font(size, weight="regular"):
    stem={"regular":"DejaVuSans","bold":"DejaVuSans-Bold","mono":"DejaVuSansMono"}[weight]
    return ImageFont.truetype(stem+".ttf",size)


def text(d,x,y,s,size,color=INK,weight="regular",maxw=None):
    f=font(size,weight)
    if maxw and d.textlength(s,font=f)>maxw:
        raise ValueError(f"Text overflow ({maxw}px): {s}")
    d.text((x,y),s,font=f,fill=color,anchor="lt")


def center(d,x,y,s,size,color=INK,weight="regular"):
    f=font(size,weight)
    d.text((x,y),s,font=f,fill=color,anchor="mt")


def box(d,bounds,fill=CARD,out=EDGE,radius=24,width=2):
    d.rounded_rectangle(bounds,radius=radius,fill=fill,outline=out,width=width)


def amount(n,n_places=6):
    return f"{Decimal(n)/Decimal(10**18):,.{n_places}f}"


def width_measure(d,s,size):
    return d.textlength(s,font=font(size))


def arrow(d,x0,y,x1,color):
    d.line((x0,y,x1-12,y),fill=color,width=6)
    d.polygon([(x1,y),(x1-17,y-10),(x1-17,y+10)],fill=color)


def cover():
    im=Image.new("RGB",(2000,800),BG)
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,17,800),fill=LIME)
    for x in range(880,2000,96):
        d.line((x,0,x,800),fill="#1A2539",width=1)
    for y in range(32,800,82):
        d.line((872,y,2000,y),fill="#1A2539",width=1)
    text(d,88,70,"Rayls Public Chain  /  Mainnet",29,LAV,"mono")
    text(d,86,160,"What did the wallet",73,INK,"bold",860)
    text(d,86,256,"spend in USDr?",73,INK,"bold",860)
    d.line((88,373,795,373),fill=EDGE,width=2)
    text(d,88,431,"One native balance.",38,LIME,"bold")
    text(d,88,491,"An ERC-20 view at 0x0400.",38,INK)
    text(d,88,611,"Receipt study · 18 November 2026",27,MUT)
    labels=[("Value attached",H["gross_value_units"],LAV),
            ("Network fee",H["gas_units"],TEAL),
            ("Net wallet debit",H["caller_debit_units"],LIME)]
    for i,(label,value,col) in enumerate(labels):
        y=89+i*186
        box(d,(962,y,1912,y+156),CARD,EDGE)
        d.rounded_rectangle((982,y+24,997,y+132),radius=7,fill=col)
        text(d,1030,y+28,label,32,MUT)
        text(d,1030,y+79,amount(value)+" USDr",48,col,"bold",790)
    text(d,978,688,"Block 14,723,934 · values rounded to 6 decimals",27,MUT,maxw=898)
    im.save(OUT/"01-usdr-wallet-cost-cover.png")


def routed():
    im=Image.new("RGB",(1600,900),PAPER)
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,1600,11),fill=ACCENT)
    text(d,65,47,"Rayls Mainnet  /  18 Nov 2026  /  Block 14,723,934",23,ACCENT,"mono")
    text(d,64,104,"Where the attached USDr went",57,DARK,"bold")
    text(d,64,184,"Four Transfer logs from one sendCredits call",27,SUB)
    xs=[65,443,821,1199]
    w=335
    labels=[("Caller","pays network gas"),("CreditMessaging","forwards Value"),
            ("EndpointV2","splits the amount"),("SendUln302","receives message fee")]
    for x,(a,b) in zip(xs,labels):
        box(d,(x,359,x+w,459),WHITE,STROKE,radius=18)
        text(d,x+18,383,a,28,DARK,"bold",w-36)
        text(d,x+18,424,b,21,SUB,maxw=w-36)
    for i,val in enumerate([H["gross_value_units"],H["forwarded_units"],H["message_fee_units"]]):
        start=xs[i]+w+5
        end=xs[i+1]-5
        arrow(d,start,407,end,ACCENT)
        center(d,(start+end)//2,322,amount(val),26,ACCENT,"mono")
    xleft=xs[0]+168
    xright=xs[2]+168
    d.line((xright,350,xright,268,xleft,268,xleft,337),fill=GREEN,width=5,joint="curve")
    d.polygon([(xleft,350),(xleft-9,332),(xleft+9,332)],fill=GREEN)
    center(d,(xleft+xright)//2,238,"Refund  "+amount(H["refund_units"])+" USDr",25,GREEN,"bold")
    box(d,(65,516,1535,668),WHITE,STROKE,radius=20)
    text(d,91,539,"Message fee breakdown from two events",26,DARK,"bold")
    text(d,91,598,"Executor "+amount(H["executor_event_units"]),27,ACCENT,"mono",490)
    text(d,575,598,"+  fees[] "+amount(H["dvn_event_sum_units"]),27,ACCENT,"mono",540)
    text(d,1090,598,"=  "+amount(H["message_fee_units"])+" USDr",27,GREEN,"mono",422)
    box(d,(65,703,1535,814),BG,BG,radius=20)
    text(d,90,724,"Net wallet debit",26,MUT)
    text(d,90,767,amount(H["message_fee_units"])+"  +  "+amount(H["gas_units"])+" gas  =  "+amount(H["caller_debit_units"])+" USDr",33,LIME,"mono",1400)
    text(d,65,850,"Figures rounded to 6 decimals. Exact smallest-unit reconciliation is in the evidence package.",22,SUB)
    im.save(OUT/"02-usdr-fee-flow.png")


def zero_value():
    im=Image.new("RGB",(1600,900),BG)
    d=ImageDraw.Draw(im)
    text(d,64,54,"Rayls Mainnet  /  Captured examples",23,LAV,"mono")
    text(d,64,112,"Zero Value, three outcomes",57,INK,"bold")
    text(d,64,193,"Check the wallet’s USDr movement and the fee separately.",28,MUT)
    cols=[
        ("control-transfer","ERC-20 transfer","0.030000 USDr sent","Matching transfer calldata and log",LAV),
        ("control-approve","Direct approval","No USDr transfer","Allowance changed; sender paid gas",TEAL),
        ("case-17","RLS to USDr swap",amount(TX["case-17"]["caller_receipt_net_units"])+" USDr in","RLS moved out in the same receipt",LIME),
    ]
    for i,(cid,label,flow,annotation,col) in enumerate(cols):
        r=TX[cid]
        assert int(r["top_level_value_units"])==0
        own=next(x for x in CHECKS if x["case_id"]==cid and x["address"]==r["caller"])
        assert own["matched"]=="True"
        x=65+i*506
        box(d,(x,278,x+458,738),CARD,EDGE)
        d.rectangle((x+26,309,x+79,315),fill=col)
        text(d,x+26,344,label,30,INK,"bold",410)
        text(d,x+26,397,"Block "+f"{int(r['block']):,}",23,MUT)
        text(d,x+26,469,flow,27,col,"bold",405)
        text(d,x+26,523,annotation,19,MUT,maxw=405)
        d.line((x+26,571,x+431,571),fill=EDGE,width=2)
        text(d,x+26,599,"Caller’s USDr balance change",22,MUT,maxw=402)
        n=int(own["observed_delta_units"])
        label=("+" if n>0 else "")+amount(n)+" USDr"
        text(d,x+26,654,label,35,INK,"bold",405)
    text(d,65,792,"Wallet changes include network gas. Figures rounded to 6 decimals.",24,MUT)
    text(d,65,835,"The transfer control corroborates the sender’s debit; its recipient’s exact historical balance was not resolved.",22,MUT,maxw=1460)
    im.save(OUT/"03-usdr-zero-value-examples.png")


if __name__=="__main__":
    OUT.mkdir(exist_ok=True)
    cover()
    routed()
    zero_value()
