import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import sys
import platform


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://letterboxd.com/"
}


session = requests.Session()
session.headers.update(HEADERS)


def get_html_selenium(url):
    """Try to use Selenium (works on local)"""
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
        return html
    except Exception as e:
        print(f"⚠️ Selenium failed: {e}")
        return None


def get_html_playwright_fallback(url):
    """Fallback to Playwright when Selenium fails (works on Render)"""
    try:
        print(f"   Using Playwright fallback for: {url}")
        
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
            # Windows: use ProactorEventLoop
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            html = loop.run_until_complete(fetch())
            return html
        finally:
            loop.close()
            
    except Exception as e:
        
        return None


def get_html_requests_fallback(url):
    """Last resort fallback using requests with best headers"""
    try:
        print(f"   Using requests fallback for: {url}")
        improved_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://letterboxd.com/",
            "Upgrade-Insecure-Requests": "1",
        }
        res = requests.get(url, headers=improved_headers, timeout=15)
        res.raise_for_status()
        return res.text
    except Exception as e:
        
        return ""


def get_html(url):
    """Get HTML - try requests first, then Selenium, then Playwright"""

    res = session.get(url)

   
    if (
        "diary-entry-row" in res.text or
        "favourite-production-poster-container" in res.text
    ):
        return res.text

    
    html = get_html_selenium(url)
    if html and (
        "diary-entry-row" in html or
        "favourite-production-poster-container" in html
    ):
        return html

    
    html = get_html_playwright_fallback(url)
    if html and (
        "diary-entry-row" in html or
        "favourite-production-poster-container" in html
    ):
        return html

    
    html = get_html_requests_fallback(url)
    return html if html else res.text

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
    html = get_html(base_url)
    soup = BeautifulSoup(html, "html.parser")

    fav_section = soup.find("section", id="favourites")

    data = []

    if not fav_section:
        
        return pd.DataFrame()

    items = fav_section.find_all(
        "div", class_="favourite-production-poster-container"
    )

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

    
    return pd.DataFrame(data)



def extract_row(row):
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
        # Look for "rated-X" class
        for cls in classes:
            if cls.startswith("rated-"):
                rating = int(cls.replace("rated-", "")) / 2
                break

    liked = row.find("span", class_="icon-like") is not None

    return {
        "title": title,
        "date": date,
        "rating": rating,
        "liked": liked
    }

def scrape_diary_df(base_url):
    total_pages = get_total_pages(base_url)
    all_data = []

    for page in range(1, total_pages + 1):

        if page == 1:
            url = base_url + "/diary/films/"
        else:
            url = f"{base_url}/diary/films/page/{page}/"

        html = get_html(url)
        soup = BeautifulSoup(html, "html.parser")

        rows = soup.find_all("tr", class_="diary-entry-row")

        for row in rows:
            data = extract_row(row)
            if data["title"]:
                all_data.append(data)

        time.sleep(1)

    df = pd.DataFrame(all_data)

    if not df.empty:
        df = df.drop_duplicates(subset=["title"], keep="last")

    return df



def extract_profile(url):
    base = get_base_url(url)
    
    
    parts = [p for p in base.split("/") if p]
    username = parts[-1] if parts else "User"

    fav_df = scrape_favorites_df(base)
    diary_df = scrape_diary_df(base)

    return username, fav_df, diary_df



def extract_default_profile():
    """Extracts the base profile to blend against."""
    
    DEFAULT_URL = "https://letterboxd.com/judezoro/"
    return extract_profile(DEFAULT_URL)


def extract_user_profile(user_url):
    """Extracts the user-provided profile."""
   
    if not user_url.startswith("http"):
        user_url = "https://" + user_url
        
    return extract_profile(user_url)