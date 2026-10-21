// Build: typst compile resume/kevin-miller-resume.typ static/kevin-miller-resume.pdf
// Every bullet is copied unchanged from job-outreach-engine's evidence_bank.json
// (tests/test_resume_pdf.py checks this). Colours are the site's tokens (static/css/tokens.css).
#let navy = rgb("#22254A")
#let brass = rgb("#E0B978")
#let brass-text = rgb("#7E5A1C")
#let on-navy = rgb("#EEF2F9")
#let ink = rgb("#1D1A1F")
#let muted = rgb("#5F5A54")

#set document(title: "Kevin Miller - Resume", author: "Kevin Miller")
#set page(paper: "us-letter", margin: (top: 0pt, bottom: 0.4in, x: 0pt))
#set text(font: "Calibri", size: 10.5pt, fill: ink)
#set par(leading: 0.55em, spacing: 0.55em)
#set list(marker: [•], indent: 0.1in, body-indent: 0.07in, spacing: 0.45em)

#let side = 0.6in

#let heading-rule(title) = block(above: 1.1em, below: 0.55em, width: 100%)[
  #text(font: "Georgia", size: 10pt, weight: "bold", fill: brass-text, tracking: 0.12em)[#upper(title)]
  #v(-0.15em)
  #line(length: 100%, stroke: 0.75pt + brass)
]

#let role(title, company, place, dates) = block(above: 0.85em, below: 0.4em, width: 100%, breakable: false)[
  #grid(columns: (1fr, auto),
    [*#title*, #company #text(fill: muted)[· #place]],
    text(fill: muted)[#dates])
]

// Header band
#block(fill: navy, width: 100%, inset: (x: side, top: 0.4in, bottom: 0.3in), stroke: (bottom: 2pt + brass))[
  #text(font: "Georgia", size: 28pt, fill: on-navy, tracking: 0.03em)[Kevin Miller]
  #v(0.2em)
  #text(size: 10.5pt, fill: on-navy)[
    kjmiller406\@gmail.com · 248-709-6326 · Detroit, MI · #link("https://montelattice.com")[montelattice.com] ·
    #link("https://www.linkedin.com/in/kevin-miller-7386a6252/")[LinkedIn] ·
    #link("https://github.com/mrsisterbob")[GitHub]
  ]
]

#pad(x: side)[
  #heading-rule("Summary")
  I design Salesforce queues and DocuSign workflows that cut advisor packet review from 60 minutes to 20.

  #heading-rule("Experience")
  #role("Wealth Operations Specialist Intern", "Signal Advisors", "Detroit, MI", "05/2026 – 08/2026")
  - Built DocuSign and Salesforce packet workflows for 150+ advisors, cutting packet review from 60 minutes to 20.
  - Resolved a Salesforce queue collision between the trading and service desks, preventing 10 critical SLA breaches.
  - Standardized custodial transfer checklists, cutting rejected paperwork resubmissions by 40%.
  - Audited onboarding paperwork for 2,000+ accounts to verify investment advisory agreements and risk profiles under SEC rules.
  - Established escalation paths for custodial account transfers, cutting request turnaround time by 25%.
  - Trained incoming operations analysts on DocuSign and Salesforce, shortening onboarding ramp from 3 weeks to 10 days.
  - Managed Salesforce ticketing queues and engaged directly with custodians to resolve urgent advisor requests within 1 to 2 hour SLAs.

  #role("Operations Consultant", "40 Acres", "Detroit, MI", "04/2026 – 05/2026")
  - Planned the approach to SEC Form D and Regulation Crowdfunding filings and explained what each one covers.
  - Set up compliance intake checkpoints and suitability reviews for incoming platform investors.
  - Read property documentation and title records and explained which custodial fields applied to each offering.

  #role("Financial Planning Intern", "Northwestern Mutual", "Grand Rapids, MI", "05/2025 – 08/2025")
  - Prepared financial planning proposals and led 15+ prospecting reviews under RIA suitability guidelines.
  - Tracked onboarding paperwork exceptions and cleared documentation hold-ups with partner firms.

  #role("Total Rewards Finance Intern", "ABC Technologies", "Southfield, MI", "05/2024 – 08/2024")
  - Reconciled employee 401(k) and healthcare deduction variances across 500+ accounts in bSwift and Excel.
  - Built structured audit checklists to cross-reference multi-plant payroll data, catching recurring 401(k) deduction errors across 70+ manufacturing facilities.

  #heading-rule("Technical Projects")
  #role("Document Automation Pipeline & Custom CRM", [#link("https://github.com/mrsisterbob/job-outreach-engine")[Source]], "Detroit, MI", "07/2026 – Present")
  - Built a Python pipeline that pulls postings from job-board REST API data feeds, normalizes each into a common record format and loads it into a SQLite database and a Google Sheets CRM.
  - Wrote 1,100+ lines of Google Apps Script that run a Google Sheets CRM, auto-populating and routing every record as the pipeline updates it.
  - Scheduled nightly Python jobs that check every tracked posting for a dead link and queue each day's follow-up emails.

  #role("Crypto Breakout Alert and Real Time Paper Trading Engine", [#link("https://github.com/mrsisterbob/crypto-trading-engine")[Source]], "Detroit, MI", "04/2026 – 08/2026")
  - Built a concurrent Python backend on SQLite in WAL mode with explicit write locks to process live exchange data and manage virtual portfolios.
  - Engineered a real time WebSocket reconciliation feed and historical backtester for automated breakout detection and simulated execution.

  #heading-rule("Education")
  #grid(columns: (1fr, auto),
    [*Hope College* · B.A. Business (Finance), B.A. Political Science · #text(fill: muted)[Holland, MI]],
    text(fill: muted)[08/2022 – 05/2026])

  #heading-rule("Certificates")
  Series 65 (Expected Q4 2026) · Securities Industry Essentials (SIE) · Bloomberg Market Concepts

  #heading-rule("Skills")
  Python · SQL · Salesforce · DocuSign · Excel · Power BI · Schwab Advisor Center · Fidelity Wealthscape · HubSpot CRM · Flask · SQLite · Google Apps Script
]
