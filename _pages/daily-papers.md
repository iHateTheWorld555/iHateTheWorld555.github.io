---
permalink: /daily-papers/
title: "Daily Papers"
excerpt: "Daily arxiv papers on audio, speech, music, and acoustics — ranked by score"
layout: daily-papers
---

{% assign papers = site.papers | sort: "date" | reverse %}
{% if papers.size > 0 %}
  {% assign paper = papers | first %}
  {{ paper.content }}
{% else %}
<p>No papers yet. Check back after the next arxiv update!</p>
{% endif %}
