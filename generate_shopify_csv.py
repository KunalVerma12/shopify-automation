#!/usr/bin/env python3
"""
Shopify Import-Ready CSV Generator for SarinSkin Store.

Takes per-product row-wise source CSVs (Column A: Field Name, Column B: Value)
or column-wise source CSVs and generates a single, fully compliant Shopify Native Import CSV (Products -> Import)
with standard columns and authoritative Metafield columns.
"""

import os
import re
import csv
import json
import glob
import argparse
from typing import Dict, List, Any, Optional

# ==============================================================================
# AUTHORITATIVE METAFIELD DEFINITIONS (Verified against live SarinSkin store)
# ==============================================================================
# Format:
# "Source Field Name / Alias": {
#     "header": "Shopify Recognized Column Header",
#     "type": "single_line_text" | "multi_line_text" | "boolean" | "list_single_line_text" | "metaobject_list" | "product_list",
#     "is_list": bool
# }

METAFIELD_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Irregular / Confirmed Keys
    "Brand Name": {
        "header": "Brand Name (product.metafields.custom.brand_name_)",
        "type": "single_line_text",
        "is_list": False
    },
    "New Key Ingredient": {
        "header": "New Key Ingredient (product.metafields.custom.new_key_ingredientss)",
        "type": "single_line_text",
        "is_list": False
    },
    "New Key Benefits": {
        "header": "New Key Benefits (product.metafields.custom.new_key_benefit)",
        "type": "single_line_text",
        "is_list": False
    },
    "New Indications": {
        "header": "New Indications (product.metafields.custom.new_indications)",
        "type": "single_line_text",
        "is_list": False
    },
    "How to Use": {
        "header": "How To Use (product.metafields.custom.how_to_use_)",
        "type": "single_line_text",
        "is_list": False
    },
    "How To Use": {
        "header": "How To Use (product.metafields.custom.how_to_use_)",
        "type": "single_line_text",
        "is_list": False
    },
    "Indication1": {
        "header": "Indication1 (product.metafields.custom.problems_solved_indications)",
        "type": "single_line_text",
        "is_list": False
    },
    "Indication2": {
        "header": "Indication2 (product.metafields.custom.indication2)",
        "type": "single_line_text",
        "is_list": False
    },
    "Indication3": {
        "header": "Indication3 (product.metafields.custom.indication3)",
        "type": "single_line_text",
        "is_list": False
    },
    "Product Type Filter": {
        "header": "Product Type Filter (product.metafields.custom.product_type)",
        "type": "list_single_line_text",
        "is_list": True
    },
    "Ingredient Filter": {
        "header": "Ingredient Filter (product.metafields.custom.ingredient)",
        "type": "list_single_line_text",
        "is_list": True
    },
    "Skin Type Filter": {
        "header": "Skin Type Filter (product.metafields.custom.skin_type_filter)",
        "type": "list_single_line_text",
        "is_list": True
    },
    "Custom Country of Origin": {
        "header": "Custom Country of Origin (product.metafields.custom.custom_country_of_origin)",
        "type": "multi_line_text",
        "is_list": False
    },
    "Custom Storage": {
        "header": "Custom Storage (product.metafields.custom.custom_storage)",
        "type": "multi_line_text",
        "is_list": False
    },
    "Custom Side Effects": {
        "header": "Custom Side Effects (product.metafields.custom.custom_side_effects)",
        "type": "multi_line_text",
        "is_list": False
    },
    "Custom Composition": {
        "header": "Custom Composition (product.metafields.custom.custom_composition)",
        "type": "multi_line_text",
        "is_list": False
    },
    "Custom Mfg/Marketer details": {
        "header": "Custom Mfg/Marketer details (product.metafields.custom.custom_mfg_marketer_details)",
        "type": "multi_line_text",
        "is_list": False
    },
    "Custom Importer details": {
        "header": "Custom Importer details (product.metafields.custom.custom_importer_details)",
        "type": "multi_line_text",
        "is_list": False
    },
    "Prescription Required": {
        "header": "Prescription Required (product.metafields.custom.prescription_required)",
        "type": "boolean",
        "is_list": False
    },
    "Pack Of Variant": {
        "header": "Pack Of Variant (product.metafields.custom.pack_of_variant)",
        "type": "boolean",
        "is_list": False
    },
    "Pack Variant": {
        "header": "Pack Variant (product.metafields.custom.pack_variant)",
        "type": "list_single_line_text",
        "is_list": True
    },
    "Product Quantity": {
        "header": "Product Quantity (product.metafields.custom.product_quantity)",
        "type": "single_line_text",
        "is_list": False
    },
    "FAQ": {
        "header": "Faqs (product.metafields.custom.faqs)",
        "type": "single_line_text",
        "is_list": False
    },
    "Faqs": {
        "header": "Faqs (product.metafields.custom.faqs)",
        "type": "single_line_text",
        "is_list": False
    },
    "Tag": {
        "header": "Tag (product.metafields.custom.tag)",
        "type": "single_line_text",
        "is_list": False
    },
    "Best Used With Product": {
        "header": "Best Used With Product (product.metafields.custom.best_used_with_product)",
        "type": "product_list",
        "is_list": True
    },
    "Ingredients": {
        "header": "Ingredients (product.metafields.shopify.ingredients)",
        "type": "list_single_line_text",
        "is_list": True
    },
    "Available offer": {
        "header": "Available offer (product.metafields.custom.available_offer)",
        "type": "metaobject_list",
        "is_list": True
    },
    "Available Offers": {
        "header": "Available offer (product.metafields.custom.available_offer)",
        "type": "metaobject_list",
        "is_list": True
    },
    "Available Coupons": {
        "header": "Available offer (product.metafields.custom.available_offer)",
        "type": "metaobject_list",
        "is_list": True
    }
}

