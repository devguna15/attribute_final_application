import streamlit as st
import sqlite3
import json
import openai

# -------------------------------
# ✅ CONFIG
# -------------------------------
DB_PATH = "hs_attributes.db"
MODEL_NAME = "gpt-4.1-mini"

# -------------------------------
# ✅ DOMAIN MAPPING (HS2 → Domain)
# -------------------------------
hs_mapping = {
    "01-05": "Live Animals",
    "06-14": "Vegetable Products",
    "15": "Animal, Vegetable Or Microbial Fats And Oils And Their Cleavage Products; Prepared Edible Fats; Animal Or Vegetable Waxes",
    "16-24": "Prepared Foodstuffs; Beverages, Spirits And Vinegar; Tobacco And Manufactured Tobacco Substitutes",
    "25-27": "Mineral Products",
    "28-38": "Products Of The Chemical Or Allied Industries",
    "39-40": "Plastics And Articles Thereof; Rubber And Articles Thereof",
    "41-43": "Raw Hides And Skins, Leather, Furskins; Articles Of Animal Gut",
    "44-46": "Wood And Articles Of Wood; Cork; Basketware and Wickerwork",
    "47-49": "Pulp Of Wood; Recovered Paper; Paper and Paperboard Articles",
    "50-63": "Textile And Textile Articles",
    "64-67": "Footwear, Headgear, Artificial Flowers; Articles Of Human Hair",
    "68-70": "Articles Of Stone, Plaster, Cement, Asbestos, Mica; Glass And Glassware",
    "71": "Natural Or Cultured Pearls, Precious Metals, and Articles Thereof; Imitation Jewellery",
    "72-83": "Base Metals And Articles Of Base Metal",
    "84-85": "Machinery And Mechanical Appliances; Electrical Equipment; Sound and TV Recorders",
    "86-89": "Vehicles, Aircraft, Vessels And Associated Transport Equipment",
    "90-92": "Optical, Medical Or Surgical Instruments; Clocks; Musical Instruments",
    "93": "Arms And Ammunition; Parts And Accessories Thereof",
    "94-96": "Miscellaneous Manufactured Articles",
    "97": "Works Of Art, Collectors' Pieces And Antiques"
}

def get_domain(hs_code: str):
    try:
        hs_int = int(str(hs_code).zfill(4)[:2])
        for k, v in hs_mapping.items():
            if "-" in k:
                lo, hi = map(int, k.split("-"))
                if lo <= hs_int <= hi:
                    return v
            elif int(k) == hs_int:
                return v
    except:
        pass
    return "General Trade Goods"

# -------------------------------
# ✅ FETCH ATTRIBUTES FROM SQLITE
# -------------------------------
def fetch_reference_attributes(hs4: str, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT extracted_attributes
        FROM hs_attribute_store
        WHERE hs4 = ?
        LIMIT 1
    """, (hs4,))

    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        return row[0]  # this is stored JSON string
    return None

def fetch_available_hs4_codes(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT hs4
        FROM hs_attribute_store
        WHERE hs4 IS NOT NULL AND hs4 != ''
        ORDER BY hs4
    """)

    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]
