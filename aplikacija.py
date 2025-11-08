# aplikacija.py
# Streamlit UI za Nutri Tracker aplikaciju (Supabase backend)

import streamlit as st
from datetime import date, timedelta
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from funkcionalnosti import (
    read_profile, update_profile, add_weight_entry, get_weight_history,
    add_entry, list_entries, delete_entry, daily_totals, range_stats,
    fetch_openfoodfacts, decode_barcode_from_image
)

# ---------------------------------------------------------------------
st.set_page_config(page_title="Nutri Tracker", page_icon="🥗", layout="wide")

st.sidebar.title("🥗 Nutri Tracker")
page = st.sidebar.radio(
    "Navigacija",
    ["Dnevnik", "Dodaj (barkod/kamera)", "Dodaj (ručno)", "Statistika", "Profil", "Težina"],
    index=0
)

selected_date = st.sidebar.date_input("Datum", value=date.today())

# ---------------------------------------------------------------------
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
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        annotations=[
            dict(
                text=f"{int(current)}/{int(target)}",
                x=0.5,
                y=0.5,
                font_size=16,
                showarrow=False
            )
        ]
    )
    return fig


def show_day_rings(totals, profile):
    cols = st.columns(4)
    with cols[0]:
        st.subheader("Kalorije")
        st.plotly_chart(ring_chart(totals.get("kcal", 0), profile.get("target_kcal", 2000), "kcal"), use_container_width=True)
    with cols[1]:
        st.subheader("Proteini (g)")
        st.plotly_chart(ring_chart(totals.get("protein", 0), profile.get("target_protein", 100), "g"), use_container_width=True)
    with cols[2]:
        st.subheader("Ugljikohidrati (g)")
        st.plotly_chart(ring_chart(totals.get("carbs", 0), profile.get("target_carbs", 250), "g"), use_container_width=True)
    with cols[3]:
        st.subheader("Masti (g)")
        st.plotly_chart(ring_chart(totals.get("fat", 0), profile.get("target_fat", 70), "g"), use_container_width=True)

# ---------------------------------------------------------------------
profile = read_profile()

# ----------------------------- STRANICE -------------------------------
if page == "Dnevnik":
    st.title("📒 Dnevnik unosa")
    totals = daily_totals(selected_date)
    show_day_rings(totals, profile)
    st.markdown("### Unosi za dan")
    df = list_entries(selected_date)
    if df.empty:
        st.info("Nema unosa za odabrani dan.")
    else:
        st.dataframe(
            df[["id", "created_at", "item_name", "qty_g", "kcal", "protein", "carbs", "fat", "sugars", "fiber", "salt"]],
            use_container_width=True
        )
        ids = df["id"].tolist()
        del_id = st.selectbox("Odaberi unos za brisanje", options=[None] + ids, format_func=lambda x: "—" if x is None else f"#{x}")
        if del_id and st.button("Obriši odabrani unos", type="primary"):
            delete_entry(str(del_id))
            st.success("Unos obrisan! Osvježi prikaz promjenom datuma.")

# ---------------------------------------------------------------------
elif page == "Dodaj (barkod/kamera)":
    st.title("📷 Dodaj putem barkoda")
    st.caption("Možeš koristiti kameru (desktop/mobitel) ili ručni unos barkoda.")

    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.camera_input("Slikaj barkod")
        barcode_cam = None
        if uploaded is not None:
            bytes_data = uploaded.getvalue()
            code = decode_barcode_from_image(bytes_data)
            if code:
                st.success(f"Pronađen barkod: **{code}**")
                barcode_cam = code
            else:
                st.warning("Nije moguće prepoznati barkod sa slike. Pokušaj ponovno ili unesi ručno.")

    with col2:
        barcode_manual = st.text_input("Ili upiši barkod ručno (EAN/UPC)")

    barcode = barcode_cam or barcode_manual
    if barcode:
        if st.button("Dohvati podatke s OpenFoodFacts"):
            p = fetch_openfoodfacts(barcode)
            if not p:
                st.error("Proizvod nije pronađen.")
            else:
                st.success(f"Nađen: {p.name} ({p.brand or 'N/A'})")
                st.write("Nutritivne vrijednosti (na 100 g/ml):")
                st.json(p.nutriments)
                qty = st.number_input("Količina (g/ml)", min_value=0.0, value=100.0, step=10.0)
                item_name = st.text_input("Naziv unosa", value=p.name)
                if st.button("Dodaj u dnevnik"):
                    add_entry(item_name=item_name, qty_g=qty, nutr=p.nutriments, barcode=barcode, raw_json=p.__dict__)
                    st.success("Dodano u dnevnik!")

