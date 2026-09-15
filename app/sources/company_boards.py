"""Jobs for companies whose careers site is not on a supported hiring platform, found by searching Indeed and LinkedIn."""
from jobspy.model import Country, ScraperInput, Site

from app import normalize
from app.sources import boards

RESULTS_PER_SEARCH = 25
SITE_ENUMS = {"indeed": Site.INDEED, "linkedin": Site.LINKEDIN}


def search_company(company, titles, minutes_old, should_stop=lambda: False, sites=("indeed", "linkedin")):
    """Returns (raw India jobs posted by this company on the chosen sites, error messages).

    sites comes from the "company_search_sites" setting; Indeed alone suits long company lists
    because LinkedIn blocks after many searches.
    """
    wanted = normalize.company_key(company)
    jobs, errors = [], []
    linkedin_blocked = False
    for title in titles or [""]:
        for site in sites:
            site_enum = SITE_ENUMS[site]
            if should_stop():
                return jobs, errors
            if site == "linkedin" and linkedin_blocked:
                continue
            scraper_input = ScraperInput(
                site_type=[site_enum],
                search_term=f"{title} {company}".strip(),
                location="India",
                country=Country.INDIA,
                distance=50,
                results_wanted=RESULTS_PER_SEARCH,
                linkedin_fetch_description=False,  # fetched below, only for this company's jobs
            )
            boards.set_posted_within(scraper_input, site, minutes_old)
            posts, run_errors = boards.run_scraper(site, scraper_input)
            errors += [f"{site}: {e}" for e in run_errors]
            if site == "linkedin" and any("429" in e for e in run_errors):
                linkedin_blocked = True
            for post in posts:
                found = normalize.company_key(post.company_name)
                if not found or not (wanted in found or found in wanted):
                    continue
                if site == "linkedin":
                    boards.add_linkedin_details(post)
                jobs.append({**boards.post_to_raw(site, post), "search_title": title})
    return jobs, errors
