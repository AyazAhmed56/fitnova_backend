"""
USDA Nutrient Enricher for FitNova
==================================

Purpose:
    Enrich the existing `nutrition_foods` Supabase table with USDA
    nutrient values.

The existing table already contains USDA foods with:
    - fdc_id
    - name
    - normalized_name
    - food_type
    - etc.

This script does NOT create duplicate foods.

It:
    1. Fetches existing nutrition_foods records from Supabase.
    2. Downloads USDA bulk CSV archives.
    3. Reads food_nutrient.csv from each archive.
    4. Extracts selected nutrient IDs.
    5. Matches USDA fdc_id with existing Supabase rows.
    6. Updates nutrient columns.
    7. Upserts the complete existing rows back into Supabase.

Run:
    python usda_nutrient_enricher.py

Optional:
    python usda_nutrient_enricher.py --dry-run

Requirements:
    pip install requests python-dotenv

Environment variables:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

These are read from your existing .env file.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time
import zipfile

from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "",
).strip()


# ============================================================
# CONFIGURATION
# ============================================================

TABLE_NAME = "nutrition_foods"

# Number of rows retrieved from Supabase at once.
SUPABASE_PAGE_SIZE = 1000

# Number of rows sent to Supabase per upsert.
SUPABASE_UPSERT_BATCH_SIZE = 100

# Timeout for HTTP requests.
HTTP_TIMEOUT = 120

# USDA bulk datasets.
#
# These are the official USDA FoodData Central CSV downloads.
#
# Foundation Foods:
# April 2026
#
# SR Legacy:
# April 2018 - final release
#
# FNDDS:
# 2021-2023, October 2024
#
USDA_DATASETS = [
    {
        "name": "Foundation Foods",
        "url": (
            "https://fdc.nal.usda.gov/fdc-datasets/"
            "FoodData_Central_foundation_food_csv_2026-04-30.zip"
        ),
    },
    {
        "name": "SR Legacy",
        "url": (
            "https://fdc.nal.usda.gov/fdc-datasets/"
            "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
        ),
    },
    {
        "name": "FNDDS 2021-2023",
        "url": (
            "https://fdc.nal.usda.gov/fdc-datasets/"
            "FoodData_Central_survey_food_csv_2024-10-31.zip"
        ),
    },
]


# ============================================================
# NUTRIENT IDs
# ============================================================
#
# These match the nutrient IDs already used by your
# usda_importer.py.
#
# USDA FoodData Central nutrient IDs:
#
# 1008 = Energy / Calories
# 1003 = Protein
# 1004 = Total lipid / Fat
# 1005 = Carbohydrate
# 1079 = Fiber
# 1087 = Calcium
# 1089 = Iron
# 1090 = Magnesium
# 1092 = Potassium
# 1095 = Zinc
# 1106 = Vitamin A
# 1162 = Vitamin C
# 1114 = Vitamin D
# 1178 = Vitamin B12
#
# ============================================================

NUTRIENT_IDS: dict[int, str] = {
    1008: "calories",
    1003: "protein_g",
    1004: "fat_g",
    1005: "carbohydrates_g",
    1079: "fiber_g",
    1087: "calcium_mg",
    1089: "iron_mg",
    1090: "magnesium_mg",
    1092: "potassium_mg",
    1095: "zinc_mg",
    1106: "vitamin_a_ug",
    1162: "vitamin_c_mg",
    1114: "vitamin_d_ug",
    1178: "vitamin_b12_ug",
}


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": "FitNova-Nutrition-Enricher/1.0",
        "Accept": "application/json",
    }
)


# ============================================================
# VALIDATION
# ============================================================


def validate_environment() -> None:
    """
    Make sure Supabase credentials exist.

    USDA bulk downloads do NOT require the USDA API key.
    """

    missing = []

    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")

    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# SUPABASE HEADERS
# ============================================================


def supabase_headers() -> dict[str, str]:
    """
    Headers for Supabase REST API.
    """

    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ============================================================
# SUPABASE SELECT
# ============================================================


def fetch_existing_foods() -> dict[int, dict[str, Any]]:
    """
    Fetch all existing rows from nutrition_foods.

    Returns:

        {
            12345: {
                "id": "...",
                "fdc_id": 12345,
                "name": "...",
                ...
            }
        }

    This allows us to enrich existing records instead of
    inserting duplicate foods.
    """

    print()
    print("=" * 70)
    print("STEP 1: FETCHING EXISTING SUPABASE FOOD RECORDS")
    print("=" * 70)

    all_foods: dict[int, dict[str, Any]] = {}

    offset = 0

    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"

    while True:
        params = {
            "select": "*",
            "food_type": "eq.raw",
            "order": "fdc_id.asc",
            "limit": str(SUPABASE_PAGE_SIZE),
            "offset": str(offset),
        }

        try:
            response = session.get(
                url,
                headers=supabase_headers(),
                params=params,
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Supabase request failed: {exc}"
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                "Supabase SELECT failed "
                f"({response.status_code}): "
                f"{response.text[:1000]}"
            )

        rows = response.json()

        if not rows:
            break

        for row in rows:
            fdc_id = row.get("fdc_id")

            if fdc_id is None:
                continue

            try:
                fdc_id_int = int(fdc_id)
            except (TypeError, ValueError):
                continue

            all_foods[fdc_id_int] = row

        print(
            f"Fetched {len(all_foods):,} existing foods...",
            end="\r",
            flush=True,
        )

        if len(rows) < SUPABASE_PAGE_SIZE:
            break

        offset += SUPABASE_PAGE_SIZE

    print()
    print(
        f"Existing USDA foods found: {len(all_foods):,}"
    )

    if not all_foods:
        raise RuntimeError(
            "No existing nutrition_foods records were found."
        )

    return all_foods


# ============================================================
# USDA DOWNLOAD
# ============================================================


def download_usda_archive(
    dataset_name: str,
    url: str,
) -> bytes:
    """
    Download a USDA ZIP archive into memory.

    Foundation and SR Legacy archives are small.
    FNDDS is around 200 MB zipped, according to USDA.

    The ZIP itself is kept in memory only while processing
    the archive. The huge CSV inside the ZIP is streamed.
    """

    print()
    print("-" * 70)
    print(f"Downloading: {dataset_name}")
    print("-" * 70)

    print(url)

    try:
        response = session.get(
            url,
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Failed downloading {dataset_name}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"USDA download failed for {dataset_name}: "
            f"HTTP {response.status_code}\n"
            f"{response.text[:500]}"
        )

    content = response.content

    size_mb = len(content) / (1024 * 1024)

    print(
        f"Downloaded {size_mb:.2f} MB"
    )

    return content


# ============================================================
# FIND FOOD_NUTRIENT CSV
# ============================================================


def find_food_nutrient_csv(
    zip_file: zipfile.ZipFile,
) -> str:
    """
    Find food_nutrient.csv inside a USDA ZIP archive.

    USDA archives may contain folders, so we don't assume
    an exact path.
    """

    candidates = []

    for name in zip_file.namelist():
        normalized = name.replace("\\", "/").lower()

        if normalized.endswith("food_nutrient.csv"):
            candidates.append(name)

    if not candidates:
        raise RuntimeError(
            "Could not find food_nutrient.csv inside USDA archive.\n"
            "Files found:\n"
            + "\n".join(zip_file.namelist()[:100])
        )

    # Prefer the shortest / direct filename.
    candidates.sort(
        key=lambda value: (
            value.count("/"),
            len(value),
        )
    )

    return candidates[0]


# ============================================================
# CONVERT NUMBER
# ============================================================


def parse_float(
    value: Any,
) -> float | None:
    """
    Safely convert USDA nutrient amount to float.
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


