"""Build a single-file article preview using Pandoc and the package figures."""
from __future__ import annotations

import base64
from html import escape
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/"Article_EN.md").read_text(encoding="utf-8")
meta=json.loads((ROOT/"visuals/figures.json").read_text(encoding="utf-8"))
article=subprocess.run(
    ["pandoc","--from=gfm","--to=html5","--wrap=none"],input=source,
    check=True,capture_output=True,text=True,encoding="utf-8").stdout


def figure(idx):
    m=meta[idx]
    p=ROOT/"visuals"/(m["filename"]+".png")
    url="data:image/png;base64,"+base64.b64encode(p.read_bytes()).decode("ascii")
    caption=("Cover: a single receipt can report three amounts that measure different things.",
             "Figure 1. The receipt’s four USDr movements and the separate gas fee.",
             "Figure 2. Value is a starting point; these examples show how to read the movement.",
             "Figure 3. The source receipt and balance checks have different coverage.")[idx]
    return f'<figure><img width="{m["width"]}" height="{m["height"]}" src="{url}" alt="{escape(m["alt"])}"><figcaption>{caption}</figcaption></figure>'


# Pandoc generates headers for each section. Insert a figure before the next heading.
def before(fragment,img):
    global article
    start=article.index(fragment)
    ix=article.rfind("<h2 ",0,start)
    assert ix>=0, fragment
    article=article[:ix]+img+"\n"+article[ix:]


before("What held across all 23 sampled calls?",figure(1))
before("Which balance evidence was available?",figure(2))
before("How to check your own receipt",figure(3))
css="""
:root{--ink:#15141c;--muted:#535267;--line:#d9d5e5;--paper:#f2f0f7;--violet:#4e31af;--lime:#e5ff30}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.66 system-ui,sans-serif}
main{max-width:1050px;margin:0 auto;padding:35px 32px 70px}
.actions{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:10px 0 25px}
.actions button{font:600 14px system-ui,sans-serif;padding:9px 13px;border:1px solid var(--ink);border-radius:4px;background:white;color:var(--ink);cursor:pointer}
.actions button:first-child{background:var(--ink);color:var(--lime)}
.actions span,figcaption{font-size:13px;color:var(--muted)}
article{background:#fff;border:1px solid var(--line);padding:clamp(18px,5vw,65px)}
h1{margin:0 0 .6em;font-size:clamp(30px,5vw,52px);letter-spacing:-.045em;line-height:1.09}
h2{margin:1.7em 0 .55em;font-size:clamp(21px,2.8vw,31px);line-height:1.24;letter-spacing:-.02em}
p{margin:.85em 0}a{color:var(--violet);text-underline-offset:.18em}
code{font:0.86em ui-monospace,monospace;background:#f1eef8;padding:.15em .25em;overflow-wrap:anywhere}
figure{margin:1.6em 0 1em}figure img{width:100%;height:auto;border:1px solid var(--line);display:block}figcaption{margin:.5em 0}
.cover{margin:0 0 22px} .cover figure{margin:0}
table{width:100%;border-collapse:collapse;margin:1.2em 0;font-size:.93em}
th,td{border-bottom:1px solid var(--line);text-align:left;padding:.55em .55em;vertical-align:top;overflow-wrap:anywhere}
thead{background:#eeebf7}ol,ul{padding-inline-start:1.5em} li+li{margin-top:.35em}
@media(max-width:550px){main{padding:18px 10px 40px}body{font-size:15px}th,td{padding:.4em .32em}}
"""
script=r"""
const status = document.getElementById("copy-status");
const markdown = JSON.parse(document.getElementById("markdown-source").textContent);
function fallbackText(text) {
  const box=document.createElement("textarea");
  box.value=text;
  box.style="position:fixed;left:0;top:0;opacity:.01;width:2px;height:2px";
  document.body.append(box); box.select();
  const ok=document.execCommand("copy"); box.remove();
  if(!ok) throw new Error("Copy unavailable");
}
async function copyMarkdown() {
  try {
    if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(markdown);}
    else {fallbackText(markdown);}
    status.textContent="Markdown copied.";
  } catch {try {fallbackText(markdown); status.textContent="Markdown copied.";}
    catch {status.textContent="Use the accompanying Article_EN.md file to copy the article.";}}
}
async function copyRich() {
  const article=document.querySelector("article").cloneNode(true);
  article.querySelectorAll("figure").forEach(e=>e.remove());
  try {
    if(navigator.clipboard?.write && typeof ClipboardItem!=="undefined") {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([article.innerHTML],{type:"text/html"}),
        "text/plain": new Blob([markdown],{type:"text/plain"})
      })]);
    } else {throw new Error("Use legacy rich copy");}
    status.textContent="Formatted text copied. Add the PNGs separately.";
  } catch {
    article.style="position:absolute;left:-10000px;top:0";
    document.body.append(article);
    const sel=window.getSelection(), range=document.createRange();
    range.selectNodeContents(article); sel.removeAllRanges(); sel.addRange(range);
    const ok=document.execCommand("copy"); sel.removeAllRanges(); article.remove();
    status.textContent=ok ? "Formatted text copied. Add the PNGs separately."
      : "Use Copy Markdown or the accompanying Article_EN.md file.";
  }
}
document.getElementById("copy-rich").addEventListener("click",copyRich);
document.getElementById("copy-markdown").addEventListener("click",copyMarkdown);
"""
page=f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>How to Check What You Actually Spent in USDr on Rayls</title>
<style>{css}</style></head><body><main>
<div class="actions"><button type="button" id="copy-rich">Copy formatted article</button>
<button type="button" id="copy-markdown">Copy Markdown</button>
<span id="copy-status" role="status">Text and links copy without the images.</span></div>
<div class="cover">{figure(0)}</div><article>{article}</article>
<script id="markdown-source" type="application/json">{json.dumps(source,ensure_ascii=False).replace("<",chr(92)+"u003c")}</script>
<script>{script}</script>
</main></body></html>
"""
(ROOT/"Article_EN.html").write_text(page,encoding="utf-8",newline="\n")
