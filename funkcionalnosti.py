# funkcionalnosti.py
# Supabase integracija za Nutri Tracker aplikaciju

import os
from datetime import datetime, date
from typing import Dict, Optional
import pandas as pd
import requests
from dataclasses import dataclass
from io import BytesIO
from PIL import Image
from supabase import create_client, Client
from dotenv import load_dotenv

# Barkod skeniranje
try:
    from pyzbar.pyzbar import decode as zbar_decode
except Exception:
    zbar_decode = None

# ---------------------- KONFIGURACIJA SUPABASE ----------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------- KONSTANTE ----------------------
NUTRI_KEYS = [
    ("energy-kcal_100g", "kcal"),
    ("proteins_100g", "protein_g"),
    ("carbohydrates_100g", "carbs_g"),
    ("fat_100g", "fat_g"),
    ("sugars_100g", "sugars_g"),
    ("fiber_100g", "fiber_g"),
    ("salt_100g", "salt_g"),
]


@dataclass
class ProductInfo:
    name: str
    brand: Optional[str]
    barcode: Optional[str]
    serving_size: Optional[str]
    image_url: Optional[str]
    nutriments: Dict[str, float]


# ---------------------- PROFIL ----------------------
def read_profile() -> Dict:
    res = supabase.table("profile").select("*").execute()
    if not res.data:
        # ako nema profila, kreiraj default
        supabase.table("profile").insert({
            "name": "Korisnik",
            "target_kcal": 2000,
            "target_protein": 100,
            "target_carbs": 250,
            "target_fat": 70
        }).execute()
        return {"name": "Korisnik", "target_kcal": 2000, "target_protein": 100,
                "target_carbs": 250, "target_fat": 70}
    return res.data[0]


def update_profile(data: Dict):
    profiles = supabase.table("profile").select("id").execute()
    if not profiles.data:
        return
    profile_id = profiles.data[0]["id"]
    supabase.table("profile").update(data).eq("id", profile_id).execute()


# ---------------------- ENTRIES ----------------------
def add_entry(item_name: str, qty_g: float, nutr: Dict[str, float],
              barcode: Optional[str] = None, raw_json: Optional[Dict] = None,
              when: Optional[date] = None):
    if when is None:
        when = date.today()
    factor = qty_g / 100.0 if qty_g else 1.0
    kcal = float(nutr.get("kcal", 0)) * factor
    protein = float(nutr.get("protein_g", 0)) * factor
    carbs = float(nutr.get("carbs_g", 0)) * factor
    fat = float(nutr.get("fat_g", 0)) * factor
    sugars = float(nutr.get("sugars_g", 0)) * factor
    fiber = float(nutr.get("fiber_g", 0)) * factor
    salt = float(nutr.get("salt_g", 0)) * factor

    supabase.table("entries").insert({
        "entry_date": when.isoformat(),
        "item_name": item_name,
        "barcode": barcode,
        "qty_g": qty_g,
        "kcal": kcal,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "sugars": sugars,
        "fiber": fiber,
        "salt": salt,
        "raw_json": raw_json or {}
    }).execute()


def list_entries(for_date: Optional[date] = None) -> pd.DataFrame:
    query = supabase.table("entries").select("*").order("created_at", desc=True)
    if for_date:
        query = query.eq("entry_date", for_date.isoformat())
    res = query.execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


def delete_entry(entry_id: str):
    supabase.table("entries").delete().eq("id", entry_id).execute()


def daily_totals(for_date: Optional[date] = None) -> Dict[str, float]:
    if for_date is None:
        for_date = date.today()
    res = supabase.table("entries").select("kcal, protein, carbs, fat, sugars, fiber, salt") \
        .eq("entry_date", for_date.isoformat()).execute()
    if not res.data:
        return {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugars": 0, "fiber": 0, "salt": 0}
    df = pd.DataFrame(res.data)
    return df.sum(numeric_only=True).to_dict()


def range_stats(start: date, end: date) -> pd.DataFrame:
    res = supabase.table("entries").select("entry_date, kcal, protein, carbs, fat, sugars, fiber, salt") \
        .gte("entry_date", start.isoformat()).lte("entry_date", end.isoformat()).execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame()
    grouped = df.groupby("entry_date").sum(numeric_only=True).reset_index()
    grouped["entry_date"] = pd.to_datetime(grouped["entry_date"]).dt.date
    return grouped


# ---------------------- WEIGHT TRACKING ----------------------
def add_weight_entry(weight_kg: float, when: Optional[date] = None):
    if when is None:
        when = date.today()
    supabase.table("weights").insert({
        "weight_date": when.isoformat(),
        "weight_kg": weight_kg
    }).execute()


def get_weight_history() -> pd.DataFrame:
    res = supabase.table("weights").select("weight_date, weight_kg").order("weight_date", asc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["weight_date"] = pd.to_datetime(df["weight_date"]).dt.date
    return df


# ---------------------- API: OpenFoodFacts ----------------------
def fetch_openfoodfacts(barcode: str) -> Optional[ProductInfo]:
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if not data or data.get("status") != 1:
        return None
    p = data.get("product", {})
    nutriments = p.get("nutriments", {}) or {}
    result_nutr = {}
    for key, alias in NUTRI_KEYS:
        val = nutriments.get(key)
        if val is not None:
            try:
                result_nutr[alias] = float(val)
            except Exception:
                pass
    name = p.get("product_name") or p.get("generic_name") or "Nepoznat proizvod"
    return ProductInfo(
        name=name,
        brand=p.get("brands"),
        barcode=p.get("code") or barcode,
        serving_size=p.get("serving_size"),
        image_url=p.get("image_url"),
        nutriments=result_nutr
    )


# ---------------------- BARKOD SKENIRANJE ----------------------
def decode_barcode_from_image(image_bytes: bytes) -> Optional[str]:
    """Vrati EAN/UPC string iz slike; None ako ne pronađe ili ako pyzbar nije dostupan."""
    if zbar_decode is None:
        return None
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        results = zbar_decode(img)
        if not results:
            return None
        return results[0].data.decode("utf-8")
    except Exception:
        return None