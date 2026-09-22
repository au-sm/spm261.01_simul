"""
Shared top nav bar injected into every SM Owners League page (Dashboard,
Rulebook, Sponsorship Marketplace, Match Engine Walkthrough) so the four
separately-hosted pages read as one connected site instead of four
unrelated links.

SINGLE SOURCE OF TRUTH for the live URLs: update PAGES here and every
page picks up the new links next time it's regenerated (Dashboard,
Rulebook, Sponsorship Marketplace all import this; classroom-demo/index.html
has no generator script, so its copy has to be hand-edited to match if a
URL ever changes -- see that file's own <!-- SITE_NAV --> comment).

Uses each page's own --ink/--paper/--accent CSS custom properties
(already identical across all four pages, dark-mode included) rather
than hardcoded colors, so the bar automatically matches whichever
page it's dropped into, light or dark.
"""

GH_BASE = "https://au-sm.github.io/spm261.01_simul"

PAGES = [
    ("home", "Home", f"{GH_BASE}/"),
    ("dashboard", "Dashboard", f"{GH_BASE}/dashboard/"),
    ("budget", "Budget Dashboard", f"{GH_BASE}/budget/"),
    ("rulebook", "Rulebook", f"{GH_BASE}/rulebook/"),
    ("sponsorship", "Sponsorship Marketplace", f"{GH_BASE}/sponsorship/"),
    ("tv", "TV Rights Marketplace", f"{GH_BASE}/tv/"),
    ("attendance", "Attendance &amp; Ticket Sales", f"{GH_BASE}/attendance/"),
    ("walkthrough", "Match Engine Walkthrough", f"{GH_BASE}/walkthrough/"),
    ("replay", "Matchday Replay", f"{GH_BASE}/matchday-replay/"),
    ("submit", "Submit", f"{GH_BASE}/submit/"),
]

NAV_CSS = '''
/* explicit overrides throughout -- some host pages already style bare
   nav{} / nav a{} for their own in-page section nav, so .sm-nav can't
   rely on defaults not leaking in from those lower-specificity rules */
.sm-nav{position:sticky;top:0;z-index:100;background:var(--ink);display:flex;flex-direction:row;
  align-items:center;flex-wrap:wrap;gap:clamp(10px,2vw,28px);padding:10px clamp(14px,4vw,32px);
  font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12.5px;
  border:none;box-shadow:0 2px 8px rgba(0,0,0,.18);}
.sm-nav .sm-brand{color:var(--paper);font-weight:600;letter-spacing:.04em;margin-right:auto;white-space:nowrap;}
.sm-nav a{color:color-mix(in srgb, var(--paper) 65%, transparent);text-decoration:none;letter-spacing:.02em;
  padding:3px 0;border-bottom:2px solid transparent;white-space:nowrap;font-size:12.5px;}
.sm-nav a:hover{color:var(--paper);}
.sm-nav a.active{color:var(--accent);border-bottom-color:var(--accent);}
'''


def render_nav(active_key):
    parts = []
    for key, label, url in PAGES:
        cls = ' class="active"' if key == active_key else ""
        parts.append(f'<a href="{url}" target="_blank" rel="noopener"{cls}>{label}</a>')
    links = "\n    ".join(parts)
    return f'''<nav class="sm-nav">
    <span class="sm-brand">SPM261.01 SOCCER LEAGUE</span>
    {links}
  </nav>'''
