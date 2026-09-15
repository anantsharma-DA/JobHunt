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

**Tracking**
- **Jobs**, **Saved**, **Applied** and **Hidden** tabs with counts. **Apply** opens the application page and moves the
  job to Applied. Every move can be undone.
- Everything is kept between sessions in a small database on your computer.

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
- **Save** moves a job to **Saved**, and **Hide** moves it to **Hidden**.
- Every move shows an **Undo** message, and each tab has buttons to move jobs back.
- Before searching for a different kind of job, use **Settings → Clear the Jobs tab**. It removes jobs you haven't
  acted on; Saved, Applied and Hidden jobs stay.

### 4. See how many people applied

Fewer applicants usually means a better chance. Sort by **Fewest applicants**, or use the **Maximum applicants**
filter.

- **LinkedIn** counts are saved automatically during the search. LinkedIn never shows an exact number above 200
  ("Over 200 applicants").
- **Naukri** doesn't include counts in its search results. Press **Update Applicants (Naukri)**, next to Search.
  - It opens each Naukri job in your **Jobs** and **Saved** tabs, one after another, in an Edge window placed
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
| Clear the Jobs tab | Removes jobs you haven't saved, applied to or hidden | – |

See the next section for the best values.

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

- **Where your data is:** everything (jobs, statuses, companies, settings) is in `data\jobhunt.db` inside the JobHunt
  folder. Delete the `data` folder to erase it all.
- **What leaves your computer:** your job titles, cities and posted-within choice go to LinkedIn, Indeed and Naukri.
  Company names go to Indeed/LinkedIn, and careers links you add are opened to find their job platform. There is no
  tracking, no analytics and no login. Naukri pages open in a fresh, temporary Edge profile with no cookies or saved
  logins.
- **Only on your computer:** JobHunt listens on `127.0.0.1` (this computer only) and has no password. Don't change
  `--host` in `run.bat` or open port 8000 to your network, or anyone who can reach it could read and change your data.
- **Protections built in:**
  - Other websites open in your browser can't read or change JobHunt's data.
  - A strict Content Security Policy lets only JobHunt's own script run.
  - Links from job listings and imported files are used only if they are normal `http://` or `https://` addresses.
  - Careers links pointing to your own computer or local network are never opened.
  - Uploads are size-limited, and Excel files are read with protection against malicious XML (`defusedxml`).
  - HTTPS certificate checks stay on for every site.

## Moving or updating JobHunt

- **To another computer:** copy the whole JobHunt folder and double-click `run.bat` there. It notices the copied setup
  was made on another computer and rebuilds it once. The `data` folder brings your jobs and settings with it; delete
  it to start fresh.
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
│   ├── main.py              Web server, API and security checks
│   ├── search.py            Runs a search across the chosen sites
│   ├── applicant_update.py  Update Applicants (Naukri)
│   ├── db.py                Local SQLite database
│   ├── normalize.py         Cleans salaries, experience, locations, links
│   ├── matching.py          Match % from job titles and skills
│   ├── cities.py            Indian cities and states
│   ├── company_import.py    CSV/Excel company lists
│   └── sources/
│       ├── boards.py        LinkedIn and Indeed (via JobSpy)
│       ├── naukri.py        Naukri (via an off-screen Microsoft Edge window)
│       ├── ats.py           Greenhouse, Lever, Ashby, SmartRecruiters, Workday feeds
│       └── company_boards.py Company-name searches on Indeed/LinkedIn
└── static/
    ├── index.html, app.js, styles.css   The page
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