# Standard metaobject references for Available offer (strict semicolon-separated, NO SPACES)
DEFAULT_AVAILABLE_OFFERS = "additional-5-off;get-a-freebie;free-shipping"

# Fields explicitly excluded from generation per project constraints
EXCLUDED_FIELDS = {
    "doctor's choice",
    "doctors choice",
    "life cycle of the product",
    "lifecycle of the product",
    "usage information",
    "key ingredients"  # custom legacy text field
}

# Standard Shopify CSV Columns
STANDARD_COLUMNS = [
    "Handle",
    "Title",
    "Body (HTML)",
    "Vendor",
    "Product Category",
    "Type",
    "Tags",
    "Published",
    "Option1 Name",
    "Option1 Value",
    "Variant SKU",
    "Variant Grams",
    "Variant Inventory Tracker",
    "Variant Inventory Qty",
    "Variant Inventory Policy",
    "Variant Fulfillment Service",
    "Variant Price",
    "Variant Compare At Price",
    "Variant Requires Shipping",
    "Variant Taxable",
    "Status"
]


def generate_handle(title: str) -> str:
    """Generate a deterministic Shopify handle from product title."""
    if not title:
        return ""
    handle = title.lower().strip()
    handle = re.sub(r"[^\w\s-]", "", handle)
    handle = re.sub(r"[\s_]+", "-", handle)
    handle = re.sub(r"-+", "-", handle)
    return handle.strip("-")


def format_metafield_value(raw_val: str, meta_type: str, is_list: bool) -> str:
    """Format cell value according to Shopify Metafield type schema."""
    if not raw_val or not str(raw_val).strip():
        return ""

    val = str(raw_val).strip()

    # Boolean formatting
    if meta_type == "boolean":
        v_low = val.lower()
        if v_low in ["true", "1", "yes", "y", "t"]:
            return "TRUE"
        elif v_low in ["false", "0", "no", "n", "f"]:
            return "FALSE"
        return "FALSE"

    # Metaobject List / Product List formatting
    if meta_type in ["metaobject_list", "product_list"]:
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
                    return "; ".join(items)
            except Exception:
                pass
        # Split on pipe, semicolon, or newline
        raw_items = re.split(r"[|\n;]", val)
        items = [item.strip() for item in raw_items if item.strip()]
        return "; ".join(items)

    # Single Line Text List formatting (Shopify CSV importer expects \n newline separated items for list pills)
    if is_list or meta_type in ["list_single_line_text"]:
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
                    return "\n".join(items)
            except Exception:
                pass

        # Split on pipe '|', newline '\n', or semicolon ';' (or comma if no pipes exist)
        if "|" in val:
            raw_items = val.split("|")
        elif "\n" in val:
            raw_items = val.split("\n")
        elif ";" in val:
            raw_items = val.split(";")
        else:
            raw_items = val.split(",")
        items = [item.strip() for item in raw_items if item.strip()]
        return "\n".join(items)

    # Multi-line Text formatting (preserve multiple separate lines, convert pipe '|' separators into newlines)
    if meta_type == "multi_line_text":
        if "|" in val:
            raw_lines = val.split("|")
            lines = [line.strip() for line in raw_lines if line.strip()]
            return "\n".join(lines)
        return val

    # Standard Text (single line text)
    # Remove unexpected internal line breaks
    val = re.sub(r"[\r\n]+", " ", val).strip()
    return val