# ============================================================
# PROCESS USDA ARCHIVE
# ============================================================


def process_usda_archive(
    dataset_name: str,
    archive_bytes: bytes,
    target_fdc_ids: set[int],
) -> dict[int, dict[str, float | None]]:
    """
    Read food_nutrient.csv from a USDA ZIP archive.

    Only records whose fdc_id already exists in Supabase
    are processed.

    Returns:

        {
            fdc_id: {
                "protein_g": 25.2,
                "calcium_mg": 120.0,
                ...
            }
        }
    """

    print()
    print("=" * 70)
    print(f"PROCESSING USDA DATASET: {dataset_name}")
    print("=" * 70)

    nutrient_data: dict[
        int,
        dict[str, float | None],
    ] = {}

    processed_rows = 0
    matched_rows = 0
    nutrient_matches = 0

    with zipfile.ZipFile(
        io.BytesIO(archive_bytes),
        "r",
    ) as zf:

        csv_name = find_food_nutrient_csv(zf)

        print(
            f"Using CSV: {csv_name}"
        )

        with zf.open(csv_name, "r") as binary_file:

            text_file = io.TextIOWrapper(
                binary_file,
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            )

            reader = csv.DictReader(text_file)

            if not reader.fieldnames:
                raise RuntimeError(
                    "food_nutrient.csv has no header."
                )

            # USDA usually uses these exact names.
            field_names = {
                field.strip().lower(): field
                for field in reader.fieldnames
                if field
            }

            fdc_id_field = field_names.get("fdc_id")
            nutrient_id_field = field_names.get("nutrient_id")
            amount_field = field_names.get("amount")

            if not fdc_id_field:
                raise RuntimeError(
                    "food_nutrient.csv does not contain fdc_id."
                )

            if not nutrient_id_field:
                raise RuntimeError(
                    "food_nutrient.csv does not contain nutrient_id."
                )

            if not amount_field:
                raise RuntimeError(
                    "food_nutrient.csv does not contain amount."
                )

            for row in reader:

                processed_rows += 1

                raw_fdc_id = row.get(fdc_id_field)
                raw_nutrient_id = row.get(
                    nutrient_id_field
                )

                if not raw_fdc_id or not raw_nutrient_id:
                    continue

                try:
                    fdc_id = int(float(raw_fdc_id))
                except (TypeError, ValueError):
                    continue

                # Important optimization:
                # Ignore USDA foods that aren't already
                # in our Supabase table.
                if fdc_id not in target_fdc_ids:
                    continue

                matched_rows += 1

                try:
                    nutrient_id = int(
                        float(raw_nutrient_id)
                    )
                except (TypeError, ValueError):
                    continue

                column = NUTRIENT_IDS.get(
                    nutrient_id
                )

                if column is None:
                    continue

                amount = parse_float(
                    row.get(amount_field)
                )

                if fdc_id not in nutrient_data:
                    nutrient_data[fdc_id] = {}

                nutrient_data[fdc_id][column] = amount

                nutrient_matches += 1

                if processed_rows % 100000 == 0:
                    print(
                        f"Rows: {processed_rows:,} | "
                        f"Matched: {matched_rows:,} | "
                        f"Nutrients: {nutrient_matches:,}",
                        end="\r",
                        flush=True,
                    )

    print()

    print(
        f"Total CSV rows processed: "
        f"{processed_rows:,}"
    )

    print(
        f"Rows matching existing foods: "
        f"{matched_rows:,}"
    )

    print(
        f"Nutrient values matched: "
        f"{nutrient_matches:,}"
    )

    print(
        f"Foods with nutrient data: "
        f"{len(nutrient_data):,}"
    )

    return nutrient_data


