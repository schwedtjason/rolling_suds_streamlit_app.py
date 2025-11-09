import json
import csv
from datetime import datetime
from pathlib import Path
import streamlit as st
from typing import Dict, List
import math

# Page + Theme
st.set_page_config(page_title="Rolling Suds — Instant Quote", page_icon="🧼", layout="wide")

st.markdown(
    """
    <style>
      .rs-hero {padding: 8px 0 12px 0;}
      .rs-card {background: #0F172A; padding: 16px 16px; border-radius: 12px; border: 1px solid #1F2937;}
      .rs-subtle {color:#9CA3AF; font-size:13px}
      .rs-cta button {width:100%}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="rs-hero">
      <h2>Rolling Suds • Instant Quote</h2>
      <div class="rs-subtle">Click to choose — no manual typing required.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

CFG_PATH = Path(__file__).with_name("pricing_config.json")
with CFG_PATH.open("r", encoding="utf-8") as f:
    CFG = json.load(f)

# Options (driven by config for consistency)
PROPERTY_TYPES = list(CFG["base_rates_per_ft2"].keys())
SIZE_BANDS = list(CFG["size_midpoints_ft2"].keys())
STORIES = list(CFG["story_multiplier"].keys())
SURFACES = list(CFG["surface_multiplier"].keys())
GRIME = list(CFG["grime_multiplier"].keys())
ADDON_RATES = CFG["addons_flat"]
ADD_ONS = [{"key": k, "label": {
    "sidewalks":"Sidewalks/Entries","dumpster":"Dumpster Pad","awnings":"Awnings",
    "windows":"Exterior Windows","parking":"Parking Lanes"
}.get(k, k.title())} for k in ADDON_RATES.keys()]
FREQUENCY = list(CFG["frequency_discounts"].keys())
JOB_CATEGORIES = list(CFG["job_categories"].keys())


def calc_quote(sel: Dict) -> Dict:
    area = CFG["size_midpoints_ft2"][sel["size"]]
    base_rate = CFG["base_rates_per_ft2"][sel["ptype"]]
    base = base_rate * area

    # Core multipliers
    price = (
        base
        * CFG["grime_multiplier"][sel["grime"]]
        * CFG["story_multiplier"][sel["stories"]]
        * CFG["surface_multiplier"][sel["surface"]]
    )

    # Size discount
    size_disc = 1.0 + CFG["size_discounts"][sel["size"]]
    price *= size_disc

    # Add-ons
    add_total = sum(ADDON_RATES[k] for k, v in sel["addons"].items() if v)

    # Materials (chemicals)
    cons_per_1000 = CFG["materials"]["consumption_gal_per_1000ft2"][sel["surface"]]
    gallons = (area / 1000.0) * cons_per_1000
    materials_cost = gallons * CFG["materials"]["cost_per_gal"]

    # Travel
    extra_miles = max(0, int(sel["miles"]) - int(CFG["travel"]["included_miles"]))
    travel_cost = extra_miles * float(CFG["travel"]["per_mile_fee"])

    # Water
    water_cost = CFG["water"]["bring_water_fee"] if sel["needs_water"] else 0.0
    water_disc_mult = 1.0 + (CFG["water"]["on_site_water_discount_pct"] if not sel["needs_water"] else 0.0)

    # Lift
    lift_cost = float(CFG["lift"]["hourly_rate"]) * float(sel["lift_hours"]) if sel.get("use_lift") else 0.0

    # Frequency
    freq_mult = 1.0 + CFG["frequency_discounts"][sel["frequency"]]

    # Rush/weekend
    rush_mult = 1.0 + (CFG["rush_weekend"]["rush_pct"] if sel.get("rush") else 0.0)
    weekend_mult = 1.0 + (CFG["rush_weekend"]["weekend_pct"] if sel.get("weekend") else 0.0)

    core = price * water_disc_mult
    subtotal = core + add_total
    discounted = subtotal * freq_mult

    extras = materials_cost + travel_cost + water_cost + lift_cost
    with_surcharges = discounted * rush_mult * weekend_mult + extras

    total = max(CFG["min_charge"], round(with_surcharges, 2))
    return {
        "area": area,
        "base": round(base, 2),
        "addons": round(add_total, 2),
        "materials": round(materials_cost, 2),
        "travel": round(travel_cost, 2),
        "water": round(water_cost, 2),
        "lift": round(lift_cost, 2),
        "subtotal": round(subtotal, 2),
        "discounted": round(discounted, 2),
        "extras": round(extras, 2),
        "total": total,
    }


def calc_production_quote(sel: Dict) -> Dict:
    area = CFG["size_midpoints_ft2"][sel["size"]]
    job_cfg = CFG["job_categories"][sel["job_category"]]
    prod_rate = job_cfg["production_ft2_per_hour"][sel["grime"]]
    # Adjust production for surface and stories (slower if multipliers > 1)
    surface_factor = CFG["surface_multiplier"][sel["surface"]]
    story_factor = CFG["story_multiplier"][sel["stories"]]
    effective_rate = prod_rate / (surface_factor * story_factor)

    crew_size = int(sel["crew_size"])
    # Use user-selected daily hours if provided; fallback to config
    daily_hours = float(sel.get("daily_hours") or CFG["crew"]["hours_per_day"])
    crew_hours_per_day = max(1.0, daily_hours) * crew_size
    hours_required = area / max(1.0, effective_rate)
    days = hours_required / max(1.0, crew_hours_per_day)

    # Day target selection (high-rise uses slider)
    if "day_target" in job_cfg:
        day_target = job_cfg["day_target"]
    else:
        day_target = float(sel.get("hi_day_target", job_cfg.get("day_target_min", 3500)))

    base_price = day_target * days

    # Frequency
    freq_mult = 1.0 + CFG["frequency_discounts"][sel["frequency"]]

    # Travel
    extra_miles = max(0, int(sel["miles"]) - int(CFG["travel"]["included_miles"]))
    travel_cost = extra_miles * float(CFG["travel"]["per_mile_fee"])

    # Water: bring water fee; if not, small discount applied to base
    water_cost = CFG["water"]["bring_water_fee"] if sel["needs_water"] else 0.0
    water_disc_mult = 1.0 + (CFG["water"]["on_site_water_discount_pct"] if not sel["needs_water"] else 0.0)

    # Add-ons, Materials, Lift (reuse logic similar to calc_quote)
    add_total = sum(ADDON_RATES[k] for k, v in sel["addons"].items() if v)

    cons_per_1000 = CFG["materials"]["consumption_gal_per_1000ft2"][sel["surface"]]
    gallons = (area / 1000.0) * cons_per_1000
    materials_cost = gallons * CFG["materials"]["cost_per_gal"]

    lift_cost = float(CFG["lift"]["hourly_rate"]) * float(sel["lift_hours"]) if sel.get("use_lift") else 0.0

    rush_mult = 1.0 + (CFG["rush_weekend"]["rush_pct"] if sel.get("rush") else 0.0)
    weekend_mult = 1.0 + (CFG["rush_weekend"]["weekend_pct"] if sel.get("weekend") else 0.0)

    core = base_price * water_disc_mult
    core *= freq_mult
    with_surcharges = core * rush_mult * weekend_mult

    extras = add_total + materials_cost + travel_cost + water_cost + lift_cost
    total = max(CFG["min_charge"], round(with_surcharges + extras, 2))

    return {
        "area": int(area),
        "days": round(days, 2),
        "crew_hours_day": crew_hours_per_day,
        "day_target": round(day_target, 2),
        "addons": round(add_total, 2),
        "materials": round(materials_cost, 2),
        "travel": round(travel_cost, 2),
        "water": round(water_cost, 2),
        "lift": round(lift_cost, 2),
        "extras": round(extras, 2),
        "total": total,
    }


def segmented(label: str, options: List[str], key: str, default_index: int = 0) -> str:
    return st.segmented_control(label, options=options, default=options[default_index], key=key)  # type: ignore[attr-defined]


with st.sidebar:
    st.markdown("##### Compare Others")
    st.caption("Open common instant-quote pages:")
    links = {
        "Platinum Pressure Washing LLC": "https://platinumpressurewashingllc.com/instant-online-estimate/",
        "Insta-Brite": "https://instabrite.com/get-a-quote-in-seconds-online-24-7/",
        "Perfect Power Wash": "https://www.perfectpowerwash.com/get-a-quote/",
        "Shine": "https://shine-windowcleaning.com/instant-quote/",
    }
    for name, url in links.items():
        st.markdown(f"- [{name}]({url})")

    st.markdown("---")
    st.markdown("##### Your Info")
    name = st.text_input("Name")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    frequency = st.selectbox("Service frequency", FREQUENCY, index=0)

    st.markdown("---")
    st.markdown("##### Job Options")
    miles = st.number_input("Travel distance (mi)", min_value=0, max_value=500, value=10, step=1)
    needs_water = st.toggle("We need to bring water", value=False)
    weekend = st.toggle("Weekend work", value=False)
    rush = st.toggle("Rush job (<48h)", value=False)
    use_lift = st.toggle("Lift required", value=False)
    lift_hours = st.number_input("Lift hours", min_value=0.0, max_value=48.0, value=0.0, step=0.5, disabled=not use_lift)

    st.markdown("---")
    with st.expander("Training & Guides"):
        st.markdown("###### Temperature & Dilution Guide")
        temp = st.slider("Estimated surface temperature (°F)", 30, 110, 75)
        if temp >= 95:
            dilution = "75% water / 25% chem"
        elif temp >= 75:
            dilution = "50% water / 50% chem"
        elif temp >= 60:
            dilution = "25% water / 75% chem"
        else:
            dilution = "15% water / 85% chem"
        st.write(f"Recommended dilution at {temp}°F: {dilution}")

        st.markdown("###### Job Type Training Videos")
        job_video = st.selectbox(
            "Select job type",
            ["Apartment Complex", "Casino", "Retail Strip Mall", "Office Building", "HOA Community", "Parking Garage"],
        )
        video_links = {
            "Apartment Complex": "https://www.loom.com/embed/6a6a50ea166c41e49e1566bbe3d6f157",
            "Casino": "https://youtu.be/casino_video_link",
            "Retail Strip Mall": "https://youtu.be/retail_video_link",
            "Office Building": "https://youtu.be/office_video_link",
            "HOA Community": "https://www.loom.com/embed/6a6a50ea166c41e49e1566bbe3d6f157",
            "Parking Garage": "https://youtu.be/eOawmJEGJk8",
        }
        url = video_links.get(job_video)
        if url:
            if "loom.com" in url:
                st.markdown(
                    f'<iframe src="{url}" frameborder="0" allowfullscreen style="width:100%;height:320px;"></iframe>',
                    unsafe_allow_html=True,
                )
            else:
                st.video(url)
        st.caption("We can replace these placeholders with your internal videos.")


left, right = st.columns([7, 5])
with left:
    st.subheader("Your Project")
    job_category = segmented("Job category", JOB_CATEGORIES, key="job_cat", default_index=0)
    ptype = segmented("Property type", PROPERTY_TYPES, key="ptype")
    size = segmented("Building size", SIZE_BANDS, key="size", default_index=1)
    stories = segmented("Stories", STORIES, key="stories")
    surface = segmented("Primary surface", SURFACES, key="surface", default_index=0)
    grime = segmented("Soiling level", GRIME, key="grime", default_index=1)
    crew_size = st.slider("Crew size", min_value=1, max_value=6, value=int(CFG["crew"]["default_size"]), step=1)

    st.markdown("###### Experience & Build-up")
    exp_level = st.radio("Experience level", ["Novice", "Medium", "Expert"], horizontal=True)
    buildup = st.radio("Build-up", ["Light", "Medium", "Heavy"], horizontal=True)

    st.markdown("###### Add‑ons")
    add_cols = st.columns(5)
    addon_state: Dict[str, bool] = {}
    for i, item in enumerate(ADD_ONS):
        with add_cols[i % 5]:
            addon_state[item["key"]] = st.toggle(item["label"], value=False, key=f"add_{item['key']}")

with right:
    st.subheader("Quote")
    # Labor & trucks block
    st.markdown("###### Labor & Trucks")
    state = st.selectbox("State", ["Default (No OT)", "California"], index=0)
    daily_hours = st.slider("Daily work hours (per tech)", 4.0, 12.0, 8.0, 0.5)
    trucks = st.slider("Number of trucks", 1, 9, max(1, math.ceil(crew_size / 2)))
    lead_rate = st.number_input("Lead tech hourly rate ($)", min_value=0.0, value=21.0, step=0.5)
    jr_rate = st.number_input("Jr tech hourly rate ($)", min_value=0.0, value=19.0, step=0.5)
    if state == "California" and daily_hours > 8:
        st.warning("Overtime: Daily hours exceed 8 — CA OT rules apply.")

    pricing_mode = segmented("Pricing mode", ["Smart", "Ft²", "Production"], key="price_mode", default_index=0)
    hi_day_target = None
    if job_category == "High-Rise (4+ stories)":
        jc = CFG["job_categories"][job_category]
        hi_day_target = st.slider(
            "High‑rise target per day ($)",
            min_value=int(jc["day_target_min"]),
            max_value=int(jc["day_target_max"]),
            value=int((jc["day_target_min"] + jc["day_target_max"]) / 2),
            step=100,
        )
    selection = {
        "job_category": job_category,
        "ptype": ptype,
        "size": size,
        "stories": stories,
        "surface": surface,
        "grime": grime,
        "frequency": frequency,
        "addons": addon_state,
        "miles": miles,
        "needs_water": needs_water,
        "weekend": weekend,
        "rush": rush,
        "use_lift": use_lift,
        "lift_hours": float(lift_hours),
        "crew_size": int(crew_size),
        "hi_day_target": hi_day_target,
        "exp_level": exp_level,
        "buildup": buildup,
        "state": state,
        "daily_hours": float(daily_hours),
        "trucks": int(trucks),
        "lead_rate": float(lead_rate),
        "jr_rate": float(jr_rate),
    }
    ft2_quote = calc_quote(selection)
    prod_quote = calc_production_quote(selection)

    if pricing_mode == "Ft²":
        quote = ft2_quote
        basis = "Ft²-based"
    elif pricing_mode == "Production":
        quote = prod_quote
        basis = "Production target"
    else:
        quote = ft2_quote if ft2_quote["total"] >= prod_quote["total"] else prod_quote
        basis = "Smart (max of Ft² / Production)"

    st.markdown(
        f"""
        <div class="rs-card">
          <div class="rs-subtle">Estimated area</div>
          <h3>{quote['area']:,} ft²</h3>
          <div class="rs-subtle">{basis}</div>
          <h4>Extras ${quote['extras']:,}</h4>
          <hr/>
          <div class="rs-subtle">Subtotal</div>
          <h4>${quote.get('subtotal', 0):,}</h4>
          <div class="rs-subtle">After frequency</div>
          <h4>${quote.get('discounted', 0):,}</h4>
          <hr/>
          <h2>Total (min ${CFG['min_charge']}): ${quote['total']:,}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Secondary breakdown
    st.markdown("###### Breakdown")
    breakdown_cols = st.columns(3)
    with breakdown_cols[0]:
        st.write(f"Add‑ons: ${quote.get('addons', 0):,}")
        st.write(f"Materials: ${quote.get('materials', 0):,}")
    with breakdown_cols[1]:
        st.write(f"Travel: ${quote.get('travel', 0):,}")
        st.write(f"Water: ${quote.get('water', 0):,}")
    with breakdown_cols[2]:
        st.write(f"Lift: ${quote.get('lift', 0):,}")
        if "day_target" in prod_quote:
            st.write(f"Day target: ${prod_quote['day_target']:,}")

    # Compute time to complete (sq ft per minute) and labor/fuel costs
    st.markdown("###### Time & Labor")
    exp_rate = {"Novice": 90, "Medium": 107, "Expert": 130}[exp_level]
    build_factor = {"Light": 1.0, "Medium": 0.85, "Heavy": 0.70}[buildup]
    suggested_per_tech = exp_rate * build_factor
    tech_count = max(1, int(crew_size))
    suggested_crew_sfpm = max(10.0, min(120.0, float(suggested_per_tech * tech_count)))
    crew_sfpm = st.slider("Crew sq ft/min", 10.0, 120.0, value=float(suggested_crew_sfpm), step=1.0)
    area = CFG["size_midpoints_ft2"][size]
    cleaning_minutes = area / max(1.0, float(crew_sfpm))
    cleaning_hours = cleaning_minutes / 60.0
    daily_hours_safe = max(0.5, float(daily_hours))
    days_fraction = cleaning_hours / daily_hours_safe
    days_needed = math.ceil(days_fraction)

    def calc_labor_cost(hours_per_day: float, days: int, rate: float, state_name: str) -> float:
        if state_name != "California":
            return rate * hours_per_day * days
        # CA daily OT: >8h @1.5x, >12h @2x
        base_h = min(8.0, hours_per_day)
        ot1_h = max(0.0, min(12.0, hours_per_day) - 8.0)
        ot2_h = max(0.0, hours_per_day - 12.0)
        return days * (rate * base_h + rate * 1.5 * ot1_h + rate * 2.0 * ot2_h)

    # Assume trucks*2 techs → split crew into trucks; compute per-tech labor using weighted average (lead/jr)
    # For simplicity, split evenly: half lead, half jr across trucks
    leads = math.ceil(tech_count / 2)
    jrs = tech_count - leads
    per_tech_hours_day = float(daily_hours)
    labor_cost = (
        leads * calc_labor_cost(per_tech_hours_day, days_needed, lead_rate, state)
        + jrs * calc_labor_cost(per_tech_hours_day, days_needed, jr_rate, state)
    )

    # Fuel based on machine-hours: each truck runs for job duration
    gallons_per_hr = float(CFG["fuel"]["gallons_per_machine_hour"])
    fuel_price = float(CFG["fuel"]["price_per_gallon"])
    machine_hours = cleaning_hours * max(1, int(trucks))
    fuel_cost = machine_hours * gallons_per_hr * fuel_price

    crew_sph = crew_sfpm * 60.0
    tech_sph = (crew_sfpm / tech_count) * 60.0
    st.write(f"SqFt/min per crew: {crew_sfpm:.1f}  •  SqFt/hour per crew: {crew_sph:.0f}")
    st.write(f"SqFt/hour per tech (approx): {tech_sph:.0f}")
    st.write(f"Estimated cleaning hours: {cleaning_hours:.2f}")
    st.write(f"Estimated days (fraction): {days_fraction:.2f}  •  Rounded: {days_needed}")
    st.write(f"Labor cost (incl. CA OT if applicable): ${labor_cost:,.2f}")
    st.write(f"Fuel cost estimate: ${fuel_cost:,.2f}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Book Site Visit", use_container_width=True):
            st.success("Thanks! A local Rolling Suds rep will contact you to confirm.")
    with col_b:
        if st.button("Email Me This Quote", use_container_width=True):
            leads_csv = Path(__file__).with_name("leads.csv")
            new_row = {
                "ts": datetime.utcnow().isoformat(timespec="seconds"),
                "name": name,
                "email": email,
                "phone": phone,
                "ptype": ptype,
                "size": size,
                "stories": stories,
                "surface": surface,
                "grime": grime,
                "frequency": frequency,
                "addons": ",".join([k for k, v in addon_state.items() if v]),
                "miles": miles,
                "needs_water": needs_water,
                "weekend": weekend,
                "rush": rush,
                "use_lift": use_lift,
                "lift_hours": float(lift_hours),
                "crew_size": int(crew_size),
                "job_category": job_category,
                "basis": basis,
                "total": quote["total"],
            }
            file_exists = leads_csv.exists()
            with leads_csv.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(new_row.keys()))
                if not file_exists:
                    writer.writeheader()
                writer.writerow(new_row)
            st.success("Quote sent! We saved your info; we’ll follow up shortly.")

st.divider()
st.caption("Rates are configurable in pricing_config.json. Update values and the app recalculates instantly.")