# -------------------------------
# ✅ YOUR FINAL PARENT → CHILD PROMPT
# -------------------------------
def build_final_prompt(hs_code, domain, item_description, reference_attributes_json):
    return f"""
Role: You are a Lead Trade Data Taxonomist for a global trade intelligence platform. Your task is to generate the final customer-facing flat JSON attribute map for a product.

INPUTS

HS Code: {hs_code}

Domain: {domain}

Item Description (Child): {item_description}

Reference Attributes JSON (Parent): {reference_attributes_json}

STEP 1 — INTERNAL ALIGNMENT (DO NOT OUTPUT)
IMPORTANT FIRST RULE: 
 Identify and Select the most specific and accurate product name for Product Type key based on the child-level description only to anchor all subsequent logic. Do not generalize or pick alternate names from parent JSON.

GATE 1: SCHEMA SELECTION (THE KEYS) Identify all keys from the Parent JSON that are technically relevant to the identified Product Type and Item Description. Finalize this list of keys to create a professional technical schema.

STRICT RELEVANCE: You must delete any keys from the Parent JSON that are logically incompatible with the identified Product Type or Domain (e.g., if Domain is "Food," delete "Vinyl Flooring" or "Machinery" keys).

GATE 2: VALUE PRIORITIZATION (THE TRUTH) For each finalized key, scan the Item Description. If a specific value, measurement, or technical detail exists in the description, you MUST assign that value to the responsible key. This is the absolute highest priority.

LOGISTICS EXTRACTION: Specifically look for and extract unit multipliers or bulk counts (e.g., "12 x 750ml", "129 BOX", "20 Pkts x 25 CTN"). Map these to Packaging or Quantity.

GATE 3: SANITY CHECK & PROFESSIONAL GENERALIZATION (THE AUDIT) If the Item Description has no information for a finalized key, audit the Parent value:

Numerical/Specific Noise: "Is this value a specific, shipment-level detail (e.g., decimals, lot-specific weights, or unique identifiers)?"

Categorical Claims: "Is this value a specific claim about the product's source, manufacturer, or third-party certification that is not explicitly supported by the Child description?"

Scale Contradiction: "Does this value contradict the physical scale or commercial nature of the item described?" ACTION: If the value is suspicious or fails the sanity check, DO NOT omit the key. Instead, replace the value with a Category-Aware Generalization (see Step 2). Never inherit specific numeric "Ghost Values" (like 21.5 MT or 520ml) from the Parent.


GATE 4: 
CHILD-ONLY ATTRIBUTES (DISCOVERY): Analyze the Item Description for unique technical attributes not present in the Parent JSON (e.g., Scientific Names, Model Numbers, Material Grades). Include them only if they are domain-relevant and technically meaningful.
CHEMICAL IDENTITY ENRICHMENT: If the product is a chemical compound, identify its standard Chemical Formula and CAS Number based on the name provided.

Ambiguity Rule: If the description does not specify the state (e.g., hydrous, anhydrous, or specific salt), provide the Base/Parent Compound details.

Standardization: Append a professional note to these values: "(Base compound; refer to CoA for specific hydration/salt state)"
STEP 2 — FINAL ATTRIBUTE GENERATION RULES
1. PRODUCT IDENTITY

Output exactly one key: "Product Type". Must be derived only from the item description (e.g., "Chana Masala").

2. CATEGORY-AWARE GENERALIZATION (THE REFERENCE APPROACH) If a value is missing or rejected by Gate 3, assign a placeholder adapted to the Domain:
below mentions are for just references:

For Food/Agri/Pharma/Consumer Domains:

Use: "Standard Grade (Refer to Product Label or Certificate of Analysis)"

Use: "Refer to Product Label or Manufacturer Website"

For Machinery/Chemical/Metal/Industrial Domains:

Use: "Standard Industrial Specification (Refer to Datasheet/Manual)"

Use: "Standard Industrial Size (Refer to Technical Drawing/Packaging)"

Logistics (Weight/Volume/Quantities): "Calculated at Time of Shipping / As per Invoice" or "Refer to Shipping Documents/Bill of Lading".

3. NO REDUNDANCY

If an attribute value is identical to the "Product Type", do not repeat it in other keys.

STEP 3 — STRUCTURE
Output a SINGLE flat JSON object.

All list-type values must be standard JSON arrays: ["Value 1", "Value 2"].

No empty arrays, empty strings, or "N/A" values.

FINAL OUTPUT FORMAT Return ONLY a valid flat JSON object. Do not include intermediate reasoning.
""".strip()

# -------------------------------
# ✅ OPENAI CALL
# -------------------------------
def call_llm(prompt):
    response = openai.chat.completions.create(
        model=MODEL_NAME,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a Lead Trade Data Taxonomist. Return ONLY a valid flat JSON object."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

# -------------------------------
# ✅ STREAMLIT UI
# -------------------------------
st.set_page_config(page_title="HS Code Attribute POC", layout="wide")
st.title("✅ HS4 Attribute Inheritance POC (Parent → Child)")

st.sidebar.header("🔑 OpenAI Key")
api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password")

if api_key:
    openai.api_key = api_key

col1, col2 = st.columns(2)

with col1:
    hs4_list = fetch_available_hs4_codes()

    if not hs4_list:
        st.error("No HS codes found in database. Please load data into hs_attribute_store.")
        st.stop()

    hs_code = st.selectbox(
        "HS Code (HS4 from DB)",
        options=hs4_list,
        index=0
    )

    item_description = st.text_area("Item Description (Child)", height=150)


with col2:
    st.markdown("### 🔍 Reference Attributes (Parent from DB)")
    hs4 = str(hs_code).strip()[:4] if hs_code else ""
    reference_json = None

    if hs4:
        reference_json = fetch_reference_attributes(hs4)

    if reference_json:
        st.code(reference_json, language="json")
    else:
        st.warning("No Parent reference attributes found yet (check DB or HS4).")

st.markdown("---")

if st.button("🚀 Generate Final Customer Attributes"):
    if not api_key:
        st.error("Please enter OpenAI API Key in sidebar.")
    elif not hs_code or not item_description:
        st.error("Please enter HS Code and Item Description.")
    elif not reference_json:
        st.error("No reference attributes found for this HS4 in DB.")
    else:
        domain = get_domain(hs_code)

        st.info(f"✅ Detected Domain: **{domain}** | HS4: **{hs4}**")

        final_prompt = build_final_prompt(
            hs_code=hs_code,
            domain=domain,
            item_description=item_description,
            reference_attributes_json=reference_json
        )

        with st.expander("📌 Final Prompt (Debug View)"):
            st.write(final_prompt)

        try:
            llm_output = call_llm(final_prompt)

            st.markdown("## ✅ FINAL OUTPUT (Customer Attributes)")
            st.code(llm_output, language="json")

            # optional: render json nicely
            try:
                parsed = json.loads(llm_output)
                st.json(parsed)
            except:
                pass

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
