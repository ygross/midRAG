import re
from pathlib import Path

def html_to_md(html):
    # Remove style, script, header, aside blocks
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL)
    html = re.sub(r'<aside[^>]*>.*?</aside>', '', html, flags=re.DOTALL)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    # Headings
    html = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n', html, flags=re.DOTALL)
    # Code blocks
    html = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>',
                  lambda m: '```\n' + m.group(1) + '\n```\n', html, flags=re.DOTALL)
    html = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html, flags=re.DOTALL)
    # Bold / italic
    html = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html, flags=re.DOTALL)
    html = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html, flags=re.DOTALL)
    html = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html, flags=re.DOTALL)
    # Links
    html = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', html, flags=re.DOTALL)
    # List items
    html = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<ul[^>]*>|</ul>|<ol[^>]*>|</ol>', '', html)
    # Tables
    html = re.sub(r'<th[^>]*>(.*?)</th>', r'| **\1** ', html, flags=re.DOTALL)
    html = re.sub(r'<td[^>]*>(.*?)</td>', r'| \1 ', html, flags=re.DOTALL)
    html = re.sub(r'<tr[^>]*>(.*?)</tr>',
                  lambda m: m.group(1).strip() + ' |\n', html, flags=re.DOTALL)
    html = re.sub(r'<thead[^>]*>|</thead>|<tbody[^>]*>|</tbody>|<table[^>]*>|</table>', '', html)
    # Paragraphs / breaks / dividers
    html = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n', html, flags=re.DOTALL)
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'<hr\s*/?>', '\n---\n', html)
    # Strip remaining tags
    html = re.sub(r'<[^>]+>', '', html)
    # HTML entities
    html = (html.replace('&amp;', '&')
                .replace('&lt;', '<')
                .replace('&gt;', '>')
                .replace('&nbsp;', ' ')
                .replace('&#39;', "'")
                .replace('&quot;', '"'))
    # Clean up excess blank lines
    html = re.sub(r'\n{4,}', '\n\n\n', html)
    html = re.sub(r'[ \t]+\n', '\n', html)
    return html.strip()


for src, dst in [
    ('templates/help.html', 'RAGhelp.md'),
    ('templates/qa.html',   'RAGQA.md'),
]:
    html = Path(src).read_text(encoding='utf-8')
    md   = html_to_md(html)
    Path(dst).write_text(md, encoding='utf-8')
    print(f'Written {dst}  ({len(md):,} chars)')
