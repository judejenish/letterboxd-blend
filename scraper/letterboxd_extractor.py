import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import sys
import logging

# Configure logging to be visible in Render
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://letterboxd.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

DIARY_COLUMNS = ["title", "date", "rating", "liked"]
FAVORITES_COLUMNS = ["title", "title_full", "slug"]

session = requests.Session()
session.headers.update(HEADERS)


def empty_diary_df():
    return pd.DataFrame(columns=DIARY_COLUMNS)


def empty_favorites_df():
    return pd.DataFrame(columns=FAVORITES_COLUMNS)


def diagnose_html(html, url):
    """Print diagnostic info about what we got"""
    if not html:
        logger.warning(f"Empty HTML for {url}")
        return
    
    logger.info(f"📊 HTML Length: {len(html)} bytes for {url}")
    
    # Check what's in the HTML
    checks = {
        "has favourites": 'id="favourites"' in html,
        "has diary-entry-row": 'diary-entry-row' in html,
        "has primaryname": 'primaryname' in html,
        "has rate-limited": 'rate' in html.lower() and 'limit' in html.lower(),
        "has captcha": 'captcha' in html.lower(),
        "has cloudflare": 'cloudflare' in html.lower(),
        "has bot detection": 'bot' in html.lower() or 'access denied' in html.lower(),
    }
    
    for check, result in checks.items():
        emoji = "✓" if result else "✗"
        logger.info(f"   {emoji} {check}: {result}")


def get_html_selenium(url):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        
        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--no-sandbox") 
        chrome_options.add_argument("--disable-dev-shm-usage") 
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"user-agent={HEADERS['User-Agent']}")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.get(url)
        time.sleep(3) 
        html = driver.page_source
        driver.quit()
        logger.info(f"✅ Selenium worked for {url}")
        return html
    except Exception as e:
        logger.warning(f"❌ Selenium failed: {str(e)[:100]}")
        return None


def get_html_playwright_fallback(url):
    try:
        logger.info(f"🎭 Trying Playwright for {url}")
        
        import asyncio
        from playwright.async_api import async_playwright
        
        async def fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(2)
                html = await page.content()
                await browser.close()
                return html
        
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            html = loop.run_until_complete(fetch())
            logger.info(f"✅ Playwright worked for {url}")
            return html
        finally:
            loop.close()
            
    except Exception as e:
        logger.warning(f"❌ Playwright failed: {str(e)[:100]}")
        return None


def get_html(url):
    """Get HTML with detailed logging"""
    logger.info(f"📡 Fetching: {url}")
    
    res = session.get(url)
    logger.info(f"   Status: {res.status_code}, Length: {len(res.text)}")
    
    is_diary_page = "/diary/" in url
    
    # Diagnose what we got
    if is_diary_page:
        if "diary-entry-row" in res.text:
            logger.info(f"   ✅ Got diary entries via session.get()")
            return res.text
        else:
            logger.warning(f"   ⚠️ session.get() did NOT have diary-entry-row")
            diagnose_html(res.text, url)
    else:
        if 'id="favourites"' in res.text:
            logger.info(f"   ✅ Got favourites section via session.get()")
            return res.text
        else:
            logger.warning(f"   ⚠️ session.get() did NOT have favourites")
            diagnose_html(res.text, url)
    
    # Try Selenium
    html = get_html_selenium(url)
    if html:
        if is_diary_page and "diary-entry-row" in html:
            return html
        if not is_diary_page and 'id="favourites"' in html:
            return html
        logger.warning(f"   ⚠️ Selenium got HTML but missing target content")
    
    # Try Playwright
    html = get_html_playwright_fallback(url)
    if html:
        if is_diary_page and "diary-entry-row" in html:
            return html
        if not is_diary_page and 'id="favourites"' in html:
            return html
        logger.warning(f"   ⚠️ Playwright got HTML but missing target content")
    
    logger.error(f"   ❌ All methods failed for {url}")
    return res.text


def resolve_url(url):
    try:
        return session.get(url, allow_redirects=True).url
    except:
        return url


def get_base_url(url):
    return resolve_url(url).rstrip("/")


def get_total_pages(base_url):
    url = base_url + "/diary/films/"
    html = get_html(url)
    soup = BeautifulSoup(html, "html.parser")

    pagination = soup.find("div", class_="pagination")
    if not pagination:
        return 1

    pages = pagination.find_all("li", class_="paginate-page")
    nums = []
    for p in pages:
        txt = p.text.strip()
        if txt.isdigit():
            nums.append(int(txt))

    return max(nums) if nums else 1


