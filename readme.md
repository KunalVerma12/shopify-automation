cat > README.md <<'EOF'
# Shopify Automation

Python-based automation scripts for managing Shopify product imports and post-import channel publishing through the Shopify Admin GraphQL API.

## Features

- Generate Shopify-compatible product CSV files
- Automate product import workflows
- Configure and manage Shopify product metafields
- Publish imported products to the Online Store
- Control product visibility across selected sales channels
- Automatically unpublish products from restricted advertising channels based on product requirements
- Uses Shopify Admin GraphQL API

## Project Structure

```text
automation/
├── main.py
├── generate_shopify_csv.py
├── update_channel_publications.py
├── authoritative_metafield_definitions.json
├── confirmed_metafields.json
├── remaining_metafields.json
├── remaining_6_metafields.json
├── remaining_7_metafields.json
├── shopify_import_ready.csv
└── README.md