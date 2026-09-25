# JobHunt

**A free job-search app for India that runs on your own Windows computer.**
It searches LinkedIn, Indeed, Naukri and the careers sites of companies you choose, puts every result in one list
with filters, and opens the real application page in one click.

- **Free:** no paid APIs, no AI key, no account or login needed.
- **Private:** runs only on your computer. Your jobs, searches and settings stay there.
- **India-focused:** search any Indian city, all of India, or remote jobs open to India.

> JobHunt finds jobs and opens their application pages. You read each job and submit the application yourself;
> nothing is applied to automatically.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Install and start](#install-and-start)
- [How to use](#how-to-use)
- [Tailor your resume with AI (optional)](#tailor-your-resume-with-ai-optional)
- [Interview questions (optional)](#interview-questions-optional)
- [Get your API keys, step by step](#get-your-api-keys-step-by-step)
- [Recommended settings so sites don't block you](#recommended-settings-so-sites-dont-block-you)
- [If a site blocks JobHunt](#if-a-site-blocks-jobhunt)
- [Your data, privacy and security](#your-data-privacy-and-security)
- [Moving or updating JobHunt](#moving-or-updating-jobhunt)
- [Troubleshooting](#troubleshooting)
- [Project files](#project-files)
- [Disclaimer](#disclaimer)

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
  and/or LinkedIn. Add companies one by one or import a CSV/Excel list.

**Results**
- One list without duplicates: a job found on several sites appears once, with a link to each site.
- **Match %** for every job, based on your job titles and skills.
- **Applicant counts:** from LinkedIn automatically, and from Naukri with the **Update Applicants (Naukri)** button.
- **Company ratings** (AmbitionBox ratings shown by Naukri), also shown on that company's jobs from other sites.
- **Filters:** job title searched, text, minimum match, minimum salary, maximum applicants, minimum company rating,
  experience, date posted, work mode, job type, city, source, and include/exclude companies.
- **Sort** by best match, newest, highest salary, fewest applicants or company name.

**Look**
- **Dark mode:** the button at the top right switches the whole app between light and dark. JobHunt remembers the
  choice, so it opens in the same mode next time, in any browser.

**Tracking**
- **Jobs**, **Saved Jobs**, **Applied** and **Hidden** tabs with counts. **Apply** opens the application page and moves the
  job to Applied. Every move can be undone.
- Everything is kept between sessions in a small database on your computer.

**Applying (optional, needs a free AI key)**
- **Tailor resume** rewrites your resume for one job using the advert's own words, and checks that the AI invented
  nothing: made-up numbers, skills or employers are flagged or removed.
- An **ATS check** scores the result and shows which of the job's keywords are missing.
- The tailored resume is written as a one-column, ATS-friendly **PDF with clickable links**.
- **Score targets:** set an ATS score and a "doesn't sound like AI" target, and tailoring keeps improving the resume
  (every ticked model writes a version, then the best is revised) until both are met, within the rounds you allow.
- Your standard answers (notice period, CTC, experience) and an optional cover note are ready to copy, next to an
  **Apply** button that opens the job's application page.
- Works with **OpenRouter, NVIDIA, Gemini, OpenAI or Claude**, with automatic fallback between them; free models are
  enough.

**Interview preparation (needs a free Tavily key)**
- **Frequently Asked Questions** on each job: questions candidates reported being asked by that company for that role,
  found on the web, each with links to where it appeared. Questions reported on 2 or more sites are marked verified.
- **Interview Questions** tab: the same for any job titles you pick.
- Answers come from the source page when it has one; otherwise the AI drafts one, clearly labelled.
- Everything found is kept on the **Saved Questions** tab (by job title, and by company) and builds up: searching
  again adds only new questions.

**Security**
- Answers only on your own computer, and refuses requests from other websites, other host names and other computers.
- API keys are encrypted with Windows' own protection (DPAPI), or can be given as environment variables instead; the
  page never receives them.
- Rate limits, size limits and a cap on slow jobs; strict checking of everything sent to the server; uploads checked
  by their real content; error messages that never show file paths or internals. Details in
  [Your data, privacy and security](#your-data-privacy-and-security).

## Requirements

- **Windows 10 or 11**
- **Internet connection**
- **Microsoft Edge**: it comes with Windows. Naukri searches use it.
- **Python 3.10 or newer**: if it's missing, `run.bat` installs it for you.

## Install and start

1. **Download:** on this GitHub page click **Code → Download ZIP**. Right-click the ZIP → **Extract All**.
   Use the extracted folder, not the files inside the ZIP.
2. **Double-click `run.bat`** in the extracted folder.
   - If Windows shows a security warning for a downloaded file, choose **Run** (or **More info → Run anyway**).
   - If your computer has no Python 3.10 or newer, `run.bat` installs Python 3.14 for your Windows user with
     winget, which comes with Windows 10 and 11. No administrator rights are needed. If that isn't possible, it asks
     you to install Python from https://www.python.org/downloads/ with **"Add python.exe to PATH"** ticked, then run
     `run.bat` again.
   - The first time, it installs everything JobHunt needs. This takes a few minutes and needs internet.
   - Your browser then opens JobHunt at http://localhost:8000.
3. **Keep the black `run.bat` window open** while you use JobHunt. Closing it stops the app.

**Next time:** double-click `run.bat`. It starts in a few seconds.

## How to use

### 1. Search for jobs

On the **Jobs** tab:

1. **Job titles:** click the box, tick one or more titles, or type your own and press Enter.
2. **Skills / keywords:** your chosen titles' skills are listed first. Tick them one by one, use
   **Tick all for my titles**, or type your own. Skills are used for the match %.
3. **Posted within:** drag the slider (5 minutes to 30 days).
4. **Cities** (optional): pick cities and/or **Remote**.
   - None picked: all of India is searched.
   - 1–3 picked: each site searches each city separately (plus a remote-only search if Remote is picked). This is
     faster and brings fewer unwanted jobs.
   - 4 or more: all of India is searched once, then filtered to your cities.
   - Jobs listed only in other cities are skipped. Jobs whose listing names no city are kept.
5. **Search on:** tick the sites to search.
6. Press **Search**. A loading screen shows each site's progress. **Cancel search** stops it and keeps the jobs
   found so far.

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
- **Job title searched:** every job remembers which search title found it. Tick titles to see only those jobs,
  without deleting anything.

### 3. Apply and keep track

- **Apply** opens the real application page in a new tab and moves the job to **Applied**.
- **Save** moves a job to **Saved Jobs**, and **Hide** moves it to **Hidden**.
- Every move shows an **Undo** message, and each tab has buttons to move jobs back.
- Before searching for a different kind of job, use **Settings → Clear the Jobs tab**. It removes jobs you haven't
  acted on; Saved Jobs, Applied and Hidden jobs stay.

### 4. See how many people applied

Fewer applicants usually means a better chance. Sort by **Fewest applicants**, or use the **Maximum applicants**
filter.

- **LinkedIn** counts are saved automatically during the search. LinkedIn never shows an exact number above 200
  ("Over 200 applicants").
- **Naukri** doesn't include counts in its search results. Press **Update Applicants (Naukri)**, next to Search.
  - It opens each Naukri job in your **Jobs** and **Saved Jobs** tabs, one after another, in an Edge window placed
    off-screen, and saves its applicant count. This takes about 4–5 seconds per job.
  - Jobs whose count was checked in the last day are skipped, so pressing it again soon is quick.
  - You can keep using the page while it runs. Counts appear on the job cards as they arrive, and **Stop** keeps the
    counts read so far. **Search** is unavailable until it finishes or you stop it.
  - **Details** on a single Naukri job also fetches that job's count.
  - **Tip:** hide the jobs you're not interested in first. Fewer jobs means a faster update and less chance of
    Naukri blocking it.
- **Indeed** and company careers sites don't publish applicant counts.

Counts are a snapshot from when they were read; hover over a count to see when.

### 5. Add company careers sites

On the **Companies** tab:

1. Enter the **company name** and, if you have it, its **careers page link**, then **Add company**.
   - To find a supported link, open any job on the company's careers page. If the address contains
     `greenhouse.io`, `lever.co`, `ashbyhq.com`, `smartrecruiters.com` or `myworkdayjobs.com`, paste it. JobHunt reads
     that job feed directly.
   - For any other careers link, JobHunt looks inside the page for one of those platforms.
   - If none is found, or there is no link, JobHunt searches your job titles plus the company name on Indeed and/or
     LinkedIn (see Settings) and keeps only that company's jobs.
2. **Add many at once:** upload a CSV or Excel (.xlsx) file with two columns, **Company name** and **Careers link**
   (the link can be empty). **Download a template** gives an example. Up to 5 MB and 2,000 companies per file.
   Companies already in your list are skipped.
3. **In search** turns a company on or off. **Test** shows how many matching jobs it finds right now.
4. On the **Jobs** tab, tick **Company sites** to include your companies in a search.

Only jobs located in India, or remote jobs open to India, are kept.

### 6. Settings

| Setting | What it does | Default |
|---|---|---|
| Results to fetch per job title, per site | How many jobs each site returns for each job title (and each city) | 100 |
| Pause between company-site requests | Wait between requests to company job feeds | 1 second |
| Companies without a supported careers link are searched on | Indeed only, LinkedIn only, or both | Indeed only |
| AI for resume tailoring | A key and models for each AI service, in the order they are tried | none, until you add a key |
| Tailoring targets | ATS score and "doesn't sound like AI" targets, and how many rounds to try | off (0), 3 rounds |
| Web search for interview questions | Your Tavily key, and how much of the free allowance is used | none, until you add a key |
| Clear the Jobs tab | Removes jobs you haven't saved, applied to or hidden | – |

How to get each key is explained in [Get your API keys, step by step](#get-your-api-keys-step-by-step).

See the next section for the best values.

## Tailor your resume with AI (optional)

JobHunt can rewrite your resume for one job at a time and get everything ready for the application. Searching for
jobs works without this; you only need an AI key to use it.

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
| **Claude (Anthropic)** | https://console.anthropic.com/settings/keys | Paid per use, no free tier: about $0.10 per tailored resume on Claude Opus 5, more when several rounds are needed. |

Step-by-step instructions for each service are in
[Get your API keys, step by step](#get-your-api-keys-step-by-step).

Each key is stored encrypted on this computer, is never shown again (only a hint like `sk-or-…7c2d`), and is sent only
to its own service. A sensible free setup is OpenRouter first with NVIDIA behind it, so tailoring keeps working when
one of them is busy.

Claude is called through Anthropic's official Python SDK. On Claude Opus 5 (and the Fable models), Anthropic's
server-side **refusal fallback** is switched on: if Claude's safety filter declines a request, Anthropic reruns it on
another Claude model instead of failing. Claude also returns guaranteed-valid JSON (structured outputs).

### 2. Fill in the Resume tab

Upload a resume you already have (PDF, Markdown or text) or paste its text, and the AI fills in the fields for you to
correct. You can also type everything yourself: contact details, links, skills, jobs with bullet points, projects,
education, certificates, and the answers forms ask for (notice period, current and expected CTC, total experience).

An HTML resume exported from a design tool usually has no readable text inside it, so use the PDF version.

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
  clickable.
- **Always one page:** the AI is told to write about 450-550 words. If the PDF would still run over, JobHunt first
  tightens the text and spacing a little (never below 9.5pt). If that isn't enough, the AI cuts the bullets that matter
  least for the job; every job stays listed, and older ones may go down to a bullet or two. Nothing is printed until you
  have checked the shorter wording and pressed **Make PDF** again. A two-page PDF is never saved.
- **Tailor again** asks for a fresh version at any time.
- **Finding them later:** the **Resume** tab lists every tailored resume (job, file name, date, ATS score) with
  **Open PDF**, **Download**, **Edit** (reopens the saved wording so you can change it and make the PDF again) and
  **Delete** (asks first, then removes the saved wording and deletes the PDF file).

### Score targets (Settings → Tailoring targets)

Leave both at 0 for one quick pass. With targets set, **Tailor resume** works in rounds:

1. **Round 1:** every model you ticked, on every service, writes its own version at the same time. Versions with
   invented claims always rank below honest ones.
2. **Rounds 2 and on:** the best version's model gets specific feedback (advert keywords your details support but it
   didn't use yet, phrases that sound generated) and rewrites it. The better version is kept each time.
3. It stops as soon as both targets are met, or after the number of rounds you set (default 3), keeping the best
   version either way. You can press **Stop** at any time. Round 1 can take a few minutes with many free models.

- **ATS target:** before starting, JobHunt works out the best score your details can honestly reach. If the target is
  higher, it tells you why (for example, skills the advert wants that aren't in your details, or a resume shorter than
  ATS systems like) and lets you tick the missing skills you really have. Ticked skills are added to your details under
  "Also skilled in"; nothing is added without you.
- **"Doesn't sound like AI" target:** the average of a built-in style check (stock phrases like "spearheaded" and
  "results-driven", lines all the same length, repeated openings) and one fixed AI model acting as a reviewer. It
  names the exact phrases to change. It is a style estimate, not a real AI detector; even commercial detectors are
  unreliable.

### 4. Apply

The same window gets the rest ready: your answers with **Copy** buttons, and an optional short cover note written
only from your saved details. Then press **Apply** (in that window, or on the job card): it opens the real application
page and moves the job to the Applied tab. Upload the PDF there yourself.

**What is sent to the AI service:** your resume details and that job's title, company and description. Nothing else,
and nothing at all until you press a button. Your jobs, searches and settings never leave your computer.

## Interview questions (optional)

**Frequently Asked Questions** on a job card finds questions candidates reported being asked by that company for that
role. The **Interview Questions** tab does the same for any job titles you pick from the list.

- **How they are found:** **Tavily** (1,000 free credits a month; key on the Settings tab) finds up to 8 pages, and
  JobHunt reads the questions (and any answers under them) straight from the pages' text, so none can be made up.
  Only when the pages have too few questions written out are your AI models asked to find more, and each one must
  still appear on a page. A company search looks for candidates' "interview experience" write-ups, since those name
  the questions actually asked.
- **Reading the pages:** Tavily's search often sends only a two-line preview of a page. JobHunt then reads the page
  with Tavily Extract, or opens it itself like a browser would (this is how AmbitionBox and Glassdoor get read). If
  pages about the exact role still can't be read, Tavily's stronger reader tries them. A search usually uses 2 credits,
  and up to 4 when that stronger reader is needed.
- **Relevance:** in a company search, pages that don't mention the company are left out. Pages about the exact role come
  first. A near role (a "Data Engineer" list for a "Data Science Engineer" search) only tops up a short list.
- **Saved, and built up over time:** every question found is kept. Searching the same job title (or company) again
  looks for **new** questions only: it uses different search wording each time, skips pages it has already read, and
  leaves out questions already saved. It then says how many new ones it found, "0 new questions found" when there were
  none. A saved question that turns up on another site gains that link (and may become verified).
- **Where they are kept:** the **Saved Questions** tab has two sections; the buttons at its top switch between them.
  **Profile Wise Saved Questions** holds job-title searches, with a job-title filter. **Saved Frequently Asked
  Questions** holds Frequently Asked Questions on jobs, with a company filter. Each group has **Search for new
  questions**.
- **Gemini search, if your key allows it:** Gemini can search Google itself and say which page supports each question.
  Google allows this for free only on older keys (Gemini 2.5, about 500 a day) or on keys with billing switched on (5,000
  a month free). JobHunt tries it first; on newer free keys Google refuses, and JobHunt goes straight to Tavily for the
  rest of the day. The Settings tab shows which one is in use.
- **Only real, sourced questions:** every question shows links to where it was found. A question no page backs, or
  that isn't actually on the page it's said to come from, is dropped.
- **Verified:** questions reported on 2 or more different sites get a "verified" badge and are listed first.
- **Answers:** taken from the source page when it gives one; otherwise drafted by your AI models (using your resume
  details for "tell me about…" questions) and labelled **AI-drafted: check before using**.
- **Free limits:** JobHunt counts both services (Settings tab) and never goes past their free limits. Opening saved
  questions costs nothing; only a new search uses credits.
- **Sites like Glassdoor and AmbitionBox:** when Tavily can't read a page from them, JobHunt opens that one page once,
  the way your browser would, to read the questions on it. It does not crawl these sites. Their terms may not allow
  automated reading, so as with the rest of JobHunt, using this is your own responsibility (see the Disclaimer).
- The searches Gemini ran are shown as Google links under the results, as Google asks apps using its search to do.

## Get your API keys, step by step

Searching for jobs needs no key at all. Keys are only needed for the optional AI features (resume tailoring, cover
notes, drafted answers) and for interview questions (Tavily). You need **at least one AI service**; the free ones
(OpenRouter, NVIDIA, Gemini) are enough. Sites change their menus now and then, so a button may be named slightly
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

Free models allow about 20 requests a minute and a daily cap; ticking several lets JobHunt fall back between them.

### NVIDIA NIM (free developer credits)

1. Go to https://build.nvidia.com and **Sign in**, or create a free NVIDIA account (no card needed).
2. Open any model page (for example a Nemotron model) and press **Get API Key**, then **Generate Key**.
3. Copy the key (it starts with `nvapi-`).
4. In JobHunt: **Settings → NVIDIA NIM card**, paste it, **Fetch models**, and tick a few.

NVIDIA lists many models that a free key can't use; if one says "not available", untick it and pick another.

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
2. Under **Billing**, add credit. Under **Limits**, you can set a monthly spend limit.
3. Open https://console.anthropic.com/settings/keys → **Create Key**, name it `JobHunt`.
4. Copy the key (it starts with `sk-ant-`). It is shown only once.
5. In JobHunt: **Settings → Claude card**, paste it, **Fetch models**, and tick `claude-opus-5` (suggested first).

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

### Settings

| Setting | Recommended |
|---|---|
| **Results to fetch per job title, per site** | Depends on how many searches LinkedIn has to run. Count *job titles × cities* (Remote counts as a city; no cities = 1): **1–2 → 100**, **3–4 → 50**, **5 or more → 30**. |
| **Posted within** | **1 day** for daily use. With 1 day, 50 results per title is enough and searches are much faster. |
| **Pause between company-site requests** | Keep **1 second**. Use 0.5 only if you have many Workday or SmartRecruiters companies. Don't set it to 0. |
| **Companies without a supported careers link are searched on** | **Indeed only**, especially with a long company list. Each company is a separate search for every job title, and on LinkedIn that quickly uses up your limit and blocks your main LinkedIn search too. |

A rough guide for LinkedIn: keep *job titles × cities × results per title* at about **200 or less** per search.
LinkedIn doesn't publish its limit; this comes from testing.

### Habits

- **Search once or twice a day** with Posted within = 1 day, instead of repeating large 30-day searches.
- **Leave a gap** (30 minutes or more) between large searches that include LinkedIn.
- **Untick LinkedIn** for extra searches with many titles or cities. Indeed and Naukri accept more.
- **Before Update Applicants (Naukri),** hide jobs you don't want, and don't press it over and over. Counts are
  only re-checked once a day anyway.
- **Run JobHunt on one computer at a time** per internet connection. Devices on the same Wi-Fi share one internet
  address, so their requests add up.

## If a site blocks JobHunt

A block is **temporary** and applies to your **internet connection**, not to you:

- JobHunt never logs in, so your LinkedIn, Indeed or Naukri **accounts are not affected**.
- Sites can't see your computer's hardware address, so the block isn't tied to your computer.
- **Other devices on the same Wi-Fi** share the connection, so they may be blocked for the same time.
- When one site blocks, the other sites in the same search keep going, and jobs found so far are kept.

| Site | What JobHunt shows | When it clears and what to do |
|---|---|---|
| **LinkedIn** | "blocked for now (too many requests). Try again in 30–60 minutes" | Usually within 30–60 minutes, sometimes a few hours. JobHunt stops asking LinkedIn for the rest of that search, because more requests only make the block last longer. Wait, then search again with fewer titles, cities or results. |
| **Naukri** | "Naukri denied access for now. Try again later" | Naukri publishes no time. Wait at least an hour. Then search with fewer titles, and hide unwanted jobs before **Update Applicants (Naukri)**. The update stops as soon as Naukri refuses and keeps the counts already read. |
| **Indeed** | "the site refused the request (403). Try again later" or "blocked for now (too many requests)…" | Rare. Wait an hour and try again. |
| **Company sites** | A message such as "HTTP 429 from …" next to the company | That company's job platform is limiting requests. Raise **Pause between company-site requests** to 2 seconds and try later. |

You don't need to do anything to unblock: just wait, then search more lightly.

## Your data, privacy and security

- **Where your data is:** everything (jobs, statuses, companies, settings, saved interview questions, your resume
  details and your API keys) is in `data\jobhunt.db` inside the JobHunt folder, and tailored resumes are in
  `data\resumes`. Delete the `data` folder to erase it all.
- **What leaves your computer:** your job titles, cities and posted-within choice go to LinkedIn, Indeed and Naukri.
  Company names go to Indeed/LinkedIn, and careers links you add are opened to find their job platform. When you
  tailor a resume, the AI service receives your resume details and the job's title, company and description, and
  nothing else. When you look up interview questions, Gemini or Tavily receives the job title and company name, and
  drafting answers also sends your resume details to your AI service. There is no tracking and no analytics. Naukri
  pages open in a fresh, temporary Edge profile with no cookies or saved logins.

### How JobHunt is protected

**Who can use it (authentication and authorization).** JobHunt is a single-user app with no login, by design: it
answers only on `127.0.0.1` (this computer), so anyone who can use it is already signed in to your Windows account.
On top of that:
- Requests from any other computer are refused, even if someone changed `--host` in `run.bat`. (Still, don't
  change it, and don't open port 8000 to your network.)
- Only the host names `localhost` and `127.0.0.1` are accepted, which blocks "DNS rebinding" tricks.
- Changes are only accepted from the JobHunt page itself: every change must carry JobHunt's own header, and requests
  from other websites (checked by Origin and Sec-Fetch-Site) are refused. Other websites can't read JobHunt's data.
- Lock your computer when you step away; anyone using your Windows account can use JobHunt.

**API keys (secret management).**
- Keys are **encrypted with Windows' Data Protection API (DPAPI)**, tied to your Windows login. Someone who copies
  `data\jobhunt.db` to another computer or Windows account can't read them. Keys saved by older versions are
  encrypted automatically the next time JobHunt starts, and no readable copy is left in the file.
- Keys can instead come from **environment variables** (see [Keeping your keys safe](#keeping-your-keys-safe)); those
  are never written to disk.
- Keys are never sent to the page (it only gets a masked hint), never written to logs, and each is sent only to its
  own service. The `.gitignore` keeps the `data` folder, databases and `.env` files out of git, so they can't be
  published by mistake.
- Deleted or replaced data (an old key, a removed resume) is overwritten in the database file, not left behind.

**Rate limits, size limits and busy limits.** Counted per connecting address; a request over a limit gets "Too many
requests. Please wait N seconds…":

| What | Limit |
|---|---|
| Changing API keys | 10 a minute |
| AI actions (tailor, PDF, cover note, resume import, fetching models, testing) | 20 a minute |
| Web actions (interview searches, job searches, applicant updates, adding/testing/importing companies) | 20 a minute |
| Everything else | 600 a minute |
| Slow jobs (AI and web actions) running at the same time | 4 |
| Size of one request | 1 MB (uploads: 5 MB) |

**Input checking (validation).** Everything the page sends is checked on the server before JobHunt acts on it: its
type, its length or range, its format (no control characters, API keys with visible characters only, IDs as positive
numbers) and its allowed values (for example a job status or an AI service name). Unknown fields are refused rather
than ignored. The reply says what was wrong without repeating what was sent.

**File uploads.** Your old resume (PDF, HTML, Markdown, text) and company lists (CSV, Excel) are treated as untrusted:
- The content must match the name: a real PDF signature for `.pdf`, a real Excel workbook for `.xlsx`, plain text for
  `.csv`, `.txt`, `.md` and `.html`. Programs, pictures, zip files or renamed files are refused.
- Size limits: 5 MB per file. Excel files are also limited once unpacked (no "zip bombs"), workbooks with macros
  are refused, and XML attacks are blocked (`defusedxml`).
- Uploads are read in memory only: never saved to disk, never opened by another program, never run. Only their text
  is kept. File names may not contain folders or special characters.
- Tailored PDFs get safe file names and are only served from the `data\resumes` folder. The page Edge prints has no
  network access and may not run scripts.

**Error messages.** Messages JobHunt writes for you (a wrong API key, an empty Resume tab, a site blocking searches)
tell you what to do. Anything unexpected shows only **"Something went wrong. Please try again later."**, never a stack
trace, file path, database detail or a library's message; the full detail goes only to the black `run.bat` window.

**Also:**
- A strict Content Security Policy lets only JobHunt's own script run; all text from websites and AI is escaped
  before it is shown.
- Links from job listings and imported files are used only if they are normal `http://` or `https://` addresses.
- Web pages JobHunt opens (careers pages, interview-question pages) are checked first: addresses on your own computer
  or local network are never opened, redirects are checked too, and at most 2 MB is read.
- HTTPS certificate checks stay on for every site.

## Moving or updating JobHunt

- **To another computer:** copy the whole JobHunt folder and double-click `run.bat` there. It notices the copied setup
  was made on another computer and rebuilds it once. The `data` folder brings your jobs and settings with it; delete
  it to start fresh. **API keys don't move:** they are encrypted for your Windows account on the old computer, so
  paste them again on the Settings tab (the same applies to a different Windows account on the same computer).
- **To a newer version:** download and extract the new version, then copy the `data` folder from your old JobHunt
  folder into the new one to keep your jobs, companies and settings.

## Troubleshooting

| Problem | What to do |
|---|---|
| "Setup failed" in the `run.bat` window | Read the messages above it; most often the internet dropped during installation. Delete the `.venv` folder and run `run.bat` again. |
| "JobHunt needs Python 3.10 or newer, and it could not be installed automatically" | Install Python from https://www.python.org/downloads/, tick **"Add python.exe to PATH"**, then run `run.bat` again. |
| The browser didn't open | Open http://localhost:8000 yourself while the `run.bat` window is open. |
| The page doesn't load, or an error mentions port 8000 | Another JobHunt window is probably open. Close all `run.bat` windows and start it again. |
| "Microsoft Edge was not found" | Install Microsoft Edge; Naukri needs it. The other sites still work. |
| An Edge window appears in the taskbar | That's the off-screen window JobHunt uses for Naukri. Don't close it during a Naukri search or applicant update. |
| No jobs found | Widen **Posted within**, pick fewer cities, and press **Reset** on the filters. |
| A site keeps failing even after waiting | Job sites change their pages. Update the site readers with the commands below, then restart `run.bat`. |
| A company's **Test** finds 0 jobs | It may have no open jobs matching your titles in India right now, or its careers site isn't supported (then it's searched on Indeed/LinkedIn by name). |
| "No model could answer…" when tailoring | Free models are often busy or out of credit. Tick a few models on the Settings tab so JobHunt can fall back to the next one, or try again later. |
| "…did not accept your API key" | The key is for a different service, or has been revoked. Paste a fresh key and press **Test the order**. |
| Tailoring says to fill in the Resume tab | Your resume details need at least your name and one job or project with a bullet point. |
| Keys are missing after moving JobHunt | Keys are encrypted for one Windows account on one computer. Paste them again on the Settings tab. |
| "Too many requests. Please wait N seconds…" | A rate limit was reached (see [How JobHunt is protected](#how-jobhunt-is-protected)). Wait that long and try again. |
| "JobHunt is busy with other searches or AI requests" | Four slow jobs are already running. Wait for one to finish. |
| "Some of the information sent isn't valid (…)" | A value was outside what JobHunt accepts (too long, wrong characters). Correct the named field. |
| "Something went wrong. Please try again later." | Something unexpected happened. Try again; if it repeats, the black `run.bat` window shows the details. |

Update the site readers (run these in the JobHunt folder):

```
.venv\Scripts\python -m pip install -U --no-deps python-jobspy
.venv\Scripts\python -m pip install -U playwright
```

`python-jobspy` is installed with `--no-deps` on purpose: its published version pins an old numpy that can't install on
new Python versions. Its real dependencies are in `requirements.txt`. To reinstall everything, delete the `.venv`
folder and run `run.bat` again.

## Project files

```
JobHunt/
├── run.bat                  Installs everything (including Python if needed) and starts the app
├── requirements.txt         Python packages run.bat installs
├── app/
│   ├── main.py              Web server, API, input checking and error messages
│   ├── guard.py             Security limits: this computer only, rate, size and busy limits
│   ├── secret_store.py      Encrypts API keys (Windows DPAPI); keys from environment variables
│   ├── errors.py            Plain error messages; details only in the run.bat window
│   ├── search.py            Runs a search across the chosen sites
│   ├── applicant_update.py  Update Applicants (Naukri)
│   ├── db.py                Local SQLite database
│   ├── normalize.py         Cleans salaries, experience, locations, links
│   ├── matching.py          Match % from job titles and skills
│   ├── cities.py            Indian cities and states
│   ├── company_import.py    CSV/Excel company lists
│   ├── ai.py                Talks to OpenRouter, NVIDIA, Gemini, OpenAI (and Claude), with fallback
│   ├── resume.py            Your resume details, tailoring, fact-checking, ATS report
│   ├── resume_pdf.py        Prints the tailored resume to an ATS-safe PDF
│   ├── tailor_run.py        Tailoring in rounds until the score targets are met
│   ├── claude_ai.py         Claude, through Anthropic's official SDK
│   ├── interview.py         Interview questions from the web (Tavily, Gemini with Google Search), saved and built up
│   └── sources/
│       ├── boards.py        LinkedIn and Indeed (via JobSpy)
│       ├── naukri.py        Naukri (via an off-screen Microsoft Edge window)
│       ├── ats.py           Greenhouse, Lever, Ashby, SmartRecruiters, Workday feeds
│       └── company_boards.py Company-name searches on Indeed/LinkedIn
└── static/
    ├── index.html, app.js, styles.css   The page
    ├── resume.js            Resume tab, AI settings, Tailor resume window, interview and saved questions
    └── job_catalog.json     Job titles and skills (editable)
```

Your own data (`data/`) and the installed Python environment (`.venv/`) are created on your computer and are never
part of the download.

Built with [FastAPI](https://fastapi.tiangolo.com/), [JobSpy](https://github.com/cullenwatson/JobSpy),
[Playwright](https://playwright.dev/python/) with Microsoft Edge, SQLite, openpyxl and plain JavaScript.

## Disclaimer

JobHunt is an independent personal project. It is not affiliated with, endorsed by or connected to LinkedIn, Indeed,
Naukri, AmbitionBox or any company it lists. It reads publicly visible job listings, at a modest pace, to help one
person search for jobs. Use it responsibly and in line with each site's terms of use; you are responsible for how you
use it. Job details, salaries, applicant counts and ratings come from those sites and can be incomplete or out of
date, so always check the original listing before applying.

### Legal disclaimer and limitation of liability

By downloading, installing, copying, modifying or using JobHunt (the "Software"), you confirm that you have read,
understood and agree to the terms below. If you do not agree, do not download or use the Software.

1. **No affiliation.** The Software is an independent project. It is not affiliated with, authorised, sponsored,
   endorsed or approved by LinkedIn, Indeed, Naukri, AmbitionBox, Greenhouse, Lever, Ashby, SmartRecruiters, Workday,
   or any other company, employer, careers site or job platform, including any company or website a user adds to the
   Software. All product names, company names, trademarks and logos belong to their respective owners and are used
   only to describe which websites the Software can read.

2. **Provided "as is".** The Software is provided "AS IS" and "AS AVAILABLE", without warranty of any kind, express
   or implied, including but not limited to warranties of merchantability, fitness for a particular purpose,
   accuracy, reliability, non-infringement, or uninterrupted or error-free operation. No warranty is given that any
   job listing, salary, applicant count, rating or other information shown by the Software is accurate, complete,
   current or lawful.

3. **You are solely responsible.** You alone are responsible and liable for your use of the Software and its
   consequences, including:
   - complying with all laws and regulations that apply to you, including computer-misuse, data-protection,
     privacy and intellectual-property laws;
   - complying with the terms of use, terms of service and access policies of every website you access with the
     Software;
   - any account suspension, access restriction, IP address block, claim, notice, complaint, demand, lawsuit,
     prosecution or other legal or non-legal action brought by any website, company, authority or other third party;
   - any decision you make, or application you submit, based on information shown by the Software;
   - the security of your own computer, network and data.

4. **Limitation of liability.** To the maximum extent permitted by applicable law, in no event shall the author and
   creator of the Software, or any contributor or copyright holder, be liable to you or to any third party for any
   claim, damages, loss or other liability of any kind, whether direct, indirect, incidental, special,
   consequential, exemplary or punitive, including but not limited to loss of data, profits, income, employment
   opportunities, business or reputation, account suspension or blocking, legal costs, fines or penalties, whether
   in contract, tort (including negligence), statute or otherwise, arising from or in connection with the Software,
   its use, misuse or inability to use, or these terms, even if advised of the possibility of such damages.

5. **Indemnity.** You agree to indemnify, defend and hold harmless the author and creator of the Software, and any
   contributor, from and against all claims, liabilities, damages, losses, costs and expenses (including reasonable
   legal fees) arising from or related to your use or misuse of the Software, your breach of these terms, or your
   violation of any law, any website's terms, or the rights of any third party.

6. **Third-party websites and content.** The Software reads information that websites make publicly visible and
   opens their pages in your browser. The author does not own, control, host, verify or endorse any third-party
   website, job listing or content, and is not responsible for them. Any application you submit, and any
   relationship that follows, is solely between you and the employer or website concerned.

7. **No advice.** Nothing in the Software or its documentation is legal, career, financial or other professional
   advice.

8. **Copies and modified versions.** Anyone who copies, modifies or redistributes the Software is solely responsible
   for their copy or version and its use. The author is not liable for any modified or redistributed version.

9. **Acceptance and severability.** Downloading or using the Software means you accept these terms. If any part of
   these terms is found to be invalid or unenforceable, the remaining parts continue in full force and effect.
