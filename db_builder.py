import pandas as pd
import sqlite3
def create_sqlite_db(db_path="hs_attributes.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS hs_attribute_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hs4 TEXT,
        master_description TEXT,
        extracted_attributes TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("✅ SQLite DB and table created:", db_path)


create_sqlite_db()
def load_csv_to_sqlite(csv_path, db_path="hs_attributes.db"):
    df = pd.read_csv(csv_path)

    # ensure required columns exist
    df = df[["hs_code", "master_description", "extracted_attributes"]].dropna()

    # create hs4
    df["hs4"] = df["hs_code"].astype(str).str[:4]

    conn = sqlite3.connect(db_path)

    df[["hs4", "master_description", "extracted_attributes"]].to_sql(
        "hs_attribute_store",
        conn,
        if_exists="append",
        index=False
    )

    conn.close()
    print("✅ Data inserted into SQLite DB:", db_path)


load_csv_to_sqlite("testing_file (1).csv")
def preview_db(db_path="hs_attributes.db", limit=5):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(f"SELECT * FROM hs_attribute_store LIMIT {limit}", conn)
    conn.close()
    return df


print(preview_db())
