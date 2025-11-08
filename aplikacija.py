# aplikacija.py
# CaloriesPal — Streamlit UI bez sidebara (kartice / tabovi)
# Povezano sa Supabase backendom

import streamlit as st
from datetime import date, timedelta
import plotly.graph_objects as go
import plotly.express as px
from funkcionalnosti import (
    read_profile, update_profile, add_weight_entry, get_weight_history,
    add_entry, list_entries, delete_entry, daily_totals, range_stats,
    fetch_openfoodfacts, decode_barcode_from_image
)

# ---------------------------------------------------------------------
st.set_page_config(page_title="CaloriesPal", page_icon="🥗", layout="wide")

# -------------------- Globalno stanje --------------------
if "camera_open" not in st.session_state:
    st.session_state["camera_open"] = False
if "last_barcode" not in st.session_state:
    st.session_state["last_barcode"] = None
if "last_product" not in st.session_state:
    st.session_state["last_product"] = None

# -------------------- CSS --------------------
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #0e1117; color: #fff; }
[data-testid="stHeader"] { background: transparent; }

.card {
    background: #1e222a;
    border-radius: 18px;
    padding: 25px;
    margin-bottom: 25px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.4);
}
.card h2, .card h3 { color: #f1f5f9; margin-top: 0; }

/* Tabs stil */
[data-baseweb="tab-list"] {
    justify-content: center;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}
[data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
    color: #ddd;
}
[data-baseweb="tab"]:hover {
    color: white;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: #fff !important;
    border-bottom: 3px solid #42b883;
}

/* Fullscreen kamera overlay */
.camera-overlay {
    position: fixed !important;
    inset: 0;
    width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.96);
    z-index: 9999;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 24px;
}
.camera-actions {
    position: fixed; top: 20px; right: 25px; z-index: 10000;
}
.camera-close-btn {
    background: #ff4b4b; color: #fff; border: none;
    border-radius: 12px; padding: 10px 16px; cursor: pointer;
    font-weight: 600;
}
.camera-close-btn:hover { background: #ff2e2e; }
</style>
""", unsafe_allow_html=True)

# -------------------- Pomoćne funkcije --------------------
def ring_chart(current, target, label):
    if target is None or target <= 0:
        target = 1
    remaining = max(target - current, 0)
    fig = go.Figure(data=[go.Pie(
        values=[current, remaining],
        labels=[f"Potrošeno {label}", f"Preostalo {label}"],
        hole=0.7,
        sort=False
    )])
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
    fig.update_traces(textinfo="none")
    fig.add_annotation(
        text=f"{int(current)}/{int(target)}",
        x=0.5, y=0.5, showarrow=False, font_size=16, font_color="white"
    )
    return fig

def show_day_rings(totals, profile):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    cols = st.columns(4)
    with cols[0]:
        st.subheader("Kalorije")
        st.plotly_chart(ring_chart(totals.get("kcal", 0), profile.get("target_kcal", 2000), "kcal"),
                        use_container_width=True, key="ring_kcal")
    with cols[1]:
        st.subheader("Proteini (g)")
        st.plotly_chart(ring_chart(totals.get("kcal", 0), profile.get("target_kcal", 2000), "kcal"), use_container_width=True, key="ring_kcal")
    with cols[2]:
        st.subheader("Ugljikohidrati (g)")
        st.plotly_chart(ring_chart(totals.get("kcal", 0), profile.get("target_kcal", 2000), "kcal"), use_container_width=True, key="ring_kcal")
    with cols[3]:
        st.subheader("Masti (g)")
        st.plotly_chart(ring_chart(totals.get("kcal", 0), profile.get("target_kcal", 2000), "kcal"), use_container_width=True, key="ring_kcal")
    st.markdown('</div>', unsafe_allow_html=True)

def camera_overlay():
    """Fullscreen kamera overlay"""
    st.markdown('<div class="camera-overlay">', unsafe_allow_html=True)
    st.markdown('<div class="camera-actions"><button class="camera-close-btn" onclick="window.parent.location.reload()">Zatvori</button></div>', unsafe_allow_html=True)
    img = st.camera_input("📷 Slikaj barkod", key="camera_fullscreen")
    if img is not None:
        image_bytes = img.getvalue()
        code = decode_barcode_from_image(image_bytes)
        if code:
            st.session_state["last_barcode"] = code
            st.session_state["camera_open"] = False
            st.success(f"✅ Barkod: {code}")
            st.experimental_rerun()
        else:
            st.warning("❌ Barkod nije prepoznat. Pokušaj ponovno.")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Profil --------------------
profile = read_profile()
today = date.today()

# -------------------- Gornji Tabs --------------------
tabs = st.tabs(["📒 Dnevnik", "📷 Barkod / Kamera", "✍️ Ručni unos", "📊 Statistika", "👤 Profil", "⚖️ Težina"])

# -------------------- Dnevnik --------------------
with tabs[0]:
    st.header("📒 Dnevnik unosa")
    selected_date = st.date_input("Datum", value=today)
    totals = daily_totals(selected_date)
    show_day_rings(totals, profile)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Unosi za dan")
    df = list_entries(selected_date)
    if df.empty:
        st.info("Nema unosa za odabrani dan.")
    else:
        st.dataframe(df, use_container_width=True)
        ids = df["id"].tolist()
        del_id = st.selectbox("Odaberi unos za brisanje", options=[None] + ids, format_func=lambda x: "—" if x is None else f"#{x}")
        if del_id and st.button("Obriši odabrani unos", type="primary"):
            delete_entry(str(del_id))
            st.success("Unos obrisan!")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Barkod / Kamera --------------------
with tabs[1]:
    st.header("📷 Dodaj putem barkoda")

    if st.session_state["camera_open"]:
        camera_overlay()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("📸 Pokreni kameru (fullscreen)", on_click=lambda: st.session_state.update({"camera_open": True}), type="primary")
    with c2:
        barcode_manual = st.text_input("Ili unesi barkod ručno", value=st.session_state["last_barcode"] or "")
    barcode = barcode_manual.strip() or st.session_state["last_barcode"]

    if barcode:
        if st.button("Dohvati podatke s OpenFoodFacts"):
            p = fetch_openfoodfacts(barcode)
            if not p:
                st.error("Proizvod nije pronađen.")
            else:
                st.success(f"Nađen: {p.name} ({p.brand or 'N/A'})")
                st.json(p.nutriments)
                qty = st.number_input("Količina (g/ml)", min_value=0.0, value=100.0, step=10.0)
                if st.button("Dodaj u dnevnik"):
                    add_entry(item_name=p.name, qty_g=qty, nutr=p.nutriments, barcode=barcode, raw_json=p.__dict__)
                    st.success("✅ Dodano u dnevnik!")
                    st.session_state["last_barcode"] = None
    else:
        st.info("📱 Pokreni kameru ili unesi barkod ručno.")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Ručni unos --------------------
with tabs[2]:
    st.header("✍️ Ručni unos")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    with st.form("manual_add"):
        item_name = st.text_input("Naziv unosa", value="Hrana/piće")
        qty = st.number_input("Količina (g/ml)", min_value=0.0, value=100.0, step=10.0)
        c1, c2, c3 = st.columns(3)
        with c1:
            kcal = st.number_input("kcal / 100g", value=100.0)
            protein = st.number_input("Proteini g / 100g", value=5.0)
        with c2:
            carbs = st.number_input("Ugljikohidrati g / 100g", value=10.0)
            fat = st.number_input("Masti g / 100g", value=3.0)
        with c3:
            sugars = st.number_input("Šećeri g / 100g", value=5.0)
            fiber = st.number_input("Vlakna g / 100g", value=2.0)
        salt = st.number_input("Sol g / 100g", value=0.5)
        submitted = st.form_submit_button("Dodaj u dnevnik")
        if submitted:
            nutr = {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat,
                    "sugars_g": sugars, "fiber_g": fiber, "salt_g": salt}
            add_entry(item_name=item_name, qty_g=qty, nutr=nutr, barcode=None, raw_json=None)
            st.success("✅ Dodano!")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Statistika --------------------
with tabs[3]:
    st.header("📊 Statistika")
    selected_date = st.date_input("Datum", value=today, key="stats_date")
    totals = daily_totals(selected_date)
    show_day_rings(totals, profile)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    start = st.date_input("Od", value=today - timedelta(days=14))
    end = st.date_input("Do", value=today)
    if start <= end:
        df = range_stats(start, end)
        if df.empty:
            st.info("Nema podataka u rasponu.")
        else:
            st.dataframe(df, use_container_width=True)
            st.plotly_chart(px.line(df, x="entry_date", y="kcal", title="Dnevne kalorije"), use_container_width=True)
    else:
        st.warning("Pogrešan raspon datuma.")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Profil --------------------
with tabs[4]:
    st.header("👤 Profil i ciljevi")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    with st.form("profile_form"):
        name = st.text_input("Ime", value=profile.get("name", "Korisnik"))
        c1, c2, c3 = st.columns(3)
        with c1:
            target_kcal = st.number_input("Cilj kalorija (kcal)", value=float(profile.get("target_kcal", 2000)))
            target_protein = st.number_input("Cilj proteina (g)", value=float(profile.get("target_protein", 100)))
        with c2:
            target_carbs = st.number_input("Cilj ugljikohidrata (g)", value=float(profile.get("target_carbs", 250)))
            target_fat = st.number_input("Cilj masti (g)", value=float(profile.get("target_fat", 70)))
        with c3:
            target_sugars = st.number_input("Cilj šećera (g)", value=float(profile.get("target_sugars", 50)))
            target_salt = st.number_input("Cilj soli (g)", value=float(profile.get("target_salt", 5)))
        if st.form_submit_button("Spremi"):
            update_profile({
                "name": name,
                "target_kcal": target_kcal,
                "target_protein": target_protein,
                "target_carbs": target_carbs,
                "target_fat": target_fat,
                "target_sugars": target_sugars,
                "target_salt": target_salt,
            })
            st.success("✅ Profil ažuriran.")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Težina --------------------
with tabs[5]:
    st.header("⚖️ Praćenje težine")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    w = st.number_input("Unesi trenutnu težinu (kg)", min_value=0.0, value=0.0, step=0.1)
    if st.button("Dodaj težinu"):
        if w > 0:
            add_weight_entry(w)
            st.success("✅ Dodano!")
        else:
            st.warning("Upiši vrijednost veću od 0.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    dfw = get_weight_history()
    if dfw.empty:
        st.info("Još nema zapisa.")
    else:
        st.plotly_chart(px.line(dfw, x="weight_date", y="weight_kg", markers=True, title="Promjena težine"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------- Footer --------------------
st.caption("© 2025 CaloriesPal — minimalistička aplikacija za praćenje prehrane i težine.")