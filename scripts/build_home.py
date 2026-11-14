# -*- coding: utf-8 -*-
# Builds _layouts/home.html, the layout of the homepage (_pages/about.md).
# Edit the data below, then run: python3 scripts/build_home.py
import io, os
BG="#FFFFFF"; INK="#1A1D1B"; MUTED="#5F6661"; QUOTE="#6A706B"; RULE="#E6E9E6"; HAIR="#DDE2DE"
# Primary accent is muted sage green: GREEN at 4.85:1 for small text, GREEN2 for display type.
# Surfaces stay white; greys carry a faint green cast so they sit with the sage, never beige.
GREEN="#557A5E"; GREEN2="#6F9C7A"; LINE="#D3DBD5"; LINE2="#EFEFEF"; TINT="#FFFFFF"
ME="<b>Yanru Huo</b>"
PUBS=[
 dict(y=2026, top=True,  img="/images/routedmd.jpg", t="Route-DMD: Distribution Matching Distillation with Task-Routed Mechanism for Speech Foundation Models",
      a=f"{ME}, Zhikang Niu, Wenming Tu, Junxi Liu, Tian Tan, Shan Yang, Yipeng Kang, Ziyang Ma, Xie Chen<sup>&dagger;</sup>, Zilong Zheng<sup>&dagger;</sup>", venue="arXiv Preprint", role="", date="2026-11",
      L=[("arXiv","https://arxiv.org/abs/2611.08011"),("Code","https://github.com/iHateTheWorld555/AuK-RouteDMD",7),("Demo","https://route-dmd.github.io/")]),
 dict(y=2026, top=True,  img="/images/auk_fig2.jpg", t="AuK Technical Report: An Open-Source Foundational Model for Speech Generation and Editing",
      a="AuK Team", venue="Technical Report", note="Core Contributor", role="", date="2026-09",
      L=[("arXiv","https://arxiv.org/abs/2609.08936"),("Code","https://github.com/Tencent-Hunyuan/AuK",1601),("Project","https://auk-project.github.io/"),("Model","https://huggingface.co/tencent/AuK"),("Demo","https://huggingface.co/spaces/tencent/AuK")]),
 dict(y=2026, top=True,  img="/images/visa.png", t="VISA: A Visual Information Strengthened Audio-Reasoning System for the Interspeech 2026 ARC Agent Track",
      a=f"Wenming Tu*, Jian Gao*, {ME}, Yixuan Wang, Jing Peng, Bohan Li, Ziyang Ma, Tao Liu, Shuai Fan<sup>&dagger;</sup>, Kai Yu, Xie Chen, Zilong Zheng<sup>&dagger;</sup>", venue="INTERSPEECH 2026", oral=True, role="", date="2026-06",
      L=[("arXiv","https://arxiv.org/abs/2606.07264"),("Code","https://github.com/DELTA-DoubleWise/Audio-Mind",14)]),
 dict(y=2026, top=True,  img="/images/mova.png", t="MOVA: Towards Scalable and Synchronized Video-Audio Generation",
      a="SII-OpenMOSS Team", venue="arXiv Preprint", note="Core Contributor", role="", date="2026-02",
      L=[("arXiv","https://arxiv.org/abs/2602.08794"),("Project","https://mosi.cn/models/mova"),("Code","https://github.com/OpenMOSS/MOVA",1144),("Model","https://huggingface.co/collections/OpenMOSS-Team/mova")]),
 dict(y=2026, top=False, img="/images/voxcanvas.jpg", t="VoxCanvas-41M: A Large-Scale Bilingual Dataset for Instruction-Based Speech Editing and Its Learning Dynamics",
      a=f"Zhikang Niu, Wenming Tu, Yalin Li, {ME}, Junxi Liu, Tianrui Wang, Ruiqi Yan, Junxuan Liang, Zilong Zheng<sup>&dagger;</sup>, Ziyang Ma, Xie Chen<sup>&dagger;</sup>", venue="arXiv Preprint", role="", date="2026-11",
      L=[("arXiv","https://arxiv.org/abs/2611.08251"),("Project","https://zhikangniu.github.io/voxcanvas/")]),
 dict(y=2026, top=False, img="/images/tinyaudio.jpg", t="TinyAudio: Compact and Efficient Text-to-Audio Generation for Low-Resource Deployment",
      a=f"Junxi Liu, Xiquan Li, Wenhao Guan, Yifan Duan, Zhikang Niu, {ME}, Ziyang Ma, Xie Chen<sup>&dagger;</sup>", venue="arXiv Preprint", role="", date="2026-09",
      L=[("arXiv","https://arxiv.org/abs/2609.31525")]),
 dict(y=2026, top=False, img="/images/mmae.png", t="MMAE: A Massive Multitask Audio Editing Benchmark",
      a="MMAE Team", venue="arXiv Preprint", note="Contributor", role="", date="2026-06",
      L=[("arXiv","https://arxiv.org/abs/2606.07229"),("Code","https://github.com/ddlBoJack/MMAE",113),("Dataset","https://huggingface.co/datasets/BoJack/MMAE")]),
 dict(y=2025, top=True,  img="/images/ditreducio_fig1.png", t="DiTReducio: A Training-Free Acceleration for DiT-Based TTS via Progressive Calibration",
      a=f"{ME}, Ziyue Jiang, Zuoli Tang, Qingyang Hong, Zhou Zhao<sup>&dagger;</sup>", venue="ACL 2026 Findings", role="", date="2025-09",
      L=[("arXiv","https://arxiv.org/abs/2509.09748"),("Code","https://github.com/MM-Speech/DiTReducio",15)]),
]
NEWS=[("Jun 2026","1 paper was accepted to <b>INTERSPEECH 2026</b> and selected for an oral presentation!"),
      ("Apr 2026","1 paper was accepted by <b>ACL 2026 Findings</b>!"),
      ("Feb 2026","We won 2nd place in the Agent Track of the <a href='https://audio-reasoning-challenge.github.io/leaderboard/'>Interspeech 2026 Audio Reasoning Challenge</a>. See the <a href='https://arxiv.org/abs/2602.14224'>Challenge Report</a>.")]
