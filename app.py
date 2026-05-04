import streamlit as st
import time
import threading
import html as html_lib

from scraper.letterboxd_extractor import (
    extract_default_profile,
    extract_user_profile
)

st.set_page_config(page_title="Letterboxd Blend", layout="wide")

# ---------------------------
# CUSTOM CSS — Spotify Dark
# ---------------------------
st.markdown("""
<style>
.stApp, [data-testid="stAppViewContainer"] { background-color: #0d0d0d; }
[data-testid="stHeader"] { background: transparent; }

.score-card {
    background: linear-gradient(160deg, #121212 0%, #0d1f0d 100%);
    border: 2px solid #1DB954;
    border-radius: 24px;
    padding: 60px 40px;
    text-align: center;
    box-shadow: 0 0 60px rgba(29,185,84,0.15);
    min-height: 340px;
}
.score-label {
    font-size: 12px;
    letter-spacing: 6px;
    color: #1DB954;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 16px;
}
.score-number {
    font-size: 110px;
    font-weight: 900;
    color: white;
    line-height: 1;
    margin: 10px 0;
}
.score-tagline { font-size: 20px; color: #b3b3b3; margin-top: 16px; font-style: italic; }
.score-names { font-size: 12px; color: #444; margin-top: 12px; letter-spacing: 2px; text-transform: uppercase; }

.common-card {
    background: #141414;
    border-radius: 20px;
    padding: 32px;
    border: 1px solid #222;
    min-height: 340px;
}
.common-count { font-size: 60px; font-weight: 900; color: #1DB954; line-height: 1; }
.common-sub { font-size: 12px; color: #666; margin-top: 6px; letter-spacing: 3px; text-transform: uppercase; }
.movie-pill {
    display: inline-block;
    background: rgba(29,185,84,0.1);
    color: #1DB954;
    border: 1px solid rgba(29,185,84,0.25);
    border-radius: 20px;
    padding: 5px 14px;
    margin: 4px;
    font-size: 13px;
    font-weight: 500;
}

.same-day-card {
    background: #141414;
    border-radius: 20px;
    padding: 32px;
    border: 2px solid #f39c12;
    min-height: 340px;
}
.same-day-item {
    background: rgba(243, 156, 18, 0.08);
    border-left: 4px solid #f39c12;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    font-size: 15px;
    color: #e0e0e0;
}
.same-day-date {
    color: #f39c12;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 1px;
}
.same-day-title {
    color: #fff;
    font-weight: 600;
    margin-top: 4px;
}

.winner-card {
    background: #141414;
    border-radius: 20px;
    padding: 40px;
    text-align: center;
    min-height: 340px;
}
.fav-card {
    background: #141414;
    border-radius: 20px;
    padding: 28px;
    border: 1px solid #222;
    min-height: 340px;
}
.fav-item {
    background: rgba(255,255,255,0.03);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 14px;
    color: #e0e0e0;
    font-weight: 500;
}

.loading-box {
    background: linear-gradient(135deg, #141414, #0d1f0d);
    border: 1px solid #1DB954;
    border-radius: 20px;
    padding: 56px 40px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)



LOADING_MESSAGES = [
    ("🍿", "Matching your taste..."),
    ("📽️", "Comparing films ..."),
    ("🎬", "Blending the movie worlds..."),
    ("⭐", "Counting those stars..."),
    ("🎭", "Analyzing your taste profile...")
]



for _k, _v in [
    ("source_loaded", False),
    ("user_loaded", False),
    ("slide", 0),
    ("score_animated", False),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---------------------------
# LOAD DEFAULT PROFILE
# ---------------------------
if not st.session_state.source_loaded:
    with st.spinner("Loading default profile..."):
        _name, _fav, _diary = extract_default_profile()
    st.session_state.source_name = _name
    st.session_state.source_fav = _fav
    st.session_state.source_diary = _diary
    st.session_state.source_loaded = True


# ---------------------------
# HEADER
# ---------------------------
st.markdown("# 🎬 Letterboxd Blend")
st.markdown(
    "<div style='color:#555; margin-bottom:28px; font-size:15px;'>"
    "Creating your movie blend</div>",
    unsafe_allow_html=True
)


# ---------------------------
# INPUT ROW
# ---------------------------
c_url, c_btn = st.columns([5, 1])
with c_url:
    user_url = st.text_input(
        "url",
        placeholder="https://letterboxd.com/username/",
        label_visibility="collapsed"
    )
with c_btn:
    blend_clicked = st.button("🎵 Blend", use_container_width=True)



if blend_clicked:
    if not user_url.strip():
        st.warning("Enter your Letterboxd URL")
    else:
        result_box: dict = {}
        error_box: dict = {}

        def _scrape():
            try:
                result_box["data"] = extract_user_profile(user_url)
            except Exception as exc:
                error_box["err"] = str(exc)

        thread = threading.Thread(target=_scrape, daemon=True)
        thread.start()

        loader_ph = st.empty()
        idx = 0
        while thread.is_alive():
            emoji, msg = LOADING_MESSAGES[idx % len(LOADING_MESSAGES)]
            loader_ph.markdown(f"""
            <div class="loading-box">
                <div style="font-size:56px">{emoji}</div>
                <div style="font-size:22px; color:white; font-weight:700; margin:14px 0 8px">{msg}</div>
                <div style="color:#444; font-size:13px">Hang tight…</div>
            </div>
            """, unsafe_allow_html=True)
            idx += 1
            time.sleep(2)

        thread.join()
        loader_ph.empty()

        if "err" in error_box:
            st.error(f"Could not load profile: {error_box['err']}")
        else:
            uname, ufav, udiary = result_box["data"]
            st.session_state.user_name = uname
            st.session_state.user_fav = ufav
            st.session_state.user_diary = udiary
            st.session_state.user_loaded = True
            st.session_state.slide = 0
            st.session_state.score_animated = False
            st.rerun()


# ---------------------------
# HELPERS
# ---------------------------
def compute_same_day_watches(s_df, u_df):
    s_clean = s_df.dropna(subset=["date"])
    u_clean = u_df.dropna(subset=["date"])
    s_pairs = set(zip(s_clean["date"], s_clean["title"]))
    u_pairs = set(zip(u_clean["date"], u_clean["title"]))
    
    same_day = s_pairs & u_pairs
    return sorted([{"date": date, "title": title} for date, title in same_day], 
                  key=lambda x: x["date"], reverse=True)


def compute_blend(s_df, u_df):
    s = set(s_df["title"])
    u = set(u_df["title"])
    common = s & u
    union = s | u
    
    # Base score from common movies
    base_score = int(len(common) / len(union) * 100) if union else 0
    
    # Bonus points for same-day watches (max +15 points)
    same_day_watches = compute_same_day_watches(s_df, u_df)
    same_day_bonus = min(len(same_day_watches) * 2, 15)
    
    final_score = min(base_score + same_day_bonus, 100)
    
    return final_score, sorted(list(common)), same_day_watches


def score_tagline(s):
    if s >= 80: return "Cinematic Soulmates 💫"
    if s >= 60: return "Film Kindred Spirits 🎬"
    if s >= 40: return "Decent Overlap 🎥"
    if s >= 20: return "Diverging Tastes 🎭"
    return "Two Different Worlds 🌍"


def fav_items_html(df, accent):
    if df.empty:
        return '<div style="color:#555; padding:20px; text-align:center">No favorites found</div>'
    out = ""
    for _, row in df.head(4).iterrows():
        title = row.get("title", "—")
        out += f'<div class="fav-item" style="border-left:3px solid {accent}">🎬 {title}</div>'
    return out


# ---------------------------
# RESULTS SLIDESHOW
# ---------------------------
if st.session_state.user_loaded:

    src_diary = st.session_state.source_diary
    usr_diary = st.session_state.user_diary
    score, common, same_day_watches = compute_blend(src_diary, usr_diary)

    SLIDES = ["Match Score", "Common Movies", "Same Day Watches", "Who Watched More", "Favorites"]
    cur = st.session_state.slide

    # ------ Slide Content ------
    slide_ph = st.empty()

    # SLIDE 0 — Match Score (animated on first view)
    if cur == 0:
        if not st.session_state.score_animated:
            for i in range(score + 1):
                slide_ph.markdown(f"""
                <div class="score-card">
                    <div class="score-label">🎯 Blend Score</div>
                    <div class="score-number">{i}%</div>
                    <div class="score-tagline">Calculating…</div>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(0.02)
            st.session_state.score_animated = True

        slide_ph.markdown(f"""
        <div class="score-card">
            <div class="score-label">🎯 Blend Score</div>
            <div class="score-number">{score}%</div>
            <div class="score-tagline">{score_tagline(score)}</div>
            <div class="score-names">
                {st.session_state.source_name} × {st.session_state.user_name}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # SLIDE 1 — Common Movies
    elif cur == 1:
        pills = "".join(
            f'<span class="movie-pill">🎬 {m}</span>' for m in common[:30]
        )
        more_txt = (
            f'<div style="color:#444; text-align:center; margin-top:12px; font-size:13px">'
            f'…and {len(common) - 30} more</div>'
            if len(common) > 30 else ""
        )
        empty_txt = (
            '<div style="color:#555; text-align:center; padding:30px; font-size:16px">'
            'No common movies yet 😢</div>'
            if not common else ""
        )
        slide_ph.markdown(f"""
        <div class="common-card">
            <div style="text-align:center; margin-bottom:24px">
                <div class="common-count">{len(common)}</div>
                <div class="common-sub">Movies in common</div>
            </div>
            <div style="text-align:center">{pills}{empty_txt}</div>
            {more_txt}
        </div>
        """, unsafe_allow_html=True)

    # SLIDE 2 — Same Day Watches
    elif cur == 2:
        if same_day_watches:
            items_html = "".join(
                f'<div style="background:rgba(243,156,18,0.08);border-left:4px solid #f39c12;border-radius:10px;padding:16px;margin-bottom:12px;">'
                f'<div style="color:#f39c12;font-weight:700;font-size:13px;letter-spacing:1px;">📅 {html_lib.escape(str(item["date"]))}</div>'
                f'<div style="color:#fff;font-weight:600;margin-top:4px;">🎬 {html_lib.escape(item["title"])}</div>'
                f'</div>'
                for item in same_day_watches[:8]
            )
            more_txt = (
                f'<div style="color:#666;text-align:center;margin-top:12px;font-size:13px;">…and {len(same_day_watches) - 8} more</div>'
                if len(same_day_watches) > 8 else ""
            )
        else:
            items_html = '<div style="color:#555;text-align:center;padding:40px;font-size:16px;">No movies watched on the same day yet 😢</div>'
            more_txt = ""

        slide_ph.markdown(
            f'<div style="background:#141414;border-radius:20px;padding:32px;border:2px solid #f39c12;min-height:340px;">'
            f'<div style="text-align:center;margin-bottom:24px;">'
            f'<div style="font-size:56px;">📅</div>'
            f'<div style="font-size:28px;font-weight:900;color:#f39c12;margin-top:8px;">{len(same_day_watches)}</div>'
            f'<div style="font-size:12px;color:#666;margin-top:4px;letter-spacing:2px;text-transform:uppercase;">Telepathic Viewings</div>'
            f'</div>{items_html}{more_txt}</div>',
            unsafe_allow_html=True
        )

    # SLIDE 3 — Who Watched More
    elif cur == 3:
        s_count = len(src_diary)
        u_count = len(usr_diary)
        sname = st.session_state.source_name
        uname = st.session_state.user_name

        if s_count > u_count:
            headline = f"🏆 {sname} IS A FILM MACHINE"
            sub = f"Watched {s_count - u_count} more films than {uname}. Absolute cinema devotee. 🍿"
            accent = "#1DB954"
            s_col, u_col = "#1DB954", "#e74c3c"
        elif u_count > s_count:
            headline = f"🔥 {uname} IS A Movie Buff"
            sub = f"{sname} has {u_count - s_count} films to catch up on. "
            accent = "#e74c3c"
            s_col, u_col = "#e74c3c", "#1DB954"
        else:
            headline = "⚖️ EQUALLY OBSESSED"
            sub = f"Both {sname} & {uname} clocked {s_count} films. A perfect cinematic Match! 🎭"
            accent = "#f39c12"
            s_col = u_col = "#f39c12"

        slide_ph.markdown(f"""
        <div class="winner-card" style="border:2px solid {accent};">
            <div style="font-size:56px; margin-bottom:16px">🎬</div>
            <div style="font-size:24px; font-weight:900; color:white; margin-bottom:12px">{headline}</div>
            <div style="font-size:15px; color:#888; margin-bottom:36px">{sub}</div>
            <div style="display:flex; justify-content:center; gap:80px">
                <div style="text-align:center">
                    <div style="font-size:52px; font-weight:900; color:{s_col}">{s_count}</div>
                    <div style="font-size:11px; color:#444; letter-spacing:2px; text-transform:uppercase; margin-top:6px">{sname}</div>
                </div>
                <div style="text-align:center">
                    <div style="font-size:52px; font-weight:900; color:{u_col}">{u_count}</div>
                    <div style="font-size:11px; color:#444; letter-spacing:2px; text-transform:uppercase; margin-top:6px">{uname}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # SLIDE 4 — Favorites
    elif cur == 4:
        sname = st.session_state.source_name
        uname = st.session_state.user_name
        src_items = fav_items_html(st.session_state.source_fav, "#1DB954")
        usr_items = fav_items_html(st.session_state.user_fav, "#e74c3c")

        slide_ph.markdown(f"""
        <div class="fav-card">
            <div style="text-align:center; margin-bottom:24px">
                <span style="font-size:20px; font-weight:700; color:white">⭐ Favorites Face-off</span>
                <div style="color:#444; font-size:13px; margin-top:4px">Top picks face-off</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:28px">
                <div>
                    <div style="color:#1DB954; font-weight:700; font-size:14px; text-align:center;
                                margin-bottom:14px; letter-spacing:1px">{sname}</div>
                    {src_items}
                </div>
                <div>
                    <div style="color:#e74c3c; font-weight:700; font-size:14px; text-align:center;
                                margin-bottom:14px; letter-spacing:1px">{uname}</div>
                    {usr_items}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ------ Navigation Bar ------
    st.write("")
    nav_l, nav_mid, nav_r = st.columns([2, 6, 2])

    with nav_l:
        if st.button("◀  Prev", disabled=(cur == 0), use_container_width=True):
            st.session_state.slide -= 1
            st.rerun()

    with nav_mid:
        dots = "".join(
            f'<span style="color:#1DB954; font-size:18px; margin:0 5px">●</span>'
            if i == cur else
            f'<span style="color:#2a2a2a; font-size:18px; margin:0 5px">●</span>'
            for i in range(len(SLIDES))
        )
        st.markdown(
            f'<div style="text-align:center; padding-top:6px">'
            f'{dots}<br>'
            f'<span style="color:#444; font-size:12px; letter-spacing:2px; text-transform:uppercase">'
            f'{SLIDES[cur]}</span></div>',
            unsafe_allow_html=True
        )

    with nav_r:
        if st.button("Next  ▶", disabled=(cur == len(SLIDES) - 1), use_container_width=True):
            st.session_state.slide += 1
            st.rerun()
