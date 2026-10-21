// Build: typst compile resume/kevin-miller-resume.typ static/kevin-miller-resume.pdf
// A frozen render of job-outreach-engine resume_engine.render_typst_markup("Kevin Miller", "e", None, "conservative"),
// the same layout as the résumés Kevin sends. Re-freeze it by rendering again; do not hand-edit the text.
// Bullets come from the engine banks (evidence_bank.json, resume_bullets_bank.json); tests/test_resume_pdf.py checks them.
#set document(
  title: "Kevin Miller - Resume",
  author: "Kevin Miller",
  date: auto,
  keywords: ("Business Operations", "Salesforce", "HubSpot CRM", "Process Automation", "Ticket Routing", "Python")
)

// Tuned 1-Page Layout Spacing
#set page(paper: "us-letter", margin: (x: 0.65in, top: 0.40in, bottom: 0.40in))
#set text(font: "Liberation Sans", size: 9.4pt, fill: rgb("#111827"))
#set par(justify: false, leading: 0.52em, spacing: 0.52em)
#set list(spacing: 0.44em, indent: 0em)
#show heading: set block(above: 0.44em, below: 0.18em)

// --- HEADER ---
#align(center)[
  #text(size: 18pt, weight: "bold", fill: rgb("#000000"))[Kevin Miller] \
  #text(size: 10pt, weight: "medium", fill: rgb("#4B5563"))[Business Operations & CRM Systems] \
  #v(2pt)
  #text(size: 9.4pt, fill: rgb("#1F2937"))[kjmiller406\@gmail.com • 248-709-6326 • Detroit, MI • #link("https://montelattice.com")[montelattice.com] • #link("https://www.linkedin.com/in/kevin-miller-7386a6252/")[LinkedIn] • #link("https://github.com/mrsisterbob")[GitHub]]
]

#v(6.5pt)
#line(length: 100%, stroke: 0.7pt + rgb("#CCCCCC"))
#v(3.8pt)

// --- SUMMARY ---
#text(size: 8.5pt, weight: "bold", tracking: 1.1pt, fill: rgb("#374151"))[SUMMARY]
#v(2pt)
I have experience in Salesforce queues and DocuSign workflows for advisors, and I am looking for business operations and CRM systems roles.

#v(6.5pt)
#line(length: 100%, stroke: 0.5pt + rgb("#E5E7EB"))
#v(3.8pt)

// --- PROFESSIONAL EXPERIENCE ---
#text(size: 8.5pt, weight: "bold", tracking: 1.1pt, fill: rgb("#374151"))[PROFESSIONAL EXPERIENCE]
#v(2pt)
*Wealth Operations Specialist Intern* | Signal Advisors #h(1fr) Detroit, MI | 05/2026 -- 08/2026
- Set up automated DocuSign workflows in Salesforce for 150+ advisors, cutting packet review from 60 to 20 minutes.
- Fixed a Salesforce queue collision between trading and service desks, preventing 10 critical SLA breaches.
- Mapped account workflows from initial Salesforce submission through execution in Orion Eclipse.
- Managed Salesforce ticketing queues and worked with custodians to resolve advisor requests within 1 to 2 hour SLAs.
#v(6.5pt)
*Operations Consultant* | 40 Acres #h(1fr) Detroit, MI | 04/2026 -- 05/2026
- Planned the approach to SEC Form D and Regulation Crowdfunding filings and explained what each one covers.
- Set up compliance intake checkpoints and suitability reviews for incoming platform investors.
- Read property documentation and title records and explained which custodial fields applied to each offering.
#v(6.5pt)
*Financial Planning Intern* | Northwestern Mutual #h(1fr) Grand Rapids, MI | 05/2025 -- 08/2025
- Prepared financial planning proposals and led 15+ prospecting reviews under RIA suitability guidelines.
- Verified client financial profiles with institutional custodians to speed up account transfers.
- Tracked onboarding paperwork exceptions and cleared documentation hold-ups with partner firms.
#v(6.5pt)
*Total Rewards Finance Intern* | ABC Technologies #h(1fr) Southfield, MI | 05/2024 -- 08/2024
- Reconciled employee 401(k) and healthcare deduction variances across 500+ accounts in bSwift and Excel.
- Built structured audit checklists to cross-reference multi-plant payroll data, catching recurring 401(k) deduction errors across 70+ manufacturing facilities.
- Prepared and maintained supporting schedules for variance analysis and recurring internal financial reports.