EDU=[("2026.09 – 2031.06 (expected)","Ph.D.","X-LANCE Lab, Shanghai Jiao Tong University (SJTU) &amp; Beijing Institute for General Artificial Intelligence (BIGAI)"),
     ("2022.09 – 2026.06","B.E.","Xiamen University (XMU)")]
INT=[("2026.07 – present","Tencent Hunyuan","Shanghai, China"),("2025.11 – 2026.06","Sii &amp; OpenMOSS","Shanghai, China")]
HON=[("2024.11","Second Prize, China Undergraduate Mathematical Contest in Modeling (CUMCM), National Level"),("2024.09","National Scholarship")]
BIO=("I'm currently a first-year Ph.D. student (2026) at <a href='https://x-lance.sjtu.edu.cn/en'>X-LANCE Lab</a>, "
     "<a href='https://en.sjtu.edu.cn/'>Shanghai Jiao Tong University</a> &amp; <a href='https://www.bigai.ai/'>Beijing Institute for General Artificial Intelligence (BIGAI)</a>, "
     "advised by <a href='https://chenxie95.github.io/'>Prof. Xie Chen</a> and <a href='https://zilongzheng.github.io/'>Dr. Zilong Zheng</a>.")
QUOTE="Your lack of commitment is an insult to those who believe in you."
SCHOLAR="https://scholar.google.com/citations?user=D_LzryQAAAAJ"

# Inline stroke icons, 24x24 viewBox, drawn with currentColor.
def ico(d): return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
# Three brand colours stay exact: arXiv red, GitHub black, Hugging Face gold.
# Own-site links (Demo, Email) take the sage accent. Project, Dataset, Scholar share one sage-grey slate.
ICONC={"arXiv":"#B31B1B","Code":"#24292F","Model":"#FFD21E",
       "Demo":"#557A5E","Project":"#2166B0","Dataset":"#FFD21E",
       "Email":"#557A5E","Scholar":"#FFD21E","GitHub":"#24292F"}