def scrape_favorites_df(base_url):
    logger.info(f"⭐ Scraping favorites: {base_url}")
    
    try:
        html = get_html(base_url)
        soup = BeautifulSoup(html, "html.parser")
        fav_section = soup.find("section", id="favourites")

        if not fav_section:
            logger.warning(f"   ❌ No favorites section in parsed HTML")
            return empty_favorites_df()

        items = fav_section.find_all("div", class_="favourite-production-poster-container")
        logger.info(f"   Found {len(items)} favorite items")

        data = []
        for item in items:
            comp = item.find("div", class_="react-component")
            if comp:
                title_full = comp.get("data-item-name")
                slug = comp.get("data-item-slug")
                title = title_full.split("(")[0].strip() if title_full else None
                data.append({
                    "title": title,
                    "title_full": title_full,
                    "slug": slug
                })

        if not data:
            return empty_favorites_df()
        
        logger.info(f"   ✅ Extracted {len(data)} favorites")
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"   ❌ Error scraping favorites: {e}")
        return empty_favorites_df()


def extract_row(row):
    try:
        title_tag = row.find("h2", class_="primaryname")
        title = title_tag.text.strip() if title_tag else None

        day_link = row.find("a", class_="daydate")
        date = None
        if day_link:
            href = day_link.get("href", "")
            parts = [p for p in href.split("/") if p]
            try:
                for_idx = parts.index("for")
                date = f"{parts[for_idx+1]}-{parts[for_idx+2]}-{parts[for_idx+3]}"
            except (ValueError, IndexError):
                date = None

        rating = None
        rating_span = row.find("span", class_="rating")
        if rating_span:
            classes = rating_span.get("class", [])
            for cls in classes:
                if cls.startswith("rated-"):
                    try:
                        rating = int(cls.replace("rated-", "")) / 2
                        break
                    except:
                        pass

        liked = row.find("span", class_="icon-liked") is not None

        return {
            "title": title,
            "date": date,
            "rating": rating,
            "liked": liked
        }
    except Exception as e:
        logger.warning(f"Error extracting row: {e}")
        return {"title": None, "date": None, "rating": None, "liked": False}


def scrape_diary_df(base_url):
    logger.info(f"📽️ Scraping diary: {base_url}")
    
    try:
        total_pages = get_total_pages(base_url)
        logger.info(f"   Total pages: {total_pages}")
        all_data = []

        for page in range(1, total_pages + 1):
            if page == 1:
                url = base_url + "/diary/films/"
            else:
                url = f"{base_url}/diary/films/page/{page}/"

            html = get_html(url)
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr", class_="diary-entry-row")
            logger.info(f"   Page {page}: {len(rows)} entries")

            for row in rows:
                data = extract_row(row)
                if data["title"]:
                    all_data.append(data)

            time.sleep(1)

        if not all_data:
            logger.warning(f"   ⚠️ No diary data found")
            return empty_diary_df()
        
        df = pd.DataFrame(all_data)
        df = df.drop_duplicates(subset=["title"], keep="last")
        
        for col in DIARY_COLUMNS:
            if col not in df.columns:
                df[col] = None
        
        logger.info(f"   ✅ Total diary entries: {len(df)}")
        return df
        
    except Exception as e:
        logger.error(f"   ❌ Error scraping diary: {e}")
        return empty_diary_df()


def extract_profile(url):
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 EXTRACTING PROFILE: {url}")
    logger.info(f"{'='*60}")
    
    base = get_base_url(url)
    parts = [p for p in base.split("/") if p]
    username = parts[-1] if parts else "User"

    fav_df = scrape_favorites_df(base)
    diary_df = scrape_diary_df(base)
    
    # Final safety: ensure dataframes always have correct columns
    if "title" not in diary_df.columns:
        logger.warning(f"⚠️ SAFETY: diary df missing 'title' column")
        diary_df = empty_diary_df()
    
    if "title" not in fav_df.columns:
        logger.warning(f"⚠️ SAFETY: fav df missing 'title' column")
        fav_df = empty_favorites_df()
    
    logger.info(f"\n✅ RESULTS for {username}:")
    logger.info(f"   Favorites: {len(fav_df)}")
    logger.info(f"   Diary: {len(diary_df)}")
    logger.info(f"{'='*60}\n")

    return username, fav_df, diary_df


def extract_default_profile():
    DEFAULT_URL = "https://letterboxd.com/judezoro/"
    return extract_profile(DEFAULT_URL)


def extract_user_profile(user_url):
    if not user_url.startswith("http"):
        user_url = "https://" + user_url
    return extract_profile(user_url)