# ============================================================
# MERGE NUTRIENT DATA
# ============================================================


def merge_nutrient_data(
    existing_foods: dict[int, dict[str, Any]],
    nutrient_data: dict[int, dict[str, float | None]],
) -> tuple[int, int]:
    """
    Merge nutrient values into existing Supabase rows.

    Returns:

        (foods_updated, nutrient_values_updated)
    """

    foods_updated = 0
    nutrient_values_updated = 0

    for fdc_id, nutrients in nutrient_data.items():

        row = existing_foods.get(fdc_id)

        if row is None:
            continue

        row_changed = False

        for column, value in nutrients.items():

            # We only replace with a real numeric value.
            #
            # This prevents a missing USDA nutrient from
            # accidentally overwriting an existing value.
            if value is None:
                continue

            row[column] = value

            row_changed = True
            nutrient_values_updated += 1

        if row_changed:
            foods_updated += 1

    return foods_updated, nutrient_values_updated


# ============================================================
# SUPABASE UPSERT
# ============================================================


def upsert_rows(
    rows: list[dict[str, Any]],
    dry_run: bool = False,
) -> None:
    """
    Upsert enriched rows back into nutrition_foods.

    We send the COMPLETE existing row instead of only nutrient
    columns.

    This is intentional.

    Sending only:
        fdc_id
        protein_g
        calcium_mg
        ...

    through an UPSERT can risk replacing unspecified fields
    depending on database configuration.

    Sending the complete existing row preserves:
        name
        normalized_name
        food_type
        source
        category
        description
        brand_name
        serving data
        etc.
    """

    if not rows:
        return

    total = len(rows)

    print()
    print("=" * 70)
    print("UPDATING SUPABASE")
    print("=" * 70)

    print(
        f"Rows to update: {total:,}"
    )

    if dry_run:
        print()
        print(
            "DRY RUN ENABLED - no Supabase changes will be made."
        )

        for row in rows[:5]:
            print()
            print(
                f"Example: {row.get('name')}"
            )

            print(
                f"  fdc_id: {row.get('fdc_id')}"
            )

            for column in NUTRIENT_IDS.values():
                value = row.get(column)

                if value is not None:
                    print(
                        f"  {column}: {value}"
                    )

        return

    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"

    headers = supabase_headers()

    # Important:
    #
    # This must match the unique constraint/index
    # used by your existing importer.
    headers[
        "Prefer"
    ] = (
        "resolution=merge-duplicates,"
        "return=minimal"
    )

    completed = 0

    for start in range(
        0,
        total,
        SUPABASE_UPSERT_BATCH_SIZE,
    ):

        end = min(
            start + SUPABASE_UPSERT_BATCH_SIZE,
            total,
        )

        batch = rows[start:end]

        params = {
            "on_conflict": "fdc_id",
        }

        try:
            response = session.post(
                url,
                headers=headers,
                params=params,
                json=batch,
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Supabase UPSERT request failed "
                f"for batch {start}-{end}: {exc}"
            ) from exc

        if response.status_code not in (
            200,
            201,
            204,
        ):
            raise RuntimeError(
                "Supabase UPSERT failed "
                f"({response.status_code}) "
                f"for batch {start}-{end}:\n"
                f"{response.text[:2000]}"
            )

        completed = end

        percentage = (
            completed / total * 100
        )

        print(
            f"Updated {completed:,}/{total:,} "
            f"({percentage:.1f}%)",
            end="\r",
            flush=True,
        )

        # Small pause prevents hammering Supabase.
        time.sleep(0.05)

    print()

    print(
        f"Successfully updated {completed:,} rows."
    )


