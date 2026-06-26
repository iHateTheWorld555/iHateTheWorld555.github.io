---
permalink: /daily-papers/
title: "Daily Papers"
excerpt: "Daily arxiv papers on audio, speech, music, and acoustics — ranked by score"
layout: daily-papers
---

{% assign papers = site.papers | sort: "date" | reverse %}
{% if papers.size > 0 %}
  {% for paper in papers %}
<div class="paper-day">
  <h1>{{ paper.date | date: "%Y-%m-%d" }} — {{ paper.title }}</h1>
  {{ paper.content }}
</div>
  {% endfor %}
{% else %}
<p>No papers yet. Check back after the next arxiv update!</p>
{% endif %}