#v(6.5pt)
#line(length: 100%, stroke: 0.5pt + rgb("#E5E7EB"))
#v(3.8pt)

// --- TECHNICAL PROJECTS ---
#text(size: 8.5pt, weight: "bold", tracking: 1.1pt, fill: rgb("#374151"))[TECHNICAL PROJECTS]
#v(2pt)
*Document Automation Pipeline & Custom CRM* | #link("https://github.com/mrsisterbob/job-outreach-engine")[Source] #h(1fr) Detroit, MI | 07/2026 -- Present
- Built a Python pipeline that pulls postings from job-board REST API data feeds, normalizes each into a common record format and loads it into a SQLite database and a Google Sheets CRM.
- Scored each posting with a deterministic Gemini layer; a Telegram command drafts the PDF and Gmail follow-up.
- Wrote 1,100+ lines of Google Apps Script that run a Google Sheets CRM, auto-populating and routing every record as the pipeline updates it.
- Scheduled nightly Python jobs that check every tracked posting for a dead link and queue each day's follow-up emails.
- Built first-party visitor analytics for montelattice.com: each pageview is bot-filtered, given a daily hashed visitor ID, tagged with its referrer host and stored in SQLite, then summarized in a daily Telegram report.
- Uses SQL through Python's sqlite3 module to read and write a SQLite job database.
#v(6.0pt)
*Market Breakout Alert and Real Time Paper Trading Engine* | #link("https://github.com/mrsisterbob/crypto-trading-engine")[Source] #h(1fr) Detroit, MI | 04/2026 -- 08/2026
- Built a concurrent Python backend on SQLite in WAL mode with explicit write locks to process live exchange data and manage virtual portfolios.
- Engineered a real time WebSocket reconciliation feed and historical backtester for automated breakout detection and simulated execution.

#v(6.5pt)
#line(length: 100%, stroke: 0.5pt + rgb("#E5E7EB"))
#v(3.8pt)

// --- EDUCATION & CREDENTIALS ---
#text(size: 8.5pt, weight: "bold", tracking: 1.1pt, fill: rgb("#374151"))[EDUCATION & CREDENTIALS]
#v(2pt)
*B.A. Business (Finance), B.A. Political Science*, Hope College #h(1fr) Holland, MI | 08/2022 -- 05/2026
#v(3.0pt)
*Certificates & Licenses:* Series 65 (Expected Q4 2026), Securities Industry Essentials (SIE), Schwab Limited Power of Attorney, Bloomberg Market Concepts
#v(3.0pt)
*Leadership & Activities:* Secretary, Student Political Organization • Member, Economic Club of Grand Rapids • Varsity Cross Country & Track (2 years) • Taught peers to host their own websites at no cost

#v(6.5pt)
#line(length: 100%, stroke: 0.5pt + rgb("#E5E7EB"))
#v(3.8pt)

// --- SKILLS & SYSTEMS ---
#text(size: 8.5pt, weight: "bold", tracking: 1.1pt, fill: rgb("#374151"))[SKILLS & SYSTEMS]
#v(2pt)
*Operations & Workflow:* Queue Routing Optimization, SLA Escalation Controls, CRM Pipeline Management. \
*Systems & Tools:* Salesforce, HubSpot CRM, DocuSign, Schwab Advisor Center, Fidelity Wealthscape, Python.