# ============================================================
# SHOW STATISTICS
# ============================================================


def print_statistics(
    foods: dict[int, dict[str, Any]],
) -> None:
    """
    Print how many records now have each nutrient.
    """

    print()
    print("=" * 70)
    print("FINAL NUTRIENT STATISTICS")
    print("=" * 70)

    total = len(foods)

    print(
        f"Total foods: {total:,}"
    )

    print()

    for column in NUTRIENT_IDS.values():

        count = 0

        for row in foods.values():

            value = row.get(column)

            if value is not None:
                count += 1

        percentage = (
            count / total * 100
            if total
            else 0
        )

        print(
            f"{column:<22} "
            f"{count:>7,} / {total:,} "
            f"({percentage:>6.2f}%)"
        )


# ============================================================
# MAIN
# ============================================================


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Enrich FitNova nutrition_foods "
            "with USDA nutrient data."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Process USDA data but do not update "
            "Supabase."
        ),
    )

    parser.add_argument(
        "--dataset",
        choices=[
            "all",
            "foundation",
            "sr_legacy",
            "fndds",
        ],
        default="all",
        help=(
            "Choose which USDA dataset to process."
        ),
    )

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("FITNOVA USDA NUTRIENT ENRICHER")
    print("=" * 70)

    print(
        "This script enriches existing nutrition_foods records."
    )

    print(
        f"Supabase table: {TABLE_NAME}"
    )

    print(
        f"Nutrients: {len(NUTRIENT_IDS)}"
    )

    if args.dry_run:
        print(
            "Mode: DRY RUN"
        )
    else:
        print(
            "Mode: LIVE"
        )

    # --------------------------------------------------------
    # Validate environment
    # --------------------------------------------------------

    validate_environment()

    # --------------------------------------------------------
    # Fetch existing Supabase records
    # --------------------------------------------------------

    existing_foods = fetch_existing_foods()

    target_fdc_ids = set(
        existing_foods.keys()
    )

    # --------------------------------------------------------
    # Select datasets
    # --------------------------------------------------------

    datasets_to_process = []

    for dataset in USDA_DATASETS:

        name = dataset["name"]

        if args.dataset == "all":
            datasets_to_process.append(
                dataset
            )

        elif (
            args.dataset == "foundation"
            and name == "Foundation Foods"
        ):
            datasets_to_process.append(
                dataset
            )

        elif (
            args.dataset == "sr_legacy"
            and name == "SR Legacy"
        ):
            datasets_to_process.append(
                dataset
            )

        elif (
            args.dataset == "fndds"
            and name == "FNDDS 2021-2023"
        ):
            datasets_to_process.append(
                dataset
            )

    if not datasets_to_process:
        raise RuntimeError(
            "No USDA dataset selected."
        )

    # --------------------------------------------------------
    # Process each USDA dataset
    # --------------------------------------------------------

    total_nutrient_data: dict[
        int,
        dict[str, float | None],
    ] = {}

    for dataset in datasets_to_process:

        name = dataset["name"]
        url = dataset["url"]

        archive = download_usda_archive(
            name,
            url,
        )

        nutrient_data = process_usda_archive(
            dataset_name=name,
            archive_bytes=archive,
            target_fdc_ids=target_fdc_ids,
        )

        # Merge results.
        #
        # If the same FDC ID appears in multiple datasets,
        # later datasets overwrite only the nutrient columns
        # that they actually contain.
        for fdc_id, nutrients in nutrient_data.items():

            if fdc_id not in total_nutrient_data:
                total_nutrient_data[fdc_id] = {}

            total_nutrient_data[
                fdc_id
            ].update(nutrients)

        # Release archive memory.
        del archive

    # --------------------------------------------------------
    # Merge into existing rows
    # --------------------------------------------------------

    foods_updated, nutrient_values_updated = (
        merge_nutrient_data(
            existing_foods,
            total_nutrient_data,
        )
    )

    print()
    print("=" * 70)
    print("MERGE SUMMARY")
    print("=" * 70)

    print(
        f"Existing foods: "
        f"{len(existing_foods):,}"
    )

    print(
        f"USDA foods matched: "
        f"{len(total_nutrient_data):,}"
    )

    print(
        f"Foods receiving nutrient data: "
        f"{foods_updated:,}"
    )

    print(
        f"Nutrient values updated: "
        f"{nutrient_values_updated:,}"
    )

    # --------------------------------------------------------
    # Prepare rows for Supabase
    # --------------------------------------------------------

    rows_to_update = []

    for fdc_id in total_nutrient_data.keys():

        row = existing_foods.get(fdc_id)

        if row is not None:
            rows_to_update.append(row)

    # --------------------------------------------------------
    # Update Supabase
    # --------------------------------------------------------

    upsert_rows(
        rows_to_update,
        dry_run=args.dry_run,
    )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    print_statistics(
        existing_foods
    )

    print()
    print("=" * 70)
    print("NUTRIENT ENRICHMENT COMPLETE")
    print("=" * 70)

    if args.dry_run:
        print(
            "DRY RUN completed. "
            "No database changes were made."
        )
    else:
        print(
            "Database enrichment completed successfully."
        )

    print()


# ============================================================
# ENTRY POINT
# ============================================================


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print()
        print(
            "Process interrupted by user."
        )
        sys.exit(1)

    except Exception as exc:
        print()
        print("=" * 70)
        print("ERROR")
        print("=" * 70)
        print(str(exc))
        print()

        sys.exit(1)