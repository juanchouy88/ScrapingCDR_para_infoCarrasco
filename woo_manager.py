from woocommerce import API
import config

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
        if not net_price: return 0
        try:
            price_with_iva = float(net_price) * config.IVA_RATE
            final_price = price_with_iva * config.MARGIN_RATE
            return int(round(final_price, 0))
        except: return 0

    def get_category_id_by_name(self, name):
        print(f"🔍 Buscando categoría '{name}' en WooCommerce...")
        try:
            res = self.wcapi.get("products/categories", params={"search": name})
            if res.status_code == 200:
                cats = res.json()
                if isinstance(cats, list):
                    for c in cats:
                        if isinstance(c, dict) and c.get("name", "").lower() == name.lower():
                            return c["id"]
            return None
        except: return None

    def get_all_products(self, category_id=None):
        products_map = {}
        page = 1
        # IMPORTANTE: Eliminamos el filtro de categoría para buscar en toda la tienda
        # Esto evita crear duplicados si el producto ya existe en otra categoría.
        while True:
            res = self.wcapi.get("products", params={"per_page": 50, "page": page})
            if res.status_code != 200: break
            data = res.json()
            if not data: break
            for p in data:
                if isinstance(p, dict) and p.get("sku"):
                    products_map[p["sku"]] = p
            page += 1
        return products_map

    def sync_product(self, scraped_data, existing_product=None):
        sku = scraped_data['sku']
        final_price = str(self.calculate_price(scraped_data.get('net_price', 0)))
        payload = {
            "sku": sku,
            "name": scraped_data['name'],
            "regular_price": final_price,
            "manage_stock": True,
            "stock_quantity": 10 if scraped_data['in_stock'] else 0,
            "status": "publish" if scraped_data['in_stock'] else "draft",
            "catalog_visibility": "visible" if scraped_data['in_stock'] else "hidden"
        }
        try:
            if existing_product:
                self.wcapi.put(f"products/{existing_product['id']}", payload)
            else:
                if scraped_data.get('image_url'): payload["images"] = [{"src": scraped_data['image_url']}]
                if scraped_data.get('category_ids'): payload["categories"] = [{"id": cid} for cid in scraped_data['category_ids']]
                self.wcapi.post("products", payload)
        except Exception as e:
            print(f"❌ Error sincronizando {sku}: {e}")

    def archive_orphan(self, product_data):
        try: self.wcapi.put(f"products/{product_data['id']}", {"stock_quantity": 0, "status": "draft"})
        except: pass