def parse_source_csv(filepath: str) -> List[Dict[str, str]]:
    """Parse a source CSV whether it is row-wise (Col A: Key, Col B: Value) or column-wise (Row 1: Headers)."""
    records = []
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))
        if not reader:
            return []

        # Check if Column-wise (first row has > 2 columns, or headers match typical product keys)
        first_row = [c.strip() for c in reader[0] if c.strip()]
        is_column_wise = len(first_row) > 2 or (len(reader) >= 2 and any(k.lower() in ["handle", "title", "sku", "price", "add product"] for k in first_row))

        if is_column_wise:
            headers = [h.strip() for h in reader[0]]
            for row in reader[1:]:
                if not any(row):
                    continue
                record = {}
                for idx, h in enumerate(headers):
                    if idx < len(row):
                        record[h] = row[idx]
                if record:
                    records.append(record)
        else:
            # Row-wise format
            record = {}
            for row in reader:
                if not row or not any(row):
                    continue
                k = row[0].strip()
                if len(row) == 2:
                    v = row[1]
                elif len(row) > 2:
                    v = ",".join(row[1:])
                else:
                    v = ""
                if k.lower() in ["field", "field name", "key", "attribute"] and v.strip().lower() in ["value", "val", "data"]:
                    continue
                if k:
                    record[k] = v
            if record:
                records.append(record)

    return records


def get_source_val(source_data: Dict[str, str], aliases: List[str]) -> str:
    """Helper to retrieve a value case-insensitively from source dict using alias list."""
    lower_map = {k.strip().lower(): v for k, v in source_data.items()}
    for alias in aliases:
        val = lower_map.get(alias.lower())
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def build_shopify_row(source_data: Dict[str, str], source_filename: str) -> Dict[str, str]:
    """Transform source dictionary into a single Shopify import row."""
    row = {col: "" for col in STANDARD_COLUMNS}

    # 1. Standard Fields (Resolving aliases case-insensitively)
    title = get_source_val(source_data, ["Title", "Add product", "Product Title", "Product Name", "Product", "Name"])
    handle = get_source_val(source_data, ["Handle"]) or generate_handle(title)
    description = get_source_val(source_data, ["Description", "Body (HTML)", "Body", "Product Description", "Details", "Product Details", "Overview"])
    brand_vendor = get_source_val(source_data, ["Brand Name", "Vendor", "Brand"])
    product_type = get_source_val(source_data, ["Type", "Product Type", "Product Type Filter"])
    tags = get_source_val(source_data, ["Tags"])
    sku = get_source_val(source_data, ["SKU", "Variant SKU"])
    price = get_source_val(source_data, ["Price", "Variant Price"])
    compare_at = get_source_val(source_data, ["Compare-at", "Compare at", "Variant Compare At Price"])

    # Default to draft, but keep published = TRUE so Online Store sales channel stays ON
    status_raw = get_source_val(source_data, ["Status"]).lower()
    status = status_raw if status_raw in ["active", "draft", "archived"] else "draft"
    published = "TRUE"

    # Resolve Option1 Name & Option1 Value (Size / Quantity)
    quantity_val = get_source_val(source_data, ["Product Quantity", "Quantity", "Size", "Net Quantity", "Net Vol", "Net Weight", "Pack Size", "Volume"])

    # Fallback: Infer quantity from SKU if present (e.g. SS-REV-HSER-REDENSYL-120ML -> 120ml)
    if not quantity_val and sku:
        m = re.search(r"[-_](\d+\s*(?:ml|g|gm|kg|l|oz|capsules|tablets|pcs|ct|tabs|tab|pieces))(?:\b|[-_]|$)", sku, re.IGNORECASE)
        if m:
            quantity_val = m.group(1).strip().lower()

    # If quantity exists, create Size variant; otherwise omit option columns
    if quantity_val:
        row["Option1 Name"] = "Size"
        row["Option1 Value"] = quantity_val
    else:
        row["Option1 Name"] = ""
        row["Option1 Value"] = ""

    row["Handle"] = handle
    row["Title"] = title
    row["Body (HTML)"] = description
    row["Vendor"] = brand_vendor
    row["Type"] = product_type
    row["Tags"] = tags
    row["Published"] = published
    row["Variant SKU"] = sku
    row["Variant Grams"] = "0"
    row["Variant Inventory Tracker"] = "shopify"
    inv_qty = get_source_val(source_data, ["Inventory Qty", "Variant Inventory Qty"])
    row["Variant Inventory Qty"] = inv_qty if inv_qty else "3"
    row["Variant Inventory Policy"] = "deny"
    row["Variant Fulfillment Service"] = "manual"
    row["Variant Price"] = price
    row["Variant Compare At Price"] = compare_at if compare_at and compare_at != "0" else ""
    row["Variant Requires Shipping"] = "TRUE"
    row["Variant Taxable"] = "TRUE"
    row["Status"] = status

    # 2. Metafields Processing
    # Standard fields keys to ignore during metafield mapping
    standard_keys = {
        "title", "add product", "product title", "product name", "product", "name",
        "handle", "description", "body (html)", "body", "product description", "details", "product details", "overview",
        "vendor", "brand", "type", "product type",
        "tags", "sku", "variant sku", "price", "variant price",
        "compare-at", "compare at", "variant compare at price", "status", "published",
        "product category", "option1 name", "option1 value", "variant grams",
        "variant weight", "variant weight unit", "variant requires shipping",
        "variant taxable", "variant inventory policy", "variant fulfillment service",
        "variant inventory tracker", "seo title", "seo description"
    }

    unmapped_keys = []
    excluded_found = []

    for raw_k, raw_v in source_data.items():
        k_clean = raw_k.strip()
        k_low = k_clean.lower()

        if k_low in standard_keys:
            continue

        if k_low in EXCLUDED_FIELDS:
            excluded_found.append(k_clean)
            continue

        matched_def = None
        for reg_k, reg_info in METAFIELD_REGISTRY.items():
            if reg_k.lower() == k_low:
                matched_def = reg_info
                break

        if matched_def:
            header = matched_def["header"]
            formatted_val = format_metafield_value(raw_v, matched_def["type"], matched_def["is_list"])
            row[header] = formatted_val
        else:
            unmapped_keys.append(k_clean)

    # Ensure Brand Name metafield is populated if vendor is present
    if brand_vendor and not row.get("Brand Name (product.metafields.custom.brand_name_)"):
        row["Brand Name (product.metafields.custom.brand_name_)"] = brand_vendor

    # Ensure Available offer is always populated with the 3 metaobject handles
    avail_offer_header = "Available offer (product.metafields.custom.available_offer)"
    row[avail_offer_header] = DEFAULT_AVAILABLE_OFFERS

    print(f"📦 Processed: '{title}' ({source_filename})")
    print(f"   -> Handle: {handle}")

    if excluded_found:
        print(f"   ℹ️  Explicitly Excluded: {', '.join(excluded_found)}")
    if unmapped_keys:
        print(f"   ⚠️  Unmapped Source Fields (Skipped): {', '.join(unmapped_keys)}")

    return row