# ---------------------------------------------------------------------
elif page == "Dodaj (ručno)":
    st.title("✍️ Ručni unos")
    with st.form("manual_add"):
        item_name = st.text_input("Naziv unosa", value="Hrana/piće")
        qty = st.number_input("Količina (g/ml)", min_value=0.0, value=100.0, step=10.0)
        c1, c2, c3 = st.columns(3)
        with c1:
            kcal = st.number_input("kcal / 100g", min_value=0.0, value=100.0, step=1.0)
            protein = st.number_input("Proteini g / 100g", min_value=0.0, value=5.0, step=0.5)
        with c2:
            carbs = st.number_input("Ugljikohidrati g / 100g", min_value=0.0, value=10.0, step=0.5)
            fat = st.number_input("Masti g / 100g", min_value=0.0, value=3.0, step=0.5)
        with c3:
            sugars = st.number_input("Šećeri g / 100g", min_value=0.0, value=5.0, step=0.5)
            fiber = st.number_input("Vlakna g / 100g", min_value=0.0, value=2.0, step=0.5)
        salt = st.number_input("Sol g / 100g", min_value=0.0, value=0.5, step=0.1)
        submitted = st.form_submit_button("Dodaj u dnevnik")
        if submitted:
            nutr = {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat,
                    "sugars_g": sugars, "fiber_g": fiber, "salt_g": salt}
            add_entry(item_name=item_name, qty_g=qty, nutr=nutr, barcode=None, raw_json=None)
            st.success("Dodano!")

# ---------------------------------------------------------------------
elif page == "Statistika":
    st.title("📊 Statistika")
    totals = daily_totals(selected_date)
    st.subheader(f"Pregled za {selected_date.isoformat()}")
    show_day_rings(totals, profile)

    st.markdown("---")
    st.subheader("Po danima (raspon)")
    start = st.date_input("Od", value=date.today() - timedelta(days=14))
    end = st.date_input("Do", value=date.today())

    if start > end:
        st.warning("Početni datum mora biti prije završnog.")
    else:
        df = range_stats(start, end)
        if df.empty:
            st.info("Nema podataka u odabranom rasponu.")
        else:
            st.dataframe(df, use_container_width=True)
            tabs = st.tabs(["Kalorije", "Proteini", "Ugljikohidrati", "Masti"])
            with tabs[0]:
                st.plotly_chart(px.line(df, x="entry_date", y="kcal", markers=True), use_container_width=True)
            with tabs[1]:
                st.plotly_chart(px.line(df, x="entry_date", y="protein", markers=True), use_container_width=True)
            with tabs[2]:
                st.plotly_chart(px.line(df, x="entry_date", y="carbs", markers=True), use_container_width=True)
            with tabs[3]:
                st.plotly_chart(px.line(df, x="entry_date", y="fat", markers=True), use_container_width=True)

# ---------------------------------------------------------------------
elif page == "Profil":
    st.title("👤 Profil i ciljevi")
    with st.form("profile_form"):
        name = st.text_input("Ime", value=profile.get("name", "Korisnik"))
        c1, c2, c3 = st.columns(3)
        with c1:
            target_kcal = st.number_input("Cilj kalorija (kcal/dan)", min_value=500.0, value=float(profile.get("target_kcal", 2000)))
            target_protein = st.number_input("Cilj proteina (g/dan)", min_value=0.0, value=float(profile.get("target_protein", 100)))
            height_cm = st.number_input("Visina (cm)", min_value=0.0, value=float(profile.get("height_cm") or 0.0))
        with c2:
            target_carbs = st.number_input("Cilj ugljikohidrata (g/dan)", min_value=0.0, value=float(profile.get("target_carbs", 250)))
            target_fat = st.number_input("Cilj masti (g/dan)", min_value=0.0, value=float(profile.get("target_fat", 70)))
            weight_kg = st.number_input("Težina (kg)", min_value=0.0, value=float(profile.get("weight_kg") or 0.0))
        with c3:
            target_fiber = st.number_input("Cilj vlakana (g/dan)", min_value=0.0, value=float(profile.get("target_fiber", 30)))
            target_sugars = st.number_input("Cilj šećera (g/dan)", min_value=0.0, value=float(profile.get("target_sugars", 50)))
            target_salt = st.number_input("Cilj soli (g/dan)", min_value=0.0, value=float(profile.get("target_salt", 5)))

        submitted = st.form_submit_button("Spremi profil")
        if submitted:
            update_profile({
                "name": name,
                "target_kcal": target_kcal,
                "target_protein": target_protein,
                "target_carbs": target_carbs,
                "target_fat": target_fat,
                "target_fiber": target_fiber,
                "target_sugars": target_sugars,
                "target_salt": target_salt,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
            })
            st.success("Profil ažuriran!")

# ---------------------------------------------------------------------
elif page == "Težina":
    st.title("⚖️ Praćenje težine")
    w = st.number_input("Unesi trenutnu težinu (kg)", min_value=0.0, value=0.0, step=0.1)
    if st.button("Dodaj težinu"):
        if w > 0:
            add_weight_entry(w)
            st.success("Dodano!")
        else:
            st.warning("Upiši vrijednost veću od 0.")

    dfw = get_weight_history()
    if dfw.empty:
        st.info("Još nema zapisa o težini.")
    else:
        st.dataframe(dfw, use_container_width=True)
        st.plotly_chart(px.line(dfw, x="weight_date", y="weight_kg", markers=True), use_container_width=True)

# ---------------------------------------------------------------------
st.caption("© Nutri Tracker — privatna aplikacija za praćenje prehrane i težine.")