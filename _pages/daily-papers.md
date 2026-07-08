---
permalink: /daily-papers/
title: "每日论文"
excerpt: "每日 arXiv 音频/语音/音乐/声学论文 — 按评分排序"
layout: daily-papers
---

{% assign papers = site.papers | sort: "date" | reverse %}
{% if papers.size > 0 %}
  {% assign paper = papers | first %}
  {{ paper.content }}
{% else %}
<p>暂无论文，下次 arXiv 更新后再来！</p>
{% endif %}