ICON={
 "arXiv":ico('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>'),
 "Project":ico('<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18"/>'),
 "Code":ico('<path d="M8 7l-5 5l5 5"/><path d="M16 7l5 5l-5 5"/><path d="M14 4l-4 16"/>'),
 "Model":ico('<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5l8-4.5"/><path d="M12 12v9"/>'),
 "Demo":ico('<circle cx="12" cy="12" r="9"/><path d="M10 8.5l5.5 3.5l-5.5 3.5z"/>'),
 "Dataset":ico('<ellipse cx="12" cy="5.5" rx="8" ry="2.5"/><path d="M4 5.5v13c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-13"/><path d="M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5"/>'),
 "Email":ico('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5l8.5 6.5l8.5-6.5"/>'),
 "Scholar":ico('<path d="M2 9.5L12 4l10 5.5L12 15z"/><path d="M6.5 12v4.5c0 1.4 2.5 2.5 5.5 2.5s5.5-1.1 5.5-2.5V12"/><path d="M22 9.5v5"/>'),
 "GitHub":'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34c-.45-1.16-1.11-1.47-1.11-1.47c-.91-.62.07-.6.07-.6c1 .07 1.53 1.03 1.53 1.03c.89 1.53 2.34 1.09 2.91.83c.09-.65.35-1.09.63-1.34c-2.22-.25-4.55-1.11-4.55-4.94c0-1.09.39-1.98 1.03-2.68c-.1-.25-.45-1.27.1-2.65c0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02c.55 1.38.2 2.4.1 2.65c.64.7 1.03 1.59 1.03 2.68c0 3.84-2.34 4.68-4.57 4.93c.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2z"/></svg>',
}
# Type scale, one size per role. Every label uses the same META style.
META=f"font-size:14.5px;letter-spacing:.1em;text-transform:uppercase;color:{MUTED};font-variant:normal"
css=f'''
@font-face{{font-family:"ETBook";src:url(/assets/fonts/home/et-book-roman-line-figures.woff) format("woff");font-weight:400}}
@font-face{{font-family:"ETBook";src:url(/assets/fonts/home/et-book-display-italic-old-style-figures.woff) format("woff");font-weight:400;font-style:italic}}
@font-face{{font-family:"ETBook";src:url(/assets/fonts/home/et-book-bold-line-figures.woff) format("woff");font-weight:700}}
@font-face{{font-family:"PlexMono";src:url(/assets/fonts/home/plexmono-italic.woff2) format("woff2");font-style:italic}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth;background:{BG}}}
body{{background:{BG};color:{INK};font-family:"ETBook",Palatino,Georgia,serif;-webkit-font-smoothing:antialiased;padding-bottom:80px}}
a{{color:inherit;text-decoration:none}}
svg{{width:15px;height:15px;flex:none}}
.w{{max-width:1680px;margin:0 auto;padding:0 48px}}
.top{{display:flex;justify-content:flex-end;align-items:center;padding:20px 0;{META};border-bottom:1px solid {INK}}}
.top a{{margin-left:30px}}
.top a:hover{{color:{INK};border-bottom:1px solid {LINE}}}
.front{{display:grid;grid-template-columns:minmax(0,1fr) 440px;grid-template-areas:"hero news" "edu news";column-gap:40px;padding-top:56px}}
.hero{{grid-area:hero;padding-bottom:56px}}
#edu{{grid-area:edu}}
.idrow{{display:flex;align-items:center;gap:30px}}
.idrow img{{width:180px;height:180px;border-radius:50%;object-fit:cover;object-position:50% 30%;flex:none;box-shadow:0 0 0 1px {RULE},0 0 0 7px {BG},0 0 0 8px {LINE}}}
h1{{font-size:116px;font-weight:400;line-height:.95;letter-spacing:-.025em;white-space:nowrap}}
h1 i{{color:{GREEN2}}}
.lede{{font-size:23px;line-height:1.52;margin-top:34px;max-width:none}}
.lede a{{border-bottom:1px solid {LINE}}}
.lede a:hover{{color:{INK};border-color:{LINE}}}
.quote{{font-family:"PlexMono",Menlo,monospace;font-style:italic;font-size:16px;line-height:1.6;color:{QUOTE};margin-top:16px}}
.ri{{margin-top:24px;font-size:18px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}
.ri .k{{{META}}}
.ri .tg{{font-style:italic}}
.ct{{margin-top:18px;display:flex;flex-wrap:wrap;align-items:center;gap:4px 22px;font-size:18px}}
.ct a{{display:inline-flex;align-items:center;gap:7px}}
.ct a svg{{color:{GREEN2};width:15px;height:15px}}
.ct a:hover{{color:{GREEN}}}
.news{{grid-area:news;border-left:1px solid {RULE};padding-left:28px}}
/* the column spans hero and education and scrolls with the page */
.nin{{display:flex;flex-direction:column;max-height:calc(100vh - 48px)}}
.news h2{{font-weight:400;font-size:33px;line-height:1.1;color:{INK};display:flex;justify-content:space-between;align-items:baseline;margin-bottom:22px}}
.news h2 .tt{{display:inline-flex;align-items:center}}
.news h2 .more{{{META};display:none}}
.news.of h2 .more{{display:inline}}
/* height:0 + flex-grow: the list fills the hero row height and never stretches it */
.scroll{{position:relative;flex:0 1 auto;min-height:0;display:flex;overflow-y:auto;padding:0 12px 0 7px;scrollbar-width:thin;scrollbar-color:{LINE} transparent}}
.scroll::-webkit-scrollbar{{width:4px}}.scroll::-webkit-scrollbar-thumb{{background:{LINE};border-radius:2px}}
.items{{border-left:1px solid {LINE};margin-left:0;display:flex;flex-direction:column;flex:1}}
.item{{position:relative;padding:0 0 30px 24px;font-size:20px;line-height:1.55}}
/* dot is 9px wide, rail is 1px, so left is -(9+1)/2 = -5px and both centres land on the same pixel */
.item::before{{content:"";position:absolute;left:0;top:6px;width:10px;height:10px;box-sizing:border-box;border-radius:50%;background:{BG};border:2px solid {GREEN2};transform:translateX(calc(-50% - .5px))}}
.item:last-child{{padding-bottom:2px}}
.item:last-of-type::after{{display:none}}
.item .d{{display:block;{META};margin-bottom:4px}}
.item a{{border-bottom:1px solid {LINE}}}
.fade{{position:sticky;bottom:0;height:34px;margin-top:-34px;background:linear-gradient(rgba(255,255,255,0),#FFFFFF);pointer-events:none;display:none}}
.news.of .fade{{display:block}}
.blk{{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;padding:34px 0;border-top:1px solid {HAIR}}}
.blk:first-child{{border-top:none;padding-top:0}}
/* Internship and Honors share one row */
.pair{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);column-gap:40px;border-top:1px solid {HAIR}}}
.pair .blk{{border-top:none;padding-top:34px}}
.blk h2{{font-weight:400;font-size:33px;line-height:1.1;text-wrap:balance}}
.em{{font-size:.78em;margin-right:.3em;line-height:1;display:inline-block;vertical-align:-.04em}}
.blk h2 small{{display:block;{META};margin-bottom:8px}}
.tl{{list-style:none;border-left:1px solid {LINE};margin-left:4px}}
.tl li{{position:relative;padding:0 0 18px 24px}}
.tl li:last-child{{padding-bottom:0}}
.tl li::before{{content:"";position:absolute;left:0;top:6px;width:10px;height:10px;box-sizing:border-box;border-radius:50%;background:{BG};border:2px solid {GREEN2};transform:translateX(calc(-50% - .5px))}}
.tl li:first-child::before{{background:{GREEN2};border-color:{GREEN2}}}
.tl .d{{{META};margin-bottom:3px}}
.tl .t{{font-size:20px;line-height:1.45}}
.tl .t b{{font-weight:400;color:{INK}}}
.tl .s{{font-size:18px;font-style:italic;color:{MUTED};line-height:1.45}}
.sec{{padding:60px 0 0}}
.sh{{border-bottom:1px solid {INK};padding-bottom:12px}}
.sh h2{{font-weight:400;font-size:52px;letter-spacing:-.01em}}
.yr{{display:grid;grid-template-columns:140px minmax(0,1fr);gap:40px;padding:30px 0 10px;border-bottom:1px solid {HAIR}}}
.yr .y{{font-size:58px;line-height:1;color:{GREEN2};font-variant-numeric:lining-nums;position:sticky;top:20px;align-self:start}}
.yr .y small{{display:block;font-size:20px;font-style:italic;color:{MUTED};margin-top:12px}}
.p{{display:grid;grid-template-columns:400px minmax(0,1fr);gap:44px;padding:0 0 34px;margin-bottom:34px;border-bottom:1px solid {HAIR}}}
.p:last-child{{border-bottom:none;margin-bottom:0}}
/* every figure box has the same size, the figure is fitted inside without cropping */
.fig{{position:relative;width:400px;height:270px;border:1px solid {RULE};border-radius:5px;background:#fff;display:flex;align-items:center;justify-content:center;padding:14px;margin:0 0 18px 10px}}
/* Bookmark tab: a solid rounded label that hangs off the lower-left corner of the panel,
   protruding past the border on both edges. */
.bm{{position:absolute;left:-10px;top:-11px;z-index:2;display:inline-flex;align-items:center;gap:8px;
  max-width:calc(100% - 26px);
  background:{GREEN};color:#fff;font-size:14.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  line-height:1;padding:9px 15px;border-radius:5px;
  box-shadow:0 2px 6px rgba(26,29,27,.18)}}
.bm span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bm em{{font-style:normal;font-size:12.5px;letter-spacing:.1em;background:#fff;color:{GREEN};padding:3px 7px;border-radius:3px;flex:none}}
.im{{display:flex;align-items:center;justify-content:center;width:100%;height:100%}}
.im img{{max-width:100%;max-height:100%;object-fit:contain;display:block}}
.p h3{{font-weight:400;font-size:26px;line-height:1.28}}
.p .a{{font-size:18px;color:{MUTED};margin-top:10px;line-height:1.52}}
.p .a b{{color:{INK}}}
.lk{{margin-top:18px;display:flex;flex-wrap:wrap;gap:10px}}
.lk a{{display:inline-flex;align-items:center;gap:9px;font-size:16.5px;font-weight:700;line-height:1;padding:9px 16px;border-radius:999px;border:1px solid transparent;background:var(--bg);color:#fff;transition:filter .15s,transform .15s}}
.lk a svg{{color:#fff;width:16px;height:16px;opacity:.95}}
.lk a .st{{display:inline-flex;align-items:center;gap:4px;font-size:16.5px;color:#fff;padding-left:8px;margin-left:1px;border-left:1px solid rgba(255,255,255,.45)}}
.lk a .st svg{{width:14px;height:14px;color:#FFD35C;opacity:1}}
.lk a:hover{{filter:brightness(.92);transform:translateY(-1px)}}

.nb{{font-size:18px;font-style:italic;color:{GREEN};margin-top:7px;display:flex;align-items:center;gap:7px}}
.nb::before{{content:"";width:18px;height:1px;background:{LINE};display:inline-block}}
.note{{font-size:18px;font-style:italic;color:{MUTED};margin-top:14px}}
.note a{{color:{INK};border-bottom:1px solid {LINE}}}
@media (max-width:1060px){{h1{{font-size:78px}}.front{{grid-template-columns:minmax(0,1fr) 320px;column-gap:32px}}
.p{{grid-template-columns:320px minmax(0,1fr);gap:32px}}.fig{{width:320px;height:210px}}.idrow img{{width:150px;height:150px}}}}
@media (max-width:760px){{.w{{padding:0 20px}}
.front{{grid-template-columns:minmax(0,1fr);grid-template-areas:"hero" "news" "edu";padding-top:30px}}.hero{{padding-bottom:30px}}
.idrow{{gap:18px}}.idrow img{{width:112px;height:112px}}h1{{font-size:clamp(40px,12vw,60px);white-space:normal}}
.lede{{font-size:18.5px;margin-top:24px}}.quote{{font-size:13px}}
.news{{border-left:none;padding-left:0;border-top:1px solid {RULE};padding:22px 0 30px}}.nin{{max-height:none}}.scroll{{max-height:320px}}
.sh h2{{font-size:36px}}.yr{{grid-template-columns:minmax(0,1fr);gap:16px}}.yr .y{{position:static;font-size:38px}}
.p{{grid-template-columns:minmax(0,1fr);gap:16px}}.fig{{width:100%;max-width:400px;height:240px}}
.blk{{gap:18px}}.pair{{grid-template-columns:minmax(0,1fr)}}.pair .blk+.blk{{border-top:1px solid {HAIR}}}}}
'''
STAR='<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.6l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5-5.8-3.05-5.8 3.05 1.1-6.5-4.7-4.6 6.5-.95z"/></svg>'
def link(l):
    tag,url=l[0],l[1]
    stars=f'<span class="st">{STAR}{l[2]}</span>' if len(l)>2 else ""
    return f'<a href="{url}" style="--bg:{ICONC[tag]}">{ICON[tag]}{tag}{stars}</a>'
