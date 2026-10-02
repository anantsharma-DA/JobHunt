# JobHunt

<img src="static/logo.svg" alt="JobHunt logo: a magnifier with an orange compass needle" width="260">

**A free job-search app for India that runs on your own Windows computer.**
It searches LinkedIn, Indeed, Naukri and the careers sites of companies you choose, puts every result in one list
with filters, and opens the real application page in one click. Optional AI features help you tailor your resume,
write messages and prepare for interviews.

- **Free to use:** JobHunt itself costs nothing and needs no account or login. Searching for jobs needs no key at all.
  The optional AI features use your own key from an AI service; OpenRouter, NVIDIA and Google Gemini have free options
  (see [What needs a key](#what-needs-a-key)).
- **Private:** runs only on your computer. Your jobs, searches, resume and settings stay there.
- **India-focused:** search any Indian city, all of India, or remote jobs open to India.

> JobHunt finds jobs and opens their application pages. You read each job and submit the application yourself;
> nothing is ever applied to automatically.

## Contents

- [What needs a key](#what-needs-a-key)
- [Features](#features)
- [Requirements](#requirements)
- [Install and start](#install-and-start)
- [How to use](#how-to-use)
- [Tailor your resume with AI](#tailor-your-resume-with-ai)
- [Interview questions and practice](#interview-questions-and-practice)
- [Insights: applications, salary, skill gaps](#insights-applications-salary-skill-gaps)
- [Get your API keys, step by step](#get-your-api-keys-step-by-step)
- [Recommended settings so sites don't block you](#recommended-settings-so-sites-dont-block-you)
- [If a site blocks JobHunt](#if-a-site-blocks-jobhunt)
- [Your data, privacy and security](#your-data-privacy-and-security)
- [Moving or updating JobHunt](#moving-or-updating-jobhunt)
- [Troubleshooting](#troubleshooting)
- [Project files](#project-files)
- [Disclaimer](#disclaimer)

## What needs a key

| What you want to do | What it needs | Cost |
|---|---|---|
| Search LinkedIn, Indeed, Naukri and company careers sites; filters, warnings, the Applied board, reminders, Insights | Nothing | Free |
| AI features: tailor your resume, cover notes, referral messages, practice feedback, drafted interview answers, **Check with AI**, reading an uploaded resume | One AI key: OpenRouter, NVIDIA, Google Gemini, OpenAI or Claude | Free with OpenRouter, NVIDIA or Gemini; OpenAI and Claude are paid per use |
| Find interview questions on the web | A Tavily key, or a Gemini key that allows Google Search | Free (Tavily: 1,000 credits a month) |

Keys are pasted on the **Settings** tab. How to get each one: [Get your API keys, step by step](#get-your-api-keys-step-by-step).

## Features

**Search**
- LinkedIn, Indeed, Naukri and company careers sites in one search. The sites are searched at the same time, with
  live progress for each and a **Cancel search** button.
- About 270 job titles in 18 fields (data, BI, software, cloud, logistics, finance, HR, sales and more), each with a
  list of matching skills to tick. You can also type your own titles and skills.
- **Posted within** anything from 5 minutes to 30 days.
- **Cities:** about 100 Indian cities plus Remote, any other city you type, or all of India.
- **Company careers sites:** job feeds on Greenhouse, Lever, Ashby, SmartRecruiters and Workday are read directly.
  Other careers pages are checked for those platforms. If none is found, the company's jobs are searched on Indeed
  and/or LinkedIn. Add companies one by one or import a CSV/Excel list, tag them with roles, and filter the list.

**Results**
- One list without duplicates: a job found on several sites appears once, with a link to each site.
- **Match %** for every job, based on your job titles and skills.
- **Applicant counts:** from LinkedIn automatically, and from Naukri with the **Update Applicants** button (Indeed and
  company sites publish no counts).
- **Company ratings** (AmbitionBox ratings shown by Naukri), also shown on that company's jobs from other sites.
- **Filters:** job title searched, text, minimum match, minimum salary, maximum applicants, minimum company rating,
  experience, date posted, work mode, job type, city, source, and include/exclude companies.
- **Sort** by best match, newest, highest salary, fewest applicants or company name.

**Warnings (worked out on your computer, no key needed)**
- **Scam warnings:** a red "Likely scam" or amber "Check this advert" badge when an advert asks for a fee or deposit,
  wants you on WhatsApp/Telegram only, uses a Gmail recruiter, promises a job with no interview or easy money, or pays
  far above the experience it asks. **Check with AI** (needs an AI key) gives a second opinion on any job.
- **Possible ghost jobs:** roles that stay up for months or keep being reposted, often without real hiring behind them.
- **Notice period:** "Immediate joiner" or "Notice up to 30 days" from the advert, and a filter for jobs that fit your
  own notice period.
- **Applying twice:** an "Already applied" badge, and a confirm box before you apply to the same role again.

**Tracking**
- **Jobs**, **Saved Jobs**, **Applied** and **Hidden** tabs with counts. **Apply** opens the application page and moves
  the job to Applied. Every move can be undone.
- **Applied board:** a column for each stage (Applied, Followed up, Interview, Offer, Rejected, No reply). Each
  application keeps its dates, interview time, notes, the recruiter's details and its stage history.
- **Reminders:** "Follow up" a week after you apply (you choose how many days), "Still no reply" after you follow up,
  and interview reminders a day and 2 hours before, shown in a **Due now** list and as **Windows notifications**.
- **Daily auto-search:** at a time and on days you choose, JobHunt searches your saved titles and cities for jobs posted
  in the last day and tells you "12 new jobs, 4 strong matches". Optionally Windows starts JobHunt for it.

**Applying (AI key needed)**
- **Tailor resume** rewrites your resume for one job using the advert's own words, and checks that the AI invented
  nothing: made-up numbers, skills or employers are flagged or removed.
- An **ATS check** scores the result and shows which of the job's keywords are missing.
- A one-page, one-column, ATS-friendly **PDF with clickable links**, in three designs (**Modern**, **Classic**,
  **Compact**). Promotions at one company are shown as separate titles.
- **Score targets:** set an ATS score and a "doesn't sound like AI" target, and tailoring keeps improving the resume
  within the rounds you allow. **Stop** ends it at once without touching your earlier version.
- Your standard answers (notice period, CTC, experience) and an optional cover note are ready to copy, next to an
  **Apply** button that opens the job's application page.
- **Referral helper:** a short referral request and a note to the recruiter, written from your saved details only.
- Works with **OpenRouter, NVIDIA, Gemini, OpenAI or Claude**, with automatic fallback between them.

**Interview preparation**
- **Frequently Asked Questions** on each job and the **Interview Questions** tab: questions found on the web (Tavily or
  Gemini key), each with links to where it appeared; questions reported on 2 or more sites are marked verified.
- Answers come from the source page when it has one (the whole answer, not a cut-off preview); otherwise your AI
  service drafts one, clearly labelled.
- Everything found is kept on the **Saved Questions** tab and builds up: searching again adds only new questions.
- **Practise (typed mock interview, AI key needed):** questions in a random order; feedback after each answer or for
  all of them at the end; scores out of 10 and a stronger answer built only from your resume. **Old Practise
  Sessions** shows every earlier session's scores so you can see yourself improve.

**Insights (worked out on your computer, no key needed)**
- **Your applications:** applications per week, the Applied → reply → interview → offer funnel, and which sites,
  match levels and resumes get replies.
- **Salary:** what jobs like yours pay by job title, city and experience, and a **CTC to monthly in-hand calculator**
  for the new tax regime (FY 2026-27).
- **Skill gaps:** the skills your matching jobs ask for that your resume doesn't mention, with free learning links.

**Look**
- Every page is in the sidebar on the left, grouped as **Find** (Jobs, Saved Jobs, Applied, Hidden), **Prepare**
  (Resume, Interview Questions, Saved Questions), **Research** (Companies, Insights) and **App** (Settings). On a
  narrow window or a phone, press **Menu** at the top.
- Royal blue (#1F3A93) with the logo's orange for highlights; Newsreader for titles, IBM Plex Sans for text and IBM Plex
  Mono for numbers. The fonts are part of JobHunt, so it looks the same offline.
- **Dark mode:** the button at the bottom of the sidebar. JobHunt remembers the choice.

**Security** (details in [Your data, privacy and security](#your-data-privacy-and-security))
- Answers only on your own computer, and refuses requests started by other websites, other host names and other
  computers.
- API keys are encrypted with Windows' own protection (DPAPI), or can be given as environment variables; the page never
  receives them.
- Rate and size limits, strict input checking, uploads checked by their real content, pages it opens checked against
  local-network addresses, error messages without internals, and tested, vulnerability-scanned package versions.

## Requirements

- **Windows 10 or 11**
- **Internet connection**
- **Microsoft Edge**: it comes with Windows. Naukri searches use it.
- **Python 3.12 or newer**: if it's missing (or older), `run.bat` installs Python 3.14 for you.

## Install and start

1. **Download:** on this GitHub page click **Code → Download ZIP**. Right-click the ZIP → **Extract All**.
   Use the extracted folder, not the files inside the ZIP.
2. **Double-click `run.bat`** in the extracted folder.
   - If Windows shows a security warning for a downloaded file, choose **Run** (or **More info → Run anyway**).
   - If your computer has no Python 3.12 or newer, `run.bat` installs Python 3.14 for your Windows user with winget,
     which comes with Windows 10 and 11. No administrator rights are needed. If that isn't possible, it asks you to
     install Python from https://www.python.org/downloads/ with **"Add python.exe to PATH"** ticked, then run
     `run.bat` again.
   - The first time, it installs everything JobHunt needs, in the exact versions listed in `constraints.txt`. This
     takes a few minutes and needs internet.
   - Your browser then opens JobHunt at http://localhost:8000.
3. **Keep the black `run.bat` window open** while you use JobHunt. Closing it stops the app.

**Next time:** double-click `run.bat`. It starts in a few seconds.

## How to use

### 1. Search for jobs

On the **Jobs** tab:

1. **Job titles:** click the box, tick one or more titles, or type your own and press Enter.
2. **Skills / keywords:** your chosen titles' skills are listed first. Tick them one by one, use
   **Tick all for my titles**, or type your own. Skills are used for the match %.
3. **Cities** (optional): pick cities and/or **Remote**.
   - None picked: all of India is searched.
   - 1–3 picked: each site searches each city separately (plus a remote-only search if Remote is picked). This is
     faster and brings fewer unwanted jobs.
   - 4 or more: all of India is searched once, then filtered to your cities.
   - Jobs listed only in other cities are skipped. Jobs whose listing names no city are kept.
4. **Posted within:** drag the slider (5 minutes to 30 days).
5. **Search on:** tick the sites to search.
6. Press **Search** (bottom right). A loading screen shows each site's progress. **Cancel search** stops it and keeps
   the jobs found so far.

How exact **Posted within** is depends on the site: LinkedIn matches it exactly, Indeed to the hour, and Naukri only
by day (1, 3, 7, 15 or 30 days), so short windows on Naukri can include jobs posted earlier the same day.

### 2. Review the results

Each job card shows the title, company, company rating, location, salary, applicant count, work mode, experience,
when it was posted, the match %, and which of your skills the job mentions.

- **Match %:** 40% for how well the job title matches the title you searched, 60% for how many of your skills appear
  in the job. Changing your skills re-scores all jobs instantly.
- **Details** shows the job description.
- **Filters** (left side) apply instantly. Jobs that don't state a salary, experience, applicant count or rating are
  always shown, so filters never hide jobs just because a detail is missing. **Reset** clears all filters.
- **Job title searched:** every job remembers which search title found it. Tick titles to see only those jobs.

### Warnings on job cards

Each badge lists its reasons when you point at it, and again in **Details**. They are signs, not proof.

| Badge | When it appears |
|---|---|
| **⚠ Likely scam** (red) | A strong sign: the advert asks you to pay a fee or deposit (registration, training, kit, "refundable"), promises easy money (earn ₹X per day, like videos, rate products, typing tasks), or pays far above the experience asked; or two clear signs together. |
| **⚠ Check this advert** (amber) | One clear sign: a recruiter with a Gmail/Yahoo/Outlook address, "apply on WhatsApp/Telegram", "no interview / direct joining", or unusually high pay for 0-1 years. A short advert or a missing company name only adds weight; on its own it never triggers a warning. |
| **Possible ghost job** | The same role at the same company has been open for 45+ days, reposted 3+ times (its posting date jumps forward by a week or more), or is still open after 30 days with 200+ applicants. JobHunt remembers roles across searches (even after you clear the Jobs tab, unless you also tick **Repost history** in Clear data), so this gets better over time. |
| **Immediate joiner** / **Notice up to N days** | The advert says how soon you must join. It turns amber when that is shorter than the notice period on your Resume tab. |
| **Already applied · date** | You applied to this role at this company on another card (reposts often appear as a new job). |

- **Check with AI** (in Details, AI key needed) sends only the advert, never your details, to your AI service for a
  second opinion. Its answer replaces the rule badge and is marked "(AI)".
- **Filters → Warnings:** **Hide likely scams** (red ones only), **Hide possible ghost jobs** and **Only jobs that fit
  my notice period** (needs your notice period on the Resume tab). All are off by default.
- **Settings → Warnings:** switch either warning off, or change the 45 days and 3 reposts.

### 3. Apply and keep track

- **Apply** opens the real application page in a new tab and moves the job to **Applied**. On a role you already
  applied to, it first asks "You applied to … on … Apply again?".
- **Save** moves a job to **Saved Jobs**, and **Hide** moves it to **Hidden**.
- Every move shows an **Undo** message, and each tab has buttons to move jobs back.
- Before searching for a different kind of job, use **Settings → Clear data** with only **Jobs** ticked. It removes
  jobs you haven't acted on; Saved Jobs, Applied and Hidden jobs stay.

### The Applied board and reminders

The **Applied** tab is a board with a column for each stage: **Applied**, **Followed up**, **Interview**, **Offer**,
**Rejected** and **No reply**. The filters on the left work on it too.

- **Move a job** to another stage with the drop-down on its card. The day of every move is kept.
- **Tracker** on a card opens its panel: stage, the day you applied, the next follow-up date, the interview date and
  time, notes, and the recruiter's name, email and phone. It also shows the stage history, and has buttons to open the
  job page, tailor your resume, see its Frequently Asked Questions, or mark it **Not applied**.
- **Due now** (at the top of the board) lists what needs doing today, and the Applied tab shows how many ("2 due"):
  - **Follow up:** 7 days after you apply (change the number in Settings), or on the date you set in the panel.
    **Mark followed up** moves the job on.
  - **Still no reply:** the same number of days after you follow up. **Follow up again** sets the next reminder;
    **Mark No reply** closes it.
  - **Interview:** a day before and 2 hours before the time you enter.
- **Windows notifications:** while JobHunt is running, each reminder also pops up once in the corner of your screen.
  Clicking it opens JobHunt. They show under "Windows PowerShell" (JobHunt uses Windows' own notifications, so nothing
  extra is installed). Turn them off in **Settings → Reminders and daily auto-search**, or in Windows under
  **Settings → System → Notifications**.
- Jobs you applied to before JobHunt kept dates show "Applied (date unknown)" until you set the date in the panel.

### Daily auto-search

**Settings → Reminders and daily auto-search → Daily auto-search** searches for you every day (or on the days you
tick), at the time you choose:

- It uses the job titles, cities and sites saved on the Jobs tab, and only looks for jobs posted in the last day.
- When it finishes you get a notification such as "12 new jobs, 4 strong matches (70%+). Top: …". **Strong match
  from** sets that percentage. The result also shows in Settings.
- If JobHunt was busy at that time, it runs as soon as it can within the next hour; it runs at most once a day.
- **Run the daily search now** runs it straight away.

**Start JobHunt automatically at this time (Windows Task Scheduler):** without it, the daily search only happens while
JobHunt is open. With it ticked, Windows starts JobHunt at that time on those days in a minimised window; JobHunt
searches, shows the notification and closes itself. If JobHunt is already open, the open copy searches instead.
- The task is called **JobHunt Daily Search**, runs only for your Windows user, needs no administrator rights, and runs
  only while you're signed in to Windows.
- Changing the time or days and pressing **Save** updates it. Unticking it, or switching the daily search off,
  removes it. If you move the JobHunt folder, tick it and **Save** again.

### 4. See how many people applied

Fewer applicants usually means a better chance. Sort by **Fewest applicants**, or use the **Maximum applicants**
filter.

- **LinkedIn** counts are saved automatically during the search. LinkedIn never shows an exact number above 200
  ("Over 200 applicants").
- **Naukri** doesn't include counts in its search results. Press **Update Applicants** (next to Search; pointing at it
  shows "Indeed & Company Sites not Included.").
  - It opens each Naukri job in your **Jobs** and **Saved Jobs** tabs, one after another, in an Edge window placed
    off-screen, and saves its applicant count. This takes about 4–5 seconds per job.
  - Jobs whose count was checked in the last day are skipped, so pressing it again soon is quick.
  - You can keep using the page while it runs. **Stop** keeps the counts read so far. **Search** is unavailable until
    it finishes or you stop it.
  - **Details** on a single Naukri job also fetches that job's count.
  - **Tip:** hide the jobs you're not interested in first, so the update is faster and less likely to be blocked.
- **Indeed** and company careers sites don't publish applicant counts.

Counts are a snapshot from when they were read; hover over a count to see when.

### 5. Add company careers sites

On the **Companies** tab:

1. Enter the **company name**, its **careers page link** if you have it, and optionally its **roles** (for example
   *Data Analyst, Business Analyst*), then **Add company**.
   - To find a supported link, open any job on the company's careers page. If the address contains
     `greenhouse.io`, `lever.co`, `ashbyhq.com`, `smartrecruiters.com` or `myworkdayjobs.com`, paste it. JobHunt reads
     that job feed directly.
   - For any other careers link, JobHunt looks inside the page for one of those platforms.
   - If none is found, or there is no link, JobHunt searches your job titles plus the company name on Indeed and/or
     LinkedIn (see Settings) and keeps only that company's jobs.
2. **Add many at once:** upload a CSV or Excel (.xlsx) file with the columns **Company name** and **Careers link** (the
   link can be empty), and optionally **Role** (several roles separated by `;`). **Download a template** gives an
   example. Up to 5 MB and 2,000 companies per file. Companies already in your list are skipped.
3. **Filters** above the list work like the Job titles box: pick or type **Company** names (typing "bank" matches every
   bank), **Read via** platforms, **Roles** and **In search** (ticked or not). Within one filter any choice matches;
   across filters all must. The line under the filters says how many are shown and how many are in search.
4. **In search** turns a company on or off. **All** in its heading ticks or unticks every company shown: all of them,
   or only the filtered ones while a filter is on.
5. **Role** on each row shows its tags; **Add** / **Edit** changes them (separate roles with commas, Enter to save, Esc
   to cancel). **Test** shows how many matching jobs it finds right now.
6. On the **Jobs** tab, tick **Company sites** to include the companies that are in search. The search line shows
   "Company sites N jobs (M new) · K companies", where K is how many are ticked **In search**.

Only jobs located in India, or remote jobs open to India, are kept, and only jobs whose title matches one of your job
titles. "0 jobs" usually means none of the ticked companies posted such a job within **Posted within**: widen it, or
tick more companies.

### 6. Settings

| Setting | What it does | Default |
|---|---|---|
| Results to fetch per job title, per site | How many jobs each site returns for each job title (and each city) | 100 |
| Pause between company-site requests | Wait between requests to company job feeds | 1 second |
| Companies without a supported careers link are searched on | Indeed only, LinkedIn only, or both | Indeed only |
| Warnings | Scam warnings and possible ghost jobs on/off, and the ghost-job limits (days open, reposts) | both on; 45 days, 3 reposts |
| Reminders and daily auto-search | Days before a follow-up reminder; Windows notifications on/off; the daily auto-search (on/off, time, days, strong-match %) and whether Windows starts JobHunt for it | 7 days; notifications on; auto-search off (09:00, Mon–Fri, 70%) |
| AI for resume tailoring | A key and models for each AI service, in the order they are tried | none, until you add a key |
| Tailoring targets | ATS score and "doesn't sound like AI" targets, how many rounds to try, and the default resume design | off (0), 3 rounds, Modern |
| Web search for interview questions | Your Tavily key, and how much of the free allowance is used | none, until you add a key |
| Minimum questions per search | Separate numbers for Frequently Asked Questions and the Interview Questions tab; fewer found shows "Only found N questions" | 10 and 10 (0 = off) |
| Clear data | Deletes data page by page (see below) | nothing ticked |

The **Good to know** panel on the right of the Settings tab sums up how searching, warnings, AI keys, reminders and
your data work. Recommended values are in [Recommended settings](#recommended-settings-so-sites-dont-block-you).

### Clear data

**Settings → Clear data** has a box for each page, each showing how much it holds:

| Page | What you can tick |
|---|---|
| Jobs | **Jobs** (results you haven't acted on), and **Repost history** (what JobHunt remembers about roles for the possible ghost job warnings) |
| Saved Jobs, Applied, Hidden | The jobs on that tab (Applied also holds each job's tracker details) |
| Resume | **Your resume details**, and **Tailored resumes and their PDF files** |
| Companies | Your company careers sites |
| Saved Questions | **Profile Wise Saved Questions**, **Saved Frequently Asked Questions** and **Practice history** (your typed answers, scores and old practice sessions), separately |
| Interview Questions, Insights | Nothing to tick: they store nothing of their own. |

- Tick one or more, then press **Clear data**. A confirm box lists exactly what will go, with counts, before anything is
  deleted. Empty ones can't be ticked.
- Clearing **Jobs**, **Saved Jobs**, **Applied** or **Hidden** also deletes what belongs to those jobs: their tracker
  details, referral messages, and tailored resumes with their PDFs.
- If one of those PDFs is open in another program, nothing is deleted; close it and press **Clear data** again. Jobs
  can't be cleared while a search or applicant update is running.
- **It can't be undone.** To keep a copy, copy the `data` folder first.

## Tailor your resume with AI

JobHunt can rewrite your resume for one job at a time and get everything ready for the application. It needs one AI
key (see [What needs a key](#what-needs-a-key)).

**JobHunt never applies for you.** LinkedIn, Indeed and Naukri all forbid automated applying and restrict accounts
that do it, so JobHunt stops at the Submit button: it prepares the resume and the answers, and you send the
application yourself.

### 1. Connect one or more AI services (Settings tab)

Each service has its own card: paste that service's key, press **Fetch models** and tick a few models. You can set up
as many services as you like.

**They are tried from the top down.** If the first service is busy, out of credit or down, JobHunt moves to the next
model in that card, then to the next service, until one answers. Use the **↑ ↓** arrows to change the order, and the
**Use** tick to switch a service off without losing its key. A card turns green and says "ready" when it has both a
key and a ticked model. **Test the order** shows which service answers first.

| Service | Key from | Cost |
|---|---|---|
| **OpenRouter** | https://openrouter.ai/keys | Only its free models are listed. About 20 requests a minute. |
| **NVIDIA NIM** | https://build.nvidia.com/ | Free developer credits (about 1,000 calls), 40 a minute, no card. |
| **Google Gemini** | https://aistudio.google.com/apikey | Free tier, but few requests a day on the bigger models. |
| **OpenAI** | https://platform.openai.com/api-keys | Paid per use; no free tier. |
| **Claude (Anthropic)** | https://console.anthropic.com/settings/keys | Paid per use, no free tier. Claude Opus 5.5 costs $4 per million tokens read and $20 per million written: usually a few cents per tailored resume, more when several rounds are needed. |

Each key is stored encrypted on this computer, is never shown again (only a hint like `sk-or-…7c2d`), and is sent only
to its own service. A sensible free setup is OpenRouter first with NVIDIA behind it, so tailoring keeps working when
one of them is busy.

**Claude** is called through Anthropic's official Python SDK. Its model list comes live from Anthropic, so new models
appear without a JobHunt update. Answers that must be JSON use Claude's structured outputs, so they always match what
JobHunt expects. On Claude Fable 5.1, Claude Opus 5.5, Claude Opus 5 and Claude Sonnet 5.5, Anthropic's server-side
**refusal fallback** is switched on: if a safety filter declines a request, Anthropic reruns it on its recommended
fallback model instead of failing.

### 2. Fill in the Resume tab

Upload a resume you already have (PDF, Markdown or text) or paste its text, and the AI fills in the fields for you to
correct. You can also type everything yourself: contact details, links, skills, jobs with bullet points, projects,
education, certificates, and the answers forms ask for (notice period, current and expected CTC, total experience).

An HTML resume exported from a design tool usually has no readable text inside it, so use the PDF version.

**Promotions:** if you held several titles at one company, open that job and use **Positions at this company**: add
each title with its own From and To dates, newest first. The PDF shows the company once, then each title on its own
line with its dates, which is how ATS software expects promotions. Leave it empty if you had one title.

### 3. Press "Tailor resume" on a job

- The AI rewrites your summary, reorders your skills and rewrites your bullet points using the job advert's own
  words, then JobHunt checks the result against your saved details.
- **Anything it made up is flagged:** an invented number, a skill only the advert mentioned, or an employer you never
  listed. Invented employers are removed outright. You edit the wording, or press **Use flagged wording anyway** if it
  is genuinely true and simply missing from your details.
- **The ATS check** shows a score out of 100: how many of the advert's keywords your resume now uses, plus checks for
  contact details, standard headings, bullet length, resume length, working links and keyword stuffing. After the PDF
  is made, it also reads the PDF back to confirm the text survives. It is an estimate from the advert's wording, not
  an official score from any company's system.
- **Make PDF** writes a one-column, ATS-friendly PDF to `data\resumes` with your portfolio and project links
  clickable. Pick its look in **Design**, next to the button (your default is set on the Settings tab):

  | Design | Look |
  |---|---|
  | **Modern** (default) | Name and headings in navy with thin lines, company in bold with dates on the right, titles in italics |
  | **Classic** | Black and grey only, Georgia serif font, centred name, small-capital headings; prints perfectly in black and white |
  | **Compact** | Bold capital name over a thick navy line, headings with a navy bar, tighter spacing to fit more on one page |

  **All three are equally ATS-safe** and give the same ATS score: one column read top to bottom, standard section
  headings, real text in normal fonts, contact details in the page itself, and no tables, text boxes, icons, skill
  bars or photos. JobHunt checks this for every PDF by reading it back the way an ATS does.
- **Always exactly one full page:** the AI is told to write about 450-550 words. JobHunt then picks the largest text
  size and spacing (9.5pt to 11.5pt) that fill the page. If it still runs over at 9.5pt, the AI cuts the bullets that
  matter least for the job; every job stays listed. Nothing is printed until you have checked the shorter wording and
  pressed **Make PDF** again. A two-page PDF is never saved.
- **Tailor again** asks for a fresh version at any time.
- **Finding them later:** the **Resume** tab lists every tailored resume (job, file name, date, ATS score) with
  **Open PDF**, **Download**, **Edit** and **Delete** (asks first, then removes the saved wording and the PDF file).

### Score targets (Settings → Tailoring targets)

Leave both at 0 for one quick pass. With targets set, **Tailor resume** works in rounds:

1. **Round 1:** every model you ticked, on every service, writes its own version at the same time. Versions with
   invented claims always rank below honest ones.
2. **Rounds 2 and on:** the best version's model gets specific feedback (advert keywords your details support but it
   didn't use yet, phrases that sound generated) and rewrites it. The better version is kept each time.
3. It stops as soon as both targets are met, or after the number of rounds you set (default 3), keeping the best
   version either way. Round 1 can take a few minutes with many free models.
4. **Stop** ends it at once, at any point. Nothing from a stopped run is kept: the resume tailored earlier for the same
   job (if there is one) stays exactly as it was and is shown again.

- **ATS target:** before starting, JobHunt works out the best score your details can honestly reach. If the target is
  higher, it tells you why and lets you tick the missing skills you really have. Ticked skills are added to your
  details under "Also skilled in"; nothing is added without you.
- **"Doesn't sound like AI" target:** the average of a built-in style check (stock phrases like "spearheaded", lines
  all the same length, repeated openings) and one fixed AI model acting as a reviewer. It is a style estimate, not a
  real AI detector; even commercial detectors are unreliable.

### 4. Apply

The same window gets the rest ready: your answers with **Copy** buttons, and an optional short **cover note** written
only from your saved details (just the note itself, ready to paste). Then press **Apply** (in that window, or on the job
card): it opens the real application page and moves the job to the Applied tab. Upload the PDF there yourself.

**What is sent to the AI service:** your resume details and that job's title, company and description. Nothing else,
and nothing at all until you press a button.

### Ask for a referral

**Referral** (on job cards, in the Tracker panel and in the **Ready to apply** box of the tailor window) opens a window
with:

- **Find people at {company} on LinkedIn:** opens LinkedIn's own people search in your browser. JobHunt reads nothing
  from LinkedIn.
- **Write with AI:** a **referral request** for someone who works there, and a **note to the recruiter**, written only
  from your saved details. Anything not in your details is listed under the message. Edit them, then **Copy** and send
  them yourself; JobHunt never sends anything. They are saved with the job.

## Interview questions and practice

**Frequently Asked Questions** on a job card finds questions candidates reported being asked by that company for that
role. The **Interview Questions** tab does the same for any job titles you pick from the list. Both need a Tavily key
or a Gemini key that allows Google Search (see [What needs a key](#what-needs-a-key)).

- **How they are found:** **Tavily** (1,000 free credits a month) finds up to 8 pages, and JobHunt reads the questions
  (and any answers under them) straight from the pages' text, so none can be made up. Only when the pages have too few
  questions written out are your AI models asked to find more, and each one must still appear on a page. A company
  search looks for candidates' "interview experience" write-ups, since those name the questions actually asked.
- **Gemini search, if your key allows it:** Gemini can search Google itself and say which page supports each question.
  Google allows this for free only on older keys (Gemini 2.5) or on keys with billing switched on. JobHunt tries it
  first; on keys where Google refuses, it uses Tavily for the rest of the day. The Settings tab shows which is in use.
- **Reading the pages:** when Tavily sends only a preview of a page, JobHunt reads the page with Tavily Extract, or
  opens it itself like a browser would (this is how AmbitionBox and Glassdoor get read). A search usually uses 2
  credits, and up to 4 when Tavily's stronger reader is needed.
- **Only real questions with their own answers:** questions a forum writer asked about themself ("What are the tools I
  used…?"), half-quoted fragments, and text that is really the next question or page furniture ("Answered by", "Read
  more") are left out. An answer ends where the next numbered question starts.
- **Whole answers:** when a site shows only a preview ("… and loading...."), JobHunt opens the question's own page (the
  link beside it, such as "Read more") to read the whole answer. If no site has it, your AI service drafts one, labelled
  **AI-drafted: check before using**.
- **Relevance:** in a company search, pages that don't mention the company are left out. Pages about the exact role come
  first; a near role only tops up a short list.
- **Saved, and built up over time:** every question found is kept on the **Saved Questions** tab (**Profile Wise Saved
  Questions** for job-title searches, **Saved Frequently Asked Questions** for jobs). Searching again uses different
  search wording, skips pages already read, and adds only new questions.
- **Verified:** questions reported on 2 or more different sites get a "verified" badge and are listed first.
- **Minimum per search (Settings tab):** when a search finds fewer new questions than your minimum, JobHunt says so.
  It doesn't search again by itself, so no extra credits are used. Set 0 to turn the message off.
- **Free limits:** JobHunt counts both services and never goes past their free limits. Opening saved questions costs
  nothing.
- **Sites like Glassdoor and AmbitionBox:** when Tavily can't read a page from them, JobHunt opens that one page (and,
  for a cut-off answer, that question's own page) the way your browser would. It does not crawl these sites. Their terms
  may not allow automated reading, so using this is your own responsibility (see the Disclaimer).

### Practise (typed mock interview)

**Practise** is on each group on the **Saved Questions** tab and in the **Frequently Asked Questions** window. It needs
an AI key.

1. Choose how you want feedback: **After each question**, or **At the end** (answer every question first with
   **Save & next**, then **Get feedback for all** scores them all at once). The questions come in a new random order
   every time.
2. Type your answer the way you'd say it. Your AI service scores it out of 10 (does it answer the question, is it
   specific, is it structured, is it the right length to say aloud) and lists what worked and what to improve.
3. **A stronger answer, from your resume:** built only from your saved details. Anything in it that isn't in your
   details is listed, so you never learn to say something untrue. The answer reported on the web (if any) is under
   **Answer reported on the web**; the AI treats it only as a hint.
4. **Next question** or **Skip**. At the end you see the average of your latest scores.
5. Each question shows your earlier scores (for example 3 → 6 → 8). **Retry weak ones** goes through the questions
   whose latest score is below 6.
6. **Old Practise Sessions** (next to **Practise** on the Saved Questions tab) lists every earlier session for that job,
   newest first: when, how many answers, the feedback mode, the average score and how it changed from the session
   before (▲/▼). Open one to see each answer you typed, its score and its feedback.

What is sent to the AI service: the question, your typed answer, the reported answer, the job title (and company) and
your resume details.

## Insights: applications, salary, skill gaps

The **Insights** tab has three sections; the buttons at its top switch between them. Everything is worked out on your
computer from your own jobs, applications and resume details; nothing is sent anywhere.

### Your applications

- **Applications, reply rate, interviews and offers** at the top. A reply is an interview, an offer or a rejection:
  anything that shows the company answered. Set the stage on the **Applied** board.
- **Applications per week** for the last 12 weeks.
- **From applying to an offer:** how many applications got a reply, an interview and an offer.
- **What gets replies:** the reply rate by the site you applied on, by match % (70%+, 40–69%, below 40%), by tailored
  resume or not, and by resume design. With only a few applications these numbers move a lot, so read them as hints.

### Salary

- **What jobs like yours pay:** the lower quarter, median and upper quarter of the pay shown by the jobs JobHunt has
  found (in LPA), with the job title searched, city and experience as filters. At least 3 jobs with pay are needed.
  Your expected CTC from the Resume tab is marked on the range. Most adverts don't show pay, so this is a guide.
- **CTC to monthly in-hand pay**, using the **new tax regime for FY 2026-27**:
  - ₹75,000 standard deduction; no tax up to ₹12 lakh of taxable income (section 87A rebate), with marginal relief
    just above it; then 5% to 30% slabs (₹4 lakh steps); surcharge above ₹50 lakh with marginal relief; 4% cess.
  - Type the CTC in lakhs (9) or in rupees (900000); the page says how it read it.
  - Match the options to your offer letter: **variable pay %**, **basic %** of fixed pay (default 50%), **your PF**
    (12% of full basic, or capped at ₹1,800 a month), and whether **employer PF** and **gratuity** (4.81% of basic)
    are inside the CTC.
  - **Professional tax:** picking your state fills in its usual yearly amount; edit it to match your payslip.
  - It's an estimate: allowances, meal cards, NPS or other deductions on your payslip can change it.

### Skill gaps

- Looks at jobs with a **40%+ match** found in the **last 30 days** (Hidden jobs left out) and lists the skills they ask
  for that your Resume tab doesn't mention, most asked first.
- **YouTube** and **Free courses** links search for free material on each skill.
- Tick the skills you really have and press **I have these: add to my Resume tab**.

## Get your API keys, step by step

Searching for jobs needs no key. Keys are only for the AI features and for interview questions (see
[What needs a key](#what-needs-a-key)). Sites change their menus now and then, so a button may be named slightly
differently.

**Where to paste them:** the **Settings** tab. Each AI service has its own card: paste the key into its box, press
**Fetch models**, tick a few models and press **Save AI settings**. The Tavily key goes in **Web search for interview
questions** → **Save key**.

### OpenRouter (free models)

1. Go to https://openrouter.ai and **Sign in** (Google, GitHub or email).
2. Open https://openrouter.ai/keys and press **Create Key**.
3. Name it `JobHunt`. Set a **credit limit** of `0` if you only want free models, so the key can never spend money.
4. Press **Create** and copy the key (it starts with `sk-or-v1-`). It is shown only once.
5. In JobHunt: **Settings → OpenRouter card**, paste it, **Fetch models**, tick 3–5 models ending in `:free`.

### NVIDIA NIM (free developer credits)

1. Go to https://build.nvidia.com and **Sign in**, or create a free NVIDIA account (no card needed).
2. Open any model page and press **Get API Key**, then **Generate Key**.
3. Copy the key (it starts with `nvapi-`).
4. In JobHunt: **Settings → NVIDIA NIM card**, paste it, **Fetch models**, and tick a few. If one says "not
   available", untick it and pick another.

### Google Gemini (free tier)

1. Go to https://aistudio.google.com/apikey and sign in with your Google account.
2. Press **Create API key**. If asked, pick or create a Google Cloud project (any name).
3. Copy the key (it usually starts with `AIza` or `AQ.`).
4. In JobHunt: **Settings → Google Gemini card**, paste it, **Fetch models**, and tick the Flash-Lite models.

### OpenAI / ChatGPT (paid)

1. Go to https://platform.openai.com and sign in (a ChatGPT subscription does **not** include API use).
2. Under **Settings → Billing**, add a payment method or credit, and under **Limits** set a monthly budget.
3. Open https://platform.openai.com/api-keys → **Create new secret key**. Name it `JobHunt`; you may choose
   **Restricted** permissions and allow only model requests.
4. Copy the key (it starts with `sk-`). It is shown only once.
5. In JobHunt: **Settings → OpenAI card**, paste it, **Fetch models**, and tick one or two.

### Claude / Anthropic (paid)

1. Go to https://console.anthropic.com and sign up or sign in.
2. Under **Billing**, add credit. Under **Limits**, set a monthly spend limit.
3. Open https://console.anthropic.com/settings/keys → **Create Key**, name it `JobHunt`.
4. Copy the key (it starts with `sk-ant-`). It is shown only once.
5. In JobHunt: **Settings → Claude card**, paste it, **Fetch models**, and tick `Claude Opus 5.5`
   (`claude-opus-5-5`, suggested first) and perhaps `Claude Sonnet 5.5` as a cheaper backup.

### Tavily (interview questions; 1,000 free credits a month)

1. Go to https://app.tavily.com and sign up (Google, GitHub or email); the free plan needs no card.
2. Your key is shown on the dashboard under **API Keys** (it starts with `tvly-`). Copy it.
3. In JobHunt: **Settings → Web search for interview questions**, paste it and press **Save key**.

JobHunt counts the credits it uses and stops at the free 1,000 a month. Tavily's terms allow one free account per
person.

### Keeping your keys safe

- **One key per app:** create a separate key named `JobHunt` for each service, so you can cancel it without
  affecting anything else.
- **Least privilege:** use free models or a spending limit (OpenRouter credit limit 0, OpenAI budget, Anthropic spend
  limit), and restricted permissions where the service offers them. Never use an organisation-admin key.
- **Never share a key:** don't paste it into chats, emails, screenshots, documents or GitHub. JobHunt never puts keys
  in the page, in logs or in its files for GitHub.
- **If a key may have been exposed:** open that service's key page, **delete (revoke)** the key, create a new one,
  and paste the new key into JobHunt. Revoking stops the old key working at once.
- **Environment variables instead of saving (optional):** keys set as Windows environment variables take priority and
  are never written to disk. Open **Start → "Edit environment variables for your account"** → **New**, and add any of:
  `JOBHUNT_OPENROUTER_KEY`, `JOBHUNT_NVIDIA_KEY`, `JOBHUNT_GEMINI_KEY`, `JOBHUNT_OPENAI_KEY`, `JOBHUNT_CLAUDE_KEY`,
  `JOBHUNT_TAVILY_KEY`. Then close and restart `run.bat`. The Settings tab shows "(from the … environment variable)"
  next to such a key.

## Recommended settings so sites don't block you

JobHunt reads the same public job pages anyone can open, but job sites limit how many automated requests they accept
from one internet connection in a short time. Go past that and the site blocks the connection for a while. JobHunt
already pauses between pages; these settings and habits keep you well under the limits.

| Setting | Recommended |
|---|---|
| **Results to fetch per job title, per site** | Count *job titles × cities* (Remote counts as a city; no cities = 1): **1–2 → 100**, **3–4 → 50**, **5 or more → 30**. |
| **Posted within** | **1 day** for daily use. With 1 day, 50 results per title is enough and searches are much faster. |
| **Pause between company-site requests** | Keep **1 second**. Use 0.5 only if you have many Workday or SmartRecruiters companies. Don't set it to 0. |
| **Companies without a supported careers link are searched on** | **Indeed only**, especially with a long company list. Each company is a separate search for every job title, and on LinkedIn that quickly uses up your limit and blocks your main LinkedIn search too. |

A rough guide for LinkedIn: keep *job titles × cities × results per title* at about **200 or less** per search.

**Habits:** search once or twice a day with Posted within = 1 day; leave 30 minutes or more between large searches
that include LinkedIn; untick LinkedIn for extra searches with many titles or cities; hide unwanted jobs before
**Update Applicants**; run JobHunt on one computer at a time per internet connection.

## If a site blocks JobHunt

A block is **temporary** and applies to your **internet connection**, not to you:

- JobHunt never logs in, so your LinkedIn, Indeed or Naukri **accounts are not affected**.
- **Other devices on the same Wi-Fi** share the connection, so they may be blocked for the same time.
- When one site blocks, the other sites in the same search keep going, and jobs found so far are kept.

| Site | What JobHunt shows | When it clears and what to do |
|---|---|---|
| **LinkedIn** | "blocked for now (too many requests). Try again in 30–60 minutes" | Usually within 30–60 minutes, sometimes a few hours. JobHunt stops asking LinkedIn for the rest of that search. Wait, then search again with fewer titles, cities or results. |
| **Naukri** | "Naukri denied access for now. Try again later" | Wait at least an hour. Then search with fewer titles, and hide unwanted jobs before **Update Applicants**. |
| **Indeed** | "the site refused the request (403). Try again later" or "blocked for now (too many requests)…" | Rare. Wait an hour and try again. |
| **Company sites** | A message such as "HTTP 429 from …" next to the company | That company's job platform is limiting requests. Raise **Pause between company-site requests** to 2 seconds and try later. |

## Your data, privacy and security

- **Where your data is:** everything (jobs, statuses, applications with their notes and recruiter contacts,
  companies, settings, saved interview questions, practice sessions, your resume details and your API keys) is in
  `data\jobhunt.db` inside the JobHunt folder, and tailored resumes are in `data\resumes`. Delete the `data` folder to
  erase it all.
- **What leaves your computer:** your job titles, cities and posted-within choice go to LinkedIn, Indeed and Naukri.
  Company names go to Indeed/LinkedIn, and careers links you add are opened to find their job platform. The AI service
  you choose receives, only when you press a button: your resume details and the job's advert (tailoring, cover
  notes, referral messages), only the advert (**Check with AI**), your uploaded resume (reading it), or the question,
  your typed answer and your resume details (**Practise**). Gemini or Tavily receive the job title and company name
  for interview questions. **Insights** send nothing anywhere. There is no tracking and no analytics. Naukri pages open
  in a fresh, temporary Edge profile with no cookies or saved logins.

### How JobHunt is protected

**Who can use it.** JobHunt is a single-user app with no login, by design: it answers only on `127.0.0.1` (this
computer), so anyone who can use it is already signed in to your Windows account. On top of that:
- Requests from any other computer are refused, even if someone changed `--host` in `run.bat`. (Still, don't change
  it, and don't open port 8000 to your network.)
- Only the host names `localhost` and `127.0.0.1` are accepted, which blocks "DNS rebinding" tricks.
- **Other websites open in your browser can't use it:** any API request a different website starts is refused (checked
  with the browser's `Sec-Fetch-Site` label), reads included; every change must also carry JobHunt's own header and come
  from JobHunt's own page (checked by Origin). Other websites can't read JobHunt's data.
- Lock your computer when you step away; anyone using your Windows account can use JobHunt.

**API keys.**
- Keys are **encrypted with Windows' Data Protection API (DPAPI)**, tied to your Windows login. Someone who copies
  `data\jobhunt.db` to another computer or Windows account can't read them.
- Keys can instead come from **environment variables**, which are never written to disk.
- Keys are never sent to the page (it only gets a masked hint), never written to logs, and each is sent only to its
  own service. The `.gitignore` keeps the `data` folder, databases and `.env` files out of git.
- Deleted or replaced data (an old key, a removed resume) is overwritten in the database file, not left behind.

**Rate limits, size limits and busy limits.** A request over a limit gets "Too many requests. Please wait N
seconds…":

| What | Limit |
|---|---|
| Changing API keys | 10 a minute |
| AI actions (tailor, PDF, cover note, referral messages, practice feedback, resume import, fetching models, testing) | 20 a minute |
| Web actions (interview searches, job searches, the daily auto-search and its Windows task, applicant updates, adding/testing/importing companies) | 20 a minute |
| Everything else | 600 a minute |
| Slow jobs (AI and web actions) running at the same time | 4 |
| Size of one request | 1 MB (uploads: 5 MB) |

**Input checking.** Everything the page sends is checked on the server before JobHunt acts on it: its type, its length
or range, its format and its allowed values. Unknown fields are refused rather than ignored. The reply says what was
wrong without repeating what was sent.

**File uploads.** Your old resume (PDF, HTML, Markdown, text) and company lists (CSV, Excel) are treated as untrusted:
- The content must match the name: a real PDF for `.pdf`, a real Excel workbook for `.xlsx`, plain text for `.csv`,
  `.txt`, `.md` and `.html`. Programs, pictures, zip files or renamed files are refused.
- 5 MB per file. Excel files are also limited once unpacked (no "zip bombs"), workbooks with macros are refused, and
  XML attacks are blocked (`defusedxml`).
- Uploads are read in memory only: never saved to disk, never opened by another program, never run.
- Tailored PDFs get safe file names and are only served from the `data\resumes` folder.

**Web pages JobHunt opens** (careers pages, interview-question pages): addresses on your own computer or local network
are never opened. The address is checked before the request and again at the moment of connecting (so a site can't
switch its address in between), redirects are checked too, and at most 2 MB is read. HTTPS certificate checks stay on.

**AI.** Job adverts, web pages and uploaded files can contain text written to steer an AI ("ignore the rules above…").
Every AI request tells the model to treat such text as data, never as instructions; everything the AI writes about you
is checked against your saved details, it is shown only as text (never run), and the AI can't take any action in
JobHunt.

**Error messages.** Anything unexpected shows only **"Something went wrong. Please try again later."**, never a stack
trace, file path or a library's message; the full detail goes only to the black `run.bat` window.

**Software supply chain.** `run.bat` installs the exact package versions in `constraints.txt`, which were tested and
scanned for known vulnerabilities (`pip-audit`, last on 2026-10-02: none found). When that file changes, `run.bat`
installs the new versions once by itself.

**Also:** a strict Content Security Policy lets only JobHunt's own script run; all text from websites and AI is escaped
before it is shown; links are used only if they are normal `http://` or `https://` addresses; Windows notifications and
the scheduled task are created without a command shell, so a job title or a setting can't run anything.

## Moving or updating JobHunt

- **To another computer:** copy the whole JobHunt folder and double-click `run.bat` there. It notices the copied setup
  was made on another computer and rebuilds it once. The `data` folder brings your jobs and settings with it. **API
  keys don't move:** they are encrypted for your Windows account, so paste them again on the Settings tab.
- **To a newer version:** download and extract the new version, then copy the `data` folder from your old JobHunt
  folder into the new one to keep your jobs, companies and settings.

## Troubleshooting

| Problem | What to do |
|---|---|
| "Setup failed" in the `run.bat` window | Read the messages above it; most often the internet dropped during installation. Delete the `.venv` folder and run `run.bat` again. |
| "JobHunt needs Python 3.12 or newer, and it could not be installed automatically" | Install Python from https://www.python.org/downloads/, tick **"Add python.exe to PATH"**, then run `run.bat` again. |
| The browser didn't open | Open http://localhost:8000 yourself while the `run.bat` window is open. |
| The page doesn't load, or an error mentions port 8000 | Another JobHunt window is probably open. Close all `run.bat` windows and start it again. |
| "Microsoft Edge was not found" | Install Microsoft Edge; Naukri needs it. The other sites still work. |
| An Edge window appears in the taskbar | That's the off-screen window JobHunt uses for Naukri. Don't close it during a Naukri search or applicant update. |
| No jobs found | Widen **Posted within**, pick fewer cities, and press **Reset** on the filters. |
| "Company sites 0 jobs" | Only companies ticked **In search** are searched, and only jobs matching your job titles in India within **Posted within** are kept. Widen Posted within or tick more companies. |
| A site keeps failing even after waiting | Job sites change their pages. Update the site readers with the commands below, then restart `run.bat`. |
| A company's **Test** finds 0 jobs | It may have no open jobs matching your titles in India right now, or its careers site isn't supported (then it's searched on Indeed/LinkedIn by name). |
| "No AI service could answer…" | Free models are often busy or out of credit. Tick a few models on the Settings tab so JobHunt can fall back to the next one, or try again later. |
| "…did not accept your API key" | The key is for a different service, or has been revoked. Paste a fresh key and press **Test the order**. |
| Tailoring says to fill in the Resume tab | Your resume details need at least your name and one job or project with a bullet point. |
| "Request from another website refused" | A link or page from another site tried to use JobHunt. Open JobHunt from its own tab at http://localhost:8000. |
| "Too many requests. Please wait N seconds…" | A rate limit was reached. Wait that long and try again. |
| "JobHunt is busy with other searches or AI requests" | Four slow jobs are already running. Wait for one to finish. |
| "Some of the information sent isn't valid (…)" | A value was outside what JobHunt accepts (too long, wrong characters). Correct the named field. |
| No Windows notifications appear | Check **Show Windows notifications** in Settings, that JobHunt is running, and that Windows allows notifications from "Windows PowerShell" and Do not disturb is off. |
| The daily auto-search didn't run | Without **Start JobHunt automatically**, JobHunt must be open at that time. With it, you must be signed in to Windows. |
| "Something went wrong. Please try again later." | Something unexpected happened. Try again; if it repeats, the black `run.bat` window shows the details. |

Update the site readers (run these in the JobHunt folder):

```
.venv\Scripts\python -m pip install -U --no-deps python-jobspy
.venv\Scripts\python -m pip install -U playwright
```

`python-jobspy` is installed with `--no-deps` on purpose: its published version pins an old numpy that can't install on
new Python versions. Its real dependencies are in `requirements.txt`. Updating packages yourself leaves the tested
versions in `constraints.txt`; to go back to them, delete the `.venv` folder and run `run.bat` again.

## Project files

```
JobHunt/
├── run.bat                  Installs everything (including Python if needed) and starts the app
├── requirements.txt         Python packages run.bat installs
├── constraints.txt          The exact, tested and vulnerability-scanned version of every package
├── app/
│   ├── main.py              Web server, API, input checking and error messages
│   ├── guard.py             Security limits: this computer only, rate, size and busy limits
│   ├── secret_store.py      Encrypts API keys (Windows DPAPI); keys from environment variables
│   ├── errors.py            Plain error messages; details only in the run.bat window
│   ├── search.py            Runs a search across the chosen sites
│   ├── job_warnings.py      Scam, ghost-job and notice-period warnings (rules, no network)
│   ├── tracker.py           Applied board: stages, dates, notes, and the reminders that are due
│   ├── notify.py            Windows notifications
│   ├── scheduler.py         Reminders and the daily auto-search in the background; the Windows task
│   ├── insights.py          Insights: application statistics, salary ranges, CTC to in-hand, skill gaps
│   ├── outreach.py          Referral request and recruiter note
│   ├── practice.py          Typed mock interview: feedback, every attempt and practice sessions
│   ├── applicant_update.py  Update Applicants (Naukri applicant counts)
│   ├── db.py                Local SQLite database
│   ├── normalize.py         Cleans salaries, experience, locations, links
│   ├── matching.py          Match % from job titles and skills
│   ├── cities.py            Indian cities and states
│   ├── company_import.py    CSV/Excel company lists
│   ├── ai.py                Talks to OpenRouter, NVIDIA, Gemini and OpenAI, with fallback between services
│   ├── claude_ai.py         Claude, through Anthropic's official SDK
│   ├── resume.py            Your resume details, tailoring, fact-checking, ATS report, cover note
│   ├── resume_pdf.py        Prints the tailored resume to a one-page, ATS-safe PDF in one of three designs
│   ├── tailor_run.py        Tailoring in rounds until the score targets are met; Stop
│   ├── interview.py         Interview questions from the web (Tavily, Gemini with Google Search), saved and built up
│   └── sources/
│       ├── boards.py        LinkedIn and Indeed (via JobSpy)
│       ├── naukri.py        Naukri (via an off-screen Microsoft Edge window)
│       ├── ats.py           Greenhouse, Lever, Ashby, SmartRecruiters, Workday feeds; opening web pages safely
│       └── company_boards.py Company-name searches on Indeed/LinkedIn
└── static/
    ├── index.html, app.js, styles.css   The page, the Jobs tab and the Companies tab
    ├── resume.js            Resume tab, AI settings, Tailor resume window, interview and saved questions
    ├── tracker.js           Applied board, tracker panel, reminders and auto-search settings
    ├── insights.js          Insights tab, Referral window, Practise window, Old Practise Sessions
    ├── logo.svg, logo-mark.svg   The JobHunt logo (the mark is also the browser-tab icon)
    ├── fonts/               Newsreader, IBM Plex Sans, IBM Plex Mono (SIL Open Font License, see OFL-*.txt)
    └── job_catalog.json     Job titles and skills (editable)
```

Your own data (`data/`) and the installed Python environment (`.venv/`) are created on your computer and are never
part of the download.

Built with [FastAPI](https://fastapi.tiangolo.com/), [JobSpy](https://github.com/cullenwatson/JobSpy),
[Playwright](https://playwright.dev/python/) with Microsoft Edge, SQLite, openpyxl, the
[Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) and plain JavaScript. Fonts:
[Newsreader](https://github.com/productiontype/Newsreader) and [IBM Plex](https://github.com/IBM/plex), both under the
SIL Open Font License.

## Disclaimer

JobHunt is an independent personal project. It is not affiliated with, endorsed by or connected to LinkedIn, Indeed,
Naukri, AmbitionBox, any AI or search service it works with, or any company it lists. It reads publicly visible job
listings, at a modest pace, to help one person search for jobs. Use it responsibly and in line with each site's terms
of use; you are responsible for how you use it. Job details, salaries, applicant counts and ratings come from those
sites and can be incomplete or out of date, so always check the original listing before applying.

### Legal disclaimer and limitation of liability

By downloading, installing, copying, modifying or using JobHunt (the "Software"), you confirm that you have read,
understood and agree to the terms below. If you do not agree, do not download or use the Software.

1. **No affiliation.** The Software is an independent project. It is not affiliated with, authorised, sponsored,
   endorsed or approved by LinkedIn, Indeed, Naukri, AmbitionBox, Glassdoor, Greenhouse, Lever, Ashby, SmartRecruiters,
   Workday, OpenRouter, NVIDIA, Google, OpenAI, Anthropic, Tavily, Microsoft, or any other company, employer, careers
   site, job platform or AI service, including any company or website a user adds to the Software. All product names,
   company names, trademarks and logos belong to their respective owners and are used only to describe which websites
   and services the Software can work with.

2. **Provided "as is".** The Software is provided "AS IS" and "AS AVAILABLE", without warranty of any kind, express
   or implied, including but not limited to warranties of merchantability, fitness for a particular purpose,
   accuracy, reliability, non-infringement, or uninterrupted or error-free operation. No warranty is given that any
   job listing, salary, applicant count, rating, interview question, answer or other information shown by the Software
   is accurate, complete, current or lawful.

3. **AI-generated content.** Tailored resumes, cover notes, referral messages, drafted interview answers, practice
   feedback, scam opinions and other text written by an AI service can be wrong, incomplete or misleading, even after
   the Software's checks. You must read and correct everything before you use or send it. You are solely responsible
   for what you submit to an employer, and for any cost charged by the AI or search services you choose to use with
   your own keys.

4. **You are solely responsible.** You alone are responsible and liable for your use of the Software and its
   consequences, including:
   - complying with all laws and regulations that apply to you, including computer-misuse, data-protection,
     privacy and intellectual-property laws;
   - complying with the terms of use, terms of service and access policies of every website and service you access
     with the Software;
   - any account suspension, access restriction, IP address block, claim, notice, complaint, demand, lawsuit,
     prosecution or other legal or non-legal action brought by any website, company, authority or other third party;
   - any decision you make, or application you submit, based on information shown by the Software;
   - the security of your own computer, network, data and API keys.

5. **Limitation of liability.** To the maximum extent permitted by applicable law, in no event shall the author and
   creator of the Software, or any contributor or copyright holder, be liable to you or to any third party for any
   claim, damages, loss or other liability of any kind, whether direct, indirect, incidental, special,
   consequential, exemplary or punitive, including but not limited to loss of data, profits, income, employment
   opportunities, business or reputation, account suspension or blocking, AI or search service charges, legal costs,
   fines or penalties, whether in contract, tort (including negligence), statute or otherwise, arising from or in
   connection with the Software, its use, misuse or inability to use, or these terms, even if advised of the
   possibility of such damages.

6. **Indemnity.** You agree to indemnify, defend and hold harmless the author and creator of the Software, and any
   contributor, from and against all claims, liabilities, damages, losses, costs and expenses (including reasonable
   legal fees) arising from or related to your use or misuse of the Software, your breach of these terms, or your
   violation of any law, any website's or service's terms, or the rights of any third party.

7. **Third-party websites, services and content.** The Software reads information that websites make publicly visible,
   opens their pages in your browser, and sends requests to the AI and search services you choose. The author does not
   own, control, host, verify or endorse any third-party website, service, job listing or content, and is not
   responsible for them or for how they handle what you send them. Any application you submit, and any relationship
   that follows, is solely between you and the employer or website concerned.

8. **No advice.** Nothing in the Software or its documentation is legal, career, financial, tax or other professional
   advice. Salary and in-hand pay figures are estimates.

9. **Copies and modified versions.** Anyone who copies, modifies or redistributes the Software is solely responsible
   for their copy or version and its use. The author is not liable for any modified or redistributed version.

10. **Acceptance and severability.** Downloading or using the Software means you accept these terms. If any part of
    these terms is found to be invalid or unenforceable, the remaining parts continue in full force and effect.

11. **Your LinkedIn, Naukri, Indeed and other accounts.** The Software never signs in to, uses or stores your LinkedIn,
    Naukri, Indeed or any other website account, and it never applies to jobs automatically. It only reads publicly
    visible job pages, the way anyone can without logging in. On the author's current testing and findings, the
    Software has not caused any account to be suspended, restricted or banned, and there is no known way for its normal
    use to do so. This reflects current findings only and is not a promise or guarantee: websites can change their
    rules, detection and enforcement at any time and without notice. If any of your accounts is ever warned,
    restricted, suspended, banned or otherwise affected, for any reason, the author and creator of the Software is not
    liable or responsible in any way, and points 4, 5 and 6 above apply in full.
