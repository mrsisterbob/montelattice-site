"""The only list of tool logos the site may show.

Every entry is a service job-outreach-engine actually CALLS, with the engine file and a string
from its call site as evidence (tests/test_engine_tools.py re-checks that against a real engine
checkout, so an entry that stops being true fails the suite). Names that merely appear in the
engine (search links it only hands to Kevin, sender and domain filter lists, profile URLs in data)
are left out on purpose and tests/test_engine_tools.py fails if one is added.

Marks are single-path monochrome SVG path data taken from Simple Icons (CC0 data; the marks
themselves belong to their owners), version 16.35.0, fetched from
https://cdn.jsdelivr.net/npm/simple-icons@16.35.0/icons/<slug>.svg. They carry no fill: the page draws
them with currentColor so they theme with the site tokens. Where Simple Icons has no icon the
entry's mark is None and the page shows the name as text. Nothing here was drawn from memory.

Verified against the engine 2026-10-12 (call sites: Gmail main.py drafts and threads, Telegram
sendMessage, Gemini generateContent, Google Sheets via Code.gs and CRM_WEBHOOK_URL, the three ATS
board APIs, Remotive, JSearch via JSEARCH_URL, the three contact-finder APIs, Typst compile).
"""
from __future__ import annotations

from typing import NamedTuple

SIMPLE_ICONS_VERSION = "16.35.0"


class Tool(NamedTuple):
    name: str
    engine_file: str  # relative to the job-outreach-engine checkout
    needle: str  # a string that occurs at the call site in engine_file
    svg_path: str | None  # path data, 24x24 viewBox; None = no licensed mark, show the name
    svg_viewbox: str = "0 0 24 24"


TOOLS: tuple[Tool, ...] = (
    Tool(
        name='Gmail',
        engine_file='main.py',
        needle='gmail.googleapis.com',
        svg_path=(  # simple-icons/gmail
            'M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z'
        ),
    ),
    Tool(
        name='Telegram',
        engine_file='main.py',
        needle='api.telegram.org',
        svg_path=(  # simple-icons/telegram
            'M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z'
        ),
    ),
    Tool(
        name='Google Gemini',
        engine_file='main.py',
        needle='generativelanguage.googleapis.com',
        svg_path=(  # simple-icons/googlegemini
            'M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81'
        ),
    ),
    Tool(
        name='Google Sheets',
        engine_file='Code.gs',
        needle='SpreadsheetApp',
        svg_path=(  # simple-icons/googlesheets
            'M11.318 12.545H7.91v-1.909h3.41v1.91zM14.728 0v6h6l-6-6zm1.363 10.636h-3.41v1.91h3.41v-1.91zm0 3.273h-3.41v1.91h3.41v-1.91zM20.727 6.5v15.864c0 .904-.732 1.636-1.636 1.636H4.909a1.636 1.636 0 0 1-1.636-1.636V1.636C3.273.732 4.005 0 4.909 0h9.318v6.5h6.5zm-3.273 2.773H6.545v7.909h10.91v-7.91zm-6.136 4.636H7.91v1.91h3.41v-1.91z'
        ),
    ),
    Tool(
        name='Greenhouse',
        engine_file='main.py',
        needle='boards-api.greenhouse.io',
        svg_path=(  # simple-icons/greenhouse
            'M16.279 7.13c0 1.16-.49 2.185-1.293 2.987-.891.891-2.184 1.114-2.184 1.872 0 1.025 1.65.713 3.231 2.295 1.048 1.047 1.694 2.43 1.694 4.034C17.727 21.482 15.187 24 12 24c-3.187 0-5.727-2.518-5.727-5.68 0-1.607.646-2.989 1.694-4.036 1.582-1.582 3.23-1.27 3.23-2.295 0-.758-1.292-.98-2.183-1.872-.802-.802-1.293-1.827-1.293-3.03 0-2.318 1.895-4.19 4.212-4.19.446 0 .847.067 1.181.067.602 0 .914-.268.914-.691 0-.245-.112-.557-.112-.891 0-.758.647-1.382 1.427-1.382s1.404.646 1.404 1.426c0 .825-.647 1.204-1.137 1.382-.401.134-.713.312-.713.713 0 .758 1.382 1.493 1.382 3.61zm-.446 11.19c0-2.206-1.627-3.99-3.833-3.99-2.206 0-3.833 1.784-3.833 3.99 0 2.184 1.627 3.989 3.833 3.989 2.206 0 3.833-1.808 3.833-3.99zM14.518 7.086c0-1.404-1.136-2.562-2.518-2.562S9.482 5.682 9.482 7.086 10.618 9.65 12 9.65s2.518-1.159 2.518-2.563z'
        ),
    ),
    Tool(
        name='Lever',
        engine_file='main.py',
        needle='api.lever.co',
        svg_path=None,
    ),
    Tool(
        name='Ashby',
        engine_file='main.py',
        needle='api.ashbyhq.com',
        svg_path=None,
    ),
    Tool(
        name='Remotive',
        engine_file='main.py',
        needle='remotive.com/api/remote-jobs',
        svg_path=None,
    ),
    Tool(
        name='JSearch',
        engine_file='main.py',
        needle='api.openwebninja.com/jsearch/search',
        svg_path=None,
    ),
    Tool(
        name='Hunter',
        engine_file='pipeline_utils.py',
        needle='api.hunter.io',
        svg_path=None,
    ),
    Tool(
        name='Prospeo',
        engine_file='pipeline_utils.py',
        needle='api.prospeo.io',
        svg_path=None,
    ),
    Tool(
        name='GetProspect',
        engine_file='pipeline_utils.py',
        needle='api.getprospect.com',
        svg_path=None,
    ),
    Tool(
        name='Typst',
        engine_file='resume_engine.py',
        needle='typst.compile(',
        svg_path=(  # simple-icons/typst
            'M12.654 17.846c0 1.114.16 1.861.479 2.242.32.381.901.572 1.743.572.872 0 1.99-.44 3.356-1.319l.871 1.45C16.547 22.931 14.44 24 12.785 24c-1.656 0-2.964-.395-3.922-1.187-.959-.82-1.438-2.256-1.438-4.307V6.989H5.246l-.349-1.626 2.528-.791V2.418L12.654 0v4.835l5.142-.395-.48 2.857-4.662-.176v10.725Z'
        ),
    ),
)
