import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# `python scripts/seed_master_data.py` で実行された場合でも `app.*` を import できるようにする。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DATABASE_URL, normalize_database_url


MASTER_DATA_DIR = PROJECT_ROOT / "master_data"


def load_json(filename: str) -> list[dict]:
    file_path = MASTER_DATA_DIR / filename
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def table_columns(table: Table) -> set[str]:
    return {column.name for column in table.columns}


def filter_payload(payload: dict, columns: set[str]) -> dict:
    return {k: v for k, v in payload.items() if k in columns}


def upsert_by_keys(session: Session, table: Table, key_fields: list[str], payload: dict) -> None:
    columns = table_columns(table)
    db_payload = filter_payload(payload, columns)
    missing_keys = [key for key in key_fields if key not in db_payload]
    if missing_keys:
        raise ValueError(f"{table.name}: missing key fields {missing_keys}")

    where_clause = [table.c[key] == db_payload[key] for key in key_fields]
    existing = session.execute(select(table).where(*where_clause).limit(1)).first()

    if existing:
        update_values = {k: v for k, v in db_payload.items() if k not in key_fields}
        if update_values:
            session.execute(table.update().where(*where_clause).values(**update_values))
        return

    session.execute(table.insert().values(**db_payload))


def resolve_category_ids(session: Session, categories_table: Table) -> dict[str, int]:
    rows = session.execute(select(categories_table.c.id, categories_table.c.name)).all()
    return {name: category_id for category_id, name in rows}


def resolve_issuer_ids(session: Session, issuers_table: Table) -> dict[str, int]:
    rows = session.execute(select(issuers_table.c.id, issuers_table.c.code)).all()
    return {code: issuer_id for issuer_id, code in rows}


def require_tables(engine: Engine, required_tables: list[str]) -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    existing = set(metadata.tables.keys())
    missing = [table for table in required_tables if table not in existing]
    if missing:
        raise RuntimeError(
            "Missing required tables: "
            + ", ".join(missing)
            + ". Run migrations that create these tables before seeding."
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed master data from backend/master_data.")
    parser.add_argument(
        "--skip-users",
        action="store_true",
        help="Do not read users.json and do not write the users table.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    engine = create_engine(normalize_database_url(DATABASE_URL))
    required_tables = [
        "users",
        "categories",
        "classification_rules",
        "fixed_expenses",
        "card_issuers",
        "csv_import_profiles",
    ]
    require_tables(engine, required_tables)

    metadata = MetaData()
    users_table = Table("users", metadata, autoload_with=engine) if not args.skip_users else None
    categories_table = Table("categories", metadata, autoload_with=engine)
    rules_table = Table("classification_rules", metadata, autoload_with=engine)
    fixed_expenses_table = Table("fixed_expenses", metadata, autoload_with=engine)
    issuers_table = Table("card_issuers", metadata, autoload_with=engine)
    profiles_table = Table("csv_import_profiles", metadata, autoload_with=engine)

    users = [] if args.skip_users else load_json("users.json")
    categories = load_json("categories.json")
    rules = load_json("classification_rules.json")
    fixed_expenses = load_json("fixed_expenses.json")
    issuers = load_json("card_issuers.json")
    profiles = load_json("csv_import_profiles.json")

    with Session(engine) as session:
        with session.begin():
            if not args.skip_users:
                for user in users:
                    upsert_by_keys(session, users_table, ["email"], user)

            for category in categories:
                upsert_by_keys(session, categories_table, ["name"], category)

            category_map = resolve_category_ids(session, categories_table)

            for rule in rules:
                category_name = rule["category_name"]
                if category_name not in category_map:
                    raise ValueError(
                        f"classification_rules: unknown category_name '{category_name}'"
                    )
                payload = dict(rule)
                payload["category_id"] = category_map[category_name]
                payload.pop("category_name", None)
                upsert_by_keys(session, rules_table, ["pattern", "category_id"], payload)

            for fixed_expense in fixed_expenses:
                category_name = fixed_expense["category_name"]
                if category_name not in category_map:
                    raise ValueError(f"fixed_expenses: unknown category_name '{category_name}'")
                payload = dict(fixed_expense)
                payload["category_id"] = category_map[category_name]
                payload.pop("category_name", None)
                for date_key in ("valid_from", "valid_until"):
                    raw = payload.get(date_key)
                    if isinstance(raw, str) and raw:
                        payload[date_key] = date.fromisoformat(raw)
                upsert_by_keys(
                    session,
                    fixed_expenses_table,
                    ["name", "billing_day", "card_holder", "valid_from"],
                    payload,
                )

            for issuer in issuers:
                upsert_by_keys(session, issuers_table, ["code"], issuer)

            issuer_map = resolve_issuer_ids(session, issuers_table)

            for profile in profiles:
                issuer_code = profile["card_issuer_code"]
                if issuer_code not in issuer_map:
                    raise ValueError(
                        f"csv_import_profiles: unknown card_issuer_code '{issuer_code}'"
                    )
                payload = dict(profile)
                payload["card_issuer_id"] = issuer_map[issuer_code]
                payload.pop("card_issuer_code", None)
                upsert_by_keys(session, profiles_table, ["card_issuer_id"], payload)

    print("Master data seeded successfully.")


if __name__ == "__main__":
    main(sys.argv[1:])
