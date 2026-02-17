from woocommerce import API
import config
import math

class WooManager:
    def __init__(self):
        self.wcapi = API(
            url=config.WOO_URL,
            consumer_key=config.WOO_KEY,
            consumer_secret=config.WOO_SECRET,
            version="wc/v3",
            timeout=30
        )

    def calculate_price(self, net_price):
        """
        Price = round((Price_CDR * 1.22) * 1.30, 0)
        """
        if not net_price:
            return 0
        price_with_iva = net_price * config.IVA_RATE
        final_price = price_with_iva * config.MARGIN_RATE
        return int(round(final_price, 0))

    def get_all_products(self, category_id=None):
        """
        Fetch all products. If category_id provided, filter by it.
        Returns dict: {sku: product_data}
        """
        print("Fetching existing products from WooCommerce...")
        products_map = {}
        page = 1
        params = {"per_page": 50}
        if category_id:
            params["category"] = category_id

        while True:
            params["page"] = page
            res = self.wcapi.get("products", params=params)
            
            if res.status_code != 200:
                print(f"Error fetching products: {res.status_code} - {res.text}")
                break
                
            data = res.json()
            if not data:
                break
            
            for p in data:
                if p.get("sku"):
                    products_map[p["sku"]] = p
            
            print(f"Fetched page {page} ({len(data)} products)")
            page += 1
            
        print(f"Total existing products fetched: {len(products_map)}")
        return products_map

    def get_category_id_by_name(self, name):
        """
        Helper to find category ID by name.
        """
        res = self.wcapi.get("products/categories", params={"search": name})
        if res.status_code == 200:
            cats = res.json()
            for c in cats:
                if c["name"].lower() == name.lower():
                    return c["id"]
        return None

    def sync_product(self, scraped_data, existing_product=None):
        """
        Create or Update product.
        """
        sku = scraped_data['sku']
        net_price = scraped_data.get('net_price', 0)
        final_price = str(self.calculate_price(net_price))
        
        # Prepare Payload
        payload = {
            "sku": sku,
            "name": scraped_data['name'],
            "regular_price": final_price,
            "description": scraped_data.get('description', ''),
            "manage_stock": True,
            "stock_quantity": 10 if scraped_data['in_stock'] else 0, # Arbitrary 10 if in stock? Or just >0
            "status": "publish" if scraped_data['in_stock'] else "draft", 
            # If out of stock, user asked for: Set Stock = 0 and Catalog Visibility = "Hidden" (or Status = "Draft").
            # Let's use status=draft for simplicity as requested "or Status = Draft"
        }

        if not scraped_data['in_stock']:
            payload["stock_quantity"] = 0
            payload["status"] = "draft"
            payload["catalog_visibility"] = "hidden"
        else:
             payload["catalog_visibility"] = "visible"

        # Image handling (only update if missing or new product)
        # Updating images on every run is heavy.
        if scraped_data.get('image_url'):
            payload["images"] = [{"src": scraped_data['image_url']}]

        # Category Assignment for New Products
        if not existing_product and scraped_data.get('category_ids'):
            payload["categories"] = [{"id": cid} for cid in scraped_data['category_ids']]
        
        if existing_product:
            # UPDATE
            # Only update if price/stock changed? Or force update?
            # User said "Actualizar Precio y forzar Visible/In Stock"
            
            pid = existing_product['id']
            print(f"Updating product {sku} (ID: {pid})...")
            
            # Use put to update
            res = self.wcapi.put(f"products/{pid}", payload)
            if res.status_code not in [200, 201]:
                 print(f"Failed to update {sku}: {res.text}")
            else:
                 print(f"Updated {sku}.")
                 
        else:
            # CREATE
            print(f"Creating product {sku}...")
            # We need a category ID to put it in the right place.
            # Assuming we can pass it in payload if we knew it.
            # For now, create without specific category or user has to map it.
            # Or we can guess from the scrape context?
            
            res = self.wcapi.post("products", payload)
            if res.status_code not in [200, 201]:
                print(f"Failed to create {sku}: {res.text}")
            else:
                print(f"Created {sku}.")

    def archive_orphan(self, product_data):
        """
        Set stock 0 and draft/hidden.
        """
        pid = product_data['id']
        sku = product_data['sku']
        print(f"Archiving orphan {sku} (ID: {pid})...")
        
        payload = {
            "stock_quantity": 0,
            "manage_stock": True,
            "status": "draft",
            "catalog_visibility": "hidden"
        }
        self.wcapi.put(f"products/{pid}", payload)

if __name__ == "__main__":
    # Test
    wm = WooManager()
    # print(wm.get_all_products())
    print(f"Price Test (100): {wm.calculate_price(100)}")
