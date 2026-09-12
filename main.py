import json
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=options)

print("Opening an active product page in Shopify Admin...", flush=True)
driver.get("https://admin.shopify.com/store/sarinskin/products/8332545065273")
time.sleep(6)

# Scroll to metafields
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)

# Extract all metafield rows, labels, values, metaobject references
js_extract = """
function getAllMetafields() {
  const card = Array.from(document.querySelectorAll("div")).find(d => d.innerText && d.innerText.includes("Product metafields") && d.innerText.includes("View definitions"));
  if (!card) return { error: "Metafield card not found", bodySnippet: document.body.innerText.slice(0, 1000) };

  const rows = Array.from(card.querySelectorAll("tr, [role='row'], .Polaris-FormLayout__Item, .Polaris-InlineGrid, .Polaris-Box"));
  return {
    cardText: card.innerText,
    inputs: Array.from(card.querySelectorAll("input, textarea")).map(i => ({ id: i.id, name: i.name, value: i.value }))
  };
}

return getAllMetafields();
"""

res = driver.execute_script(js_extract)
print("--- METAFEILD CARD TEXT ---", flush=True)
print(res.get("cardText", res.get("bodySnippet", "")))

exit(0)