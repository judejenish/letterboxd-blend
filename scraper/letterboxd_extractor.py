import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import sys


# Better default headers - mimics real browser
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


# Define columns ONCE - used everywhere to ensure consistency
DIARY_COLUMNS = ["title", "date", "rating", "liked"]
FAVORITES_COLUMNS = ["title", "title_full", "slug"]


session = requests.Session()
session.headers.update(HEADERS)


def empty_diary_df():
    """Always return an empty diary df WITH correct columns"""
    return pd.DataFrame(columns=DIARY_COLUMNS)


def empty_favorites_df():
    """Always return an empty favorites df WITH correct columns"""
    return pd.DataFrame(columns=FAVORITES_COLUMNS)


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
        print(f"⚠️ Selenium failed: {str(e)[:80]}")
        return None


def get_html_playwright_fallback(url):
    """Fallback to Playwright when Selenium fails (works on Render)"""
    try:
        print(f"   🎭 Trying Playwright for: {url}")
        
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
            return html
        finally:
            loop.close()
            
    except Exception as e:
        print(f"   ⚠️ Playwright failed: {str(e)[:80]}")
        return None


def get_html_requests_fallback(url):
    """Last resort fallback using requests with best headers"""
    try:
        improved_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://letterboxd.com/",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
        res = requests.get(url, headers=improved_headers, timeout=15)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"   ❌ Requests fallback failed: {str(e)[:80]}")
        return ""


def get_html(url):
    """Get HTML with URL-specific validation"""
    print(f"📡 Fetching: {url}")
    
    res = session.get(url)
    
    is_diary_page = "/diary/" in url
    
    # Check if initial response has what we need
    if is_diary_page:
        if "diary-entry-row" in res.text:
            print(f"   ✓ Got diary entries via session.get()")
            return res.text
    else:
        if 'id="favourites"' in res.text:
            print(f"   ✓ Got favourites section via session.get()")
            return res.text
    
    print(f"   ⚠️ Initial request didn't have what we need, trying fallbacks...")
    
    # Try Selenium
    html = get_html_selenium(url)
    if html:
        if is_diary_page and "diary-entry-row" in html:
            print(f"   ✓ Got diary entries via Selenium")
            return html
        if not is_diary_page and 'id="favourites"' in html:
            print(f"   ✓ Got favourites section via Selenium")
            return html
    
    # Try Playwright
    html = get_html_playwright_fallback(url)
    if html:
        if is_diary_page and "diary-entry-row" in html:
            print(f"   ✓ Got diary entries via Playwright")
            return html
        if not is_diary_page and 'id="favourites"' in html:
            print(f"   ✓ Got favourites section via Playwright")
            return html
    
    # Last resort: requests with better headers
    print(f"   ⚠️ All methods failed, using requests fallback")
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
    print(f"⭐ Scraping favorites: {base_url}")
    
    try:
        html = get_html(base_url)
        soup = BeautifulSoup(html, "html.parser")
        fav_section = soup.find("section", id="favourites")

        if not fav_section:
            print(f"   ❌ No favorites section found")
            return empty_favorites_df()

        items = fav_section.find_all("div", class_="favourite-production-poster-container")
        print(f"   Found {len(items)} favorite items")

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
            print(f"   ⚠️ No favorite data extracted")
            return empty_favorites_df()
        
        print(f"   ✓ Extracted {len(data)} favorites")
        return pd.DataFrame(data)
    except Exception as e:
        print(f"   ❌ Error scraping favorites: {e}")
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
        print(f"   ⚠️ Error extracting row: {e}")
        return {"title": None, "date": None, "rating": None, "liked": False}


def scrape_diary_df(base_url):
    print(f"📽️ Scraping diary: {base_url}")
    
    try:
        total_pages = get_total_pages(base_url)
        print(f"   Total pages: {total_pages}")
        all_data = []

        for page in range(1, total_pages + 1):
            if page == 1:
                url = base_url + "/diary/films/"
            else:
                url = f"{base_url}/diary/films/page/{page}/"

            html = get_html(url)
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr", class_="diary-entry-row")
            print(f"   Page {page}: {len(rows)} entries")

            for row in rows:
                data = extract_row(row)
                if data["title"]:
                    all_data.append(data)

            time.sleep(1)

        if not all_data:
            print(f"   ⚠️ No diary data found - returning empty df with columns")
            return empty_diary_df()
        
        df = pd.DataFrame(all_data)
        df = df.drop_duplicates(subset=["title"], keep="last")
        
        # SAFETY: Verify columns exist
        for col in DIARY_COLUMNS:
            if col not in df.columns:
                df[col] = None
        
        print(f"   ✓ Total diary entries: {len(df)}")
        print(f"   ✓ Columns: {df.columns.tolist()}")
        return df
        
    except Exception as e:
        print(f"   ❌ Error scraping diary: {e}")
        return empty_diary_df()


def extract_profile(url):
    print(f"\n{'='*60}")
    print(f"🔍 Profile: {url}")
    print(f"{'='*60}")
    
    base = get_base_url(url)
    parts = [p for p in base.split("/") if p]
    username = parts[-1] if parts else "User"

    fav_df = scrape_favorites_df(base)
    diary_df = scrape_diary_df(base)
    
    # Final safety check
    if "title" not in diary_df.columns:
        print(f"⚠️ SAFETY: diary df missing 'title' column, fixing...")
        diary_df = empty_diary_df()
    
    if "title" not in fav_df.columns:
        print(f"⚠️ SAFETY: fav df missing 'title' column, fixing...")
        fav_df = empty_favorites_df()
    
    print(f"\n✅ RESULTS for {username}:")
    print(f"   Favorites: {len(fav_df)} (cols: {fav_df.columns.tolist()})")
    print(f"   Diary: {len(diary_df)} (cols: {diary_df.columns.tolist()})")
    print(f"{'='*60}\n")

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