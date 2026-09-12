#!/usr/bin/env python3
"""
Post-Import Sales Channel Publishing Script for Shopify Admin GraphQL API.

Solves Problem 1:
- Shopify product CSV import cannot control channel-level visibility (Online Store vs. FB/IG vs. Google/YouTube).
- This post-import script connects to the Shopify Admin GraphQL API and:
  1. Publishes all imported products to "Online Store".
  2. Unpublishes products where "Prescription Required" = TRUE from restricted advertising channels
     ("Facebook & Instagram" and "Google & YouTube").
"""

import os
import sys
import csv
import json
import argparse
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Set

API_VERSION = "2026-01"


def execute_graphql(shop_domain: str, access_token: str, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a GraphQL query/mutation against Shopify Admin API."""
    clean_domain = shop_domain.replace("https://", "").replace("http://", "").strip("/")
    if not clean_domain.endswith(".myshopify.com"):
        clean_domain = f"{clean_domain}.myshopify.com"

    url = f"https://{clean_domain}/admin/api/{API_VERSION}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        error_content = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP {e.code} Error: {error_content}")
    except Exception as e:
        raise RuntimeError(f"GraphQL request failed: {str(e)}")


def fetch_publications(shop_domain: str, access_token: str, dry_run: bool = False) -> Dict[str, str]:
    """Fetch publication (sales channel) names and IDs."""
    if dry_run:
        print("[DRY-RUN] Mocking publications lookup...")
        return {
            "online store": "gid://shopify/Publication/1111111111",
            "facebook & instagram": "gid://shopify/Publication/2222222222",
            "facebook and instagram": "gid://shopify/Publication/2222222222",
            "google & youtube": "gid://shopify/Publication/3333333333",
            "google and youtube": "gid://shopify/Publication/3333333333"
        }

    query = """
    query getPublications {
      publications(first: 50) {
        edges {
          node {
            id
            name
          }
        }
      }
    }
    """
    res = execute_graphql(shop_domain, access_token, query)
    publications = {}
    edges = res.get("data", {}).get("publications", {}).get("edges", [])
    for edge in edges:
        node = edge.get("node", {})
        name = node.get("name", "").strip().lower()
        pub_id = node.get("id")
        if name and pub_id:
            publications[name] = pub_id

    return publications


def publish_product_to_channel(shop_domain: str, access_token: str, product_gid: str, publication_gid: str, dry_run: bool = False):
    """Publish a product to a specific publication channel."""
    if dry_run:
        print(f"  [DRY-RUN] publishablePublish(product={product_gid}, publication={publication_gid})")
        return

    mutation = """
    mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
      publishablePublish(id: $id, input: $input) {
        publishable {
          ... on Product {
            id
            title
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "id": product_gid,
        "input": [{"publicationId": publication_gid}]
    }
    res = execute_graphql(shop_domain, access_token, mutation, variables)
    errors = res.get("data", {}).get("publishablePublish", {}).get("userErrors", [])
    if errors:
        print(f"  ❌ Errors publishing {product_gid}: {errors}")


def unpublish_product_from_channel(shop_domain: str, access_token: str, product_gid: str, publication_gid: str, dry_run: bool = False):
    """Unpublish a product from a specific publication channel."""
    if dry_run:
        print(f"  [DRY-RUN] publishableUnpublish(product={product_gid}, publication={publication_gid})")
        return

    mutation = """
    mutation publishableUnpublish($id: ID!, $input: [PublicationInput!]!) {
      publishableUnpublish(id: $id, input: $input) {
        publishable {
          ... on Product {
            id
            title
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    variables = {
        "id": product_gid,
        "input": [{"publicationId": publication_gid}]
    }
    res = execute_graphql(shop_domain, access_token, mutation, variables)
    errors = res.get("data", {}).get("publishableUnpublish", {}).get("userErrors", [])
    if errors:
        print(f"  ❌ Errors unpublishing {product_gid}: {errors}")


def update_store_publications(
    shop_domain: str,
    access_token: str,
    import_csv_path: str,
    dry_run: bool = False
):
    """Process import CSV, match handles to products, and apply channel visibility policies."""
    print("=" * 80)
    print("🚀 Starting Shopify Sales Channel Publishing Sync")
    print(f"   Target Store: {shop_domain}")
    print(f"   CSV File: {import_csv_path}")
    print(f"   Dry-Run Mode: {'ENABLED' if dry_run else 'DISABLED'}")
    print("=" * 80)

    # 1. Fetch channel publication IDs
    pub_map = fetch_publications(shop_domain, access_token, dry_run=dry_run)
    print("\n🔍 Discovered Publication Channels:")
    for name, gid in pub_map.items():
        print(f"   - {name}: {gid}")

    online_store_id = pub_map.get("online store")
    fb_ig_id = pub_map.get("facebook & instagram") or pub_map.get("facebook and instagram") or pub_map.get("facebook")
    google_yt_id = pub_map.get("google & youtube") or pub_map.get("google and youtube") or pub_map.get("google")

    if not online_store_id and not dry_run:
        raise ValueError("Could not find 'Online Store' publication channel.")

    # 2. Read products from import CSV
    with open(import_csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    print(f"\n📂 Read {len(reader)} products from CSV.")

    for row in reader:
        handle = row.get("Handle", "").strip()
        title = row.get("Title", "").strip()
        rx_val = row.get("Prescription Required (product.metafields.custom.prescription_required)", "").strip().upper()
        is_prescription = rx_val in ["TRUE", "1", "YES"]

        print(f"\n📦 Processing Product: '{title}' (handle: {handle})")
        print(f"   Rx Required: {is_prescription}")

        # In production, query the product GID using Admin GraphQL products connection by handle
        product_gid = f"gid://shopify/Product/{handle}" if dry_run else None
        if not dry_run:
            product_query = """
            query getProductByHandle($query: String!) {
              products(first: 1, query: $query) {
                edges {
                  node {
                    id
                    title
                  }
                }
              }
            }
            """
            p_res = execute_graphql(shop_domain, access_token, product_query, {"query": f"handle:{handle}"})
            edges = p_res.get("data", {}).get("products", {}).get("edges", [])
            if not edges:
                print(f"   ⚠️ Product with handle '{handle}' not found on store. Skipping.")
                continue
            product_gid = edges[0]["node"]["id"]

        # Policy 1: Always publish to Online Store
        if online_store_id:
            print("   ✅ Action: Publishing to 'Online Store'")
            publish_product_to_channel(shop_domain, access_token, product_gid, online_store_id, dry_run=dry_run)

        # Policy 2: If Prescription Required, unpublish from FB/IG and Google/YouTube
        if is_prescription:
            if fb_ig_id:
                print("   🚫 Action: Unpublishing from 'Facebook & Instagram' (Rx Compliance)")
                unpublish_product_from_channel(shop_domain, access_token, product_gid, fb_ig_id, dry_run=dry_run)
            if google_yt_id:
                print("   🚫 Action: Unpublishing from 'Google & YouTube' (Rx Compliance)")
                unpublish_product_from_channel(shop_domain, access_token, product_gid, google_yt_id, dry_run=dry_run)
        else:
            print("   ℹ️  Non-prescription product: Standard advertising channels allowed.")

    print("\n" + "=" * 80)
    print("🎉 Sales Channel Publishing Sync Complete!")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Shopify Post-Import Sales Channel Publisher")
    parser.add_argument("--shop", default=os.getenv("SHOPIFY_SHOP_DOMAIN", "sarinskin"), help="Shopify store domain")
    parser.add_argument("--token", default=os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN", ""), help="Shopify Admin API access token")
    parser.add_argument("--input", "-i", default="shopify_import_ready.csv", help="Input CSV path")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate execution without modifying live store (default: True)")
    parser.add_argument("--live", action="store_true", help="Execute against live store (requires valid token)")

    args = parser.parse_args()
    is_dry_run = not args.live

    if not is_dry_run and not args.token:
        print("❌ Error: --token or SHOPIFY_ADMIN_ACCESS_TOKEN must be set when running in live mode.")
        sys.exit(1)

    update_store_publications(
        shop_domain=args.shop,
        access_token=args.token,
        import_csv_path=args.input,
        dry_run=is_dry_run
    )


if __name__ == "__main__":
    main()