def pub(p):
    note=f'<div class="nb">{p["note"]}</div>' if p.get("note") else ""
    return f'''<article class="p"><div class="fig"><div class="bm"><span>{p["venue"]}</span>{'<em>Oral</em>' if p.get("oral") else ''}</div><div class="im"><img src="{p["img"]}" alt=""></div></div><div>
<h3>{p["t"]}</h3><div class="a">{p["a"]}</div>{note}
<div class="lk">{"".join(link(l) for l in p["L"])}</div></div></article>'''
def year(y):
    ps=[p for p in PUBS if p["y"]==y]
    # ordering rule kept from before: first-author, co-first and core-contributor papers first, then by date
    ps=sorted([p for p in ps if p["top"]],key=lambda p:p["date"],reverse=True)+sorted([p for p in ps if not p["top"]],key=lambda p:p["date"],reverse=True)
    return f'<div class="yr"><div class="y">{y}<small>{len(ps)} paper{"s" if len(ps)>1 else ""}</small></div><div>{"".join(pub(p) for p in ps)}</div></div>'
def tl(rows,fmt): return '<ul class="tl">'+"".join(fmt(r) for r in rows)+"</ul>"
CONTACT=[("Email","mailto:huoyanru123@gmail.com"),("Scholar",SCHOLAR),("GitHub","https://github.com/iHateTheWorld555")]
JS='''<script>(function(){var n=document.querySelector(".news"),s=n.querySelector(".scroll");function f(){n.classList.toggle("of",s.scrollHeight>s.clientHeight+2)}f();addEventListener("resize",f);addEventListener("load",f)})()</script>'''
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Yanru Huo</title><meta name="description" content="Yanru Huo's academic homepage"><link rel="icon" type="image/svg+xml" href="/images/favicon.svg"><link rel="icon" type="image/png" href="/images/favicon-32x32.png" sizes="32x32"><link rel="apple-touch-icon" sizes="180x180" href="/images/apple-touch-icon-180x180.png"><style>{css}</style></head><body><div class="w">
<nav class="top"><a href="#news">news</a><a href="#pubs">publications</a><a href="/daily-papers/">daily papers</a></nav>
<div class="front"><header class="hero">
<div class="idrow"><img src="/images/profile.jpg" alt="Yanru Huo"><h1>Yanru <i>Huo</i></h1></div>
<div class="ct">{"".join(f'<a href="{u}">{ICON[t]}{"Google Scholar" if t=="Scholar" else t}</a>' for t,u in CONTACT)}</div>
<p class="lede">{BIO}</p>
<p class="quote">{QUOTE}</p>
<div class="ri"><span class="k">Research Interests</span><span class="tg">Speech synthesis, audio understanding</span></div>
</header>
<aside class="news" id="news"><div class="nin"><h2><span class="tt"><span class="em">&#128227;</span>News</span><span class="more">scroll for more</span></h2><div class="scroll">
<div class="items">{"".join(f'<div class="item"><span class="d">{d}</span>{t}</div>' for d,t in NEWS)}</div><div class="fade"></div></div></div></aside>
<section id="edu">
<div class="blk"><h2><small>01</small><span class="em">&#127891;</span>Education</h2>{tl(EDU, lambda r: f'<li><div class="d">{r[0]}</div><div class="t"><b>{r[1]}</b>, {r[2]}</div></li>')}</div>
<div class="pair"><div class="blk"><h2><small>02</small><span class="em">&#128188;</span>Internship</h2>{tl(INT, lambda r: f'<li><div class="d">{r[0]}</div><div class="t">{r[1]}</div><div class="s">{r[2]}</div></li>')}</div>
<div class="blk"><h2><small>03</small><span class="em">&#127942;</span>Honors &amp; Awards</h2>{tl(HON, lambda r: f'<li><div class="d">{r[0]}</div><div class="t">{r[1]}</div></li>')}</div></div>
</section></div>
<section class="sec" id="pubs"><div class="sh"><h2><span class="em">&#128218;</span>Publications</h2></div>
{year(2026)}{year(2025)}
<p class="note">* equal contribution. &dagger; corresponding author. Full list on <a href="{SCHOLAR}">Google Scholar</a>.</p></section>
</div>{JS}</body></html>'''
out=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","_layouts","home.html")
assert "{{" not in html and "{%" not in html
io.open(out,"w",encoding="utf-8").write(html)
print("ok middots:", html.count("·")+html.count("&middot;"))
