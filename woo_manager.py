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
        if not net_price: return 0.0
        try:
            # Fórmula de precio: $(Neto x 1.22) x 1.30 -> IVA y luego Margen
            price_with_iva = float(net_price) * getattr(config, 'IVA_RATE', 1.22)
            final_price = price_with_iva * getattr(config, 'MARGIN_RATE', 1.30)
            return round(final_price, 2)
        except: return 0.0

    def get_category_id_by_name(self, name):
        print(f"🔍 Buscando categoría '{name}' en WooCommerce...")
        try:
            res = self.wcapi.get("products/categories", params={"search": name})
            if res.status_code == 200:
                cats = res.json()
                if isinstance(cats, list):
                    for c in cats:
                        # Error de Categorías: Aplica un isinstance(c, dict)
                        if isinstance(c, dict) and c.get("name", "").lower() == name.lower():
                            return c.get("id")
            return None
        except: return None

    def get_all_products(self, category_id=None):
        products_map = {}
        page = 1
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
        # Lógica de Sincronización Segura
        if scraped_data.get('error'):
            # Si hay error (navegación, timeout), salta producto, ni siquiera loggea sincro
            return False, "Error"

        sku = scraped_data.get('sku')
        if not sku:
            return False, "Sin SKU"

        net_price = scraped_data.get('net_price', 0)
        final_price_float = self.calculate_price(net_price)
        final_price_str = str(final_price_float)

        if final_price_float == 0:
            return False, "Precio 0"

        mpn = scraped_data.get('mpn', 'N/A')
        in_stock = scraped_data.get('in_stock', True)

        payload = {
            "sku": sku,
            "name": scraped_data['name'],
            "regular_price": final_price_str,
            "manage_stock": True,
            "stock_quantity": 10 if in_stock else 0,
            "status": "publish" if in_stock else "draft",
            "catalog_visibility": "visible" if in_stock else "hidden"
        }
        
        try:
            if existing_product:
                self.wcapi.put(f"products/{existing_product['id']}", payload)
            else:
                if scraped_data.get('image_url'): 
                    payload["images"] = [{"src": scraped_data['image_url']}]
                if scraped_data.get('category_ids'): 
                    payload["categories"] = [{"id": cid} for cid in scraped_data['category_ids']]
                self.wcapi.post("products", payload)
            
            # Print log in github actions requested style
            print(f"✅ Sincronizado: {sku} | MPN: {mpn} | $ {final_price_float}")
            return True, "Sincronizado"
        except Exception as e:
            print(f"❌ Error sincronizando {sku}: {e}")
            return False, "Error Sincro"

    def archive_orphan(self, product_data):
        # Según las instrucciones: SOLO archivar si el scraper confirmó
        # explícitamente "Sin Stock". NO archivar basándose en "huérfanos".
        # En esta versión 2.0 segura no archivamos ciegas por si acaso.
        pass