def generate_import_csv(input_paths: List[str], output_path: str):
    """Process multiple source CSVs and write single Shopify-import-ready CSV."""
    meta_headers = []
    seen_headers = set()
    for item in METAFIELD_REGISTRY.values():
        h = item["header"]
        if h not in seen_headers:
            seen_headers.add(h)
            meta_headers.append(h)

    all_headers = STANDARD_COLUMNS + meta_headers

    rows = []
    for path in input_paths:
        if not os.path.exists(path):
            print(f"❌ File not found: {path}")
            continue
        data_records = parse_source_csv(path)
        if not data_records:
            print(f"⚠️ Empty CSV: {path}")
            continue
        for record in data_records:
            row = build_shopify_row(record, os.path.basename(path))
            rows.append(row)

    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            full_row = {col: r.get(col, "") for col in all_headers}
            writer.writerow(full_row)

    print("\n" + "=" * 80)
    print(f"🎉 Generated Shopify Import CSV with {len(rows)} products: {output_path}")
    print(f"📊 Total Columns: {len(all_headers)} (Standard: {len(STANDARD_COLUMNS)}, Metafields: {len(meta_headers)})")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Generate Shopify Import-ready CSV from row-wise product CSVs.")
    parser.add_argument("--input", "-i", nargs="+", default=["batch_products.csv"],
                        help="Input file(s) or glob pattern (e.g. products/*.csv)")
    parser.add_argument("--output", "-o", default="shopify_import_ready.csv",
                        help="Output CSV path (default: shopify_import_ready.csv)")

    args = parser.parse_args()

    expanded_paths = []
    for pattern in args.input:
        matched = glob.glob(pattern)
        if matched:
            expanded_paths.extend(matched)
        else:
            expanded_paths.append(pattern)

    generate_import_csv(expanded_paths, args.output)


if __name__ == "__main__":
    main()
