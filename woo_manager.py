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
            # Fórmula estricta: (Neto * 1.22) * 1.30 y redondea a entero
            price_with_iva = float(net_price) * 1.22
            final_price = price_with_iva * 1.30
            return round(final_price, 0)
        except: return 0.0

    # Categorías eliminadas según requerimiento (método ignorado/ausente o comentado)
    # def get_category_id_by_name(self, name): ...

    def get_all_products(self):
        # Ahora obtiene el mapa de todos los productos de manera global sin filtro de categoría
        print("🔍 Recuperando productos globales pre-existentes de WooCommerce...")
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
        if scraped_data.get('error'):
            return False, "Error"

        sku = scraped_data.get('sku')
        if not sku:
            return False, "Sin SKU"

        net_price = scraped_data.get('net_price', 0)
        final_price_float = self.calculate_price(net_price)
        final_price_str = str(int(final_price_float)) if final_price_float.is_integer() else str(final_price_float)

        image_url = scraped_data.get('image_url', '')

        # PROTECCIÓN DE TIENDA: Absurdos / Minimos
        if final_price_float < 1.0 or final_price_float > 10000.0:
            print(f"⚠️ Precio irreal detectado (${final_price_float}) en SKU {sku}. Difiere del neto de ${net_price}. Saltando sincronización de este producto.")
            return False, "Error Precio"
            
        # BLINDAJE PARA IMÁGENES: Crea igual pero alerta en log
        if not image_url:
            print(f"⚠️ AVISO: Producto SKU {sku} no tiene imagen válida detectada. Se sincronizará de todos modos para revisión.")

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
            # CATEGORÍAS ELIMINADAS: NO pasamos `categories`
        }
        
        try:
            if existing_product:
                self.wcapi.put(f"products/{existing_product['id']}", payload)
            else:
                if image_url:
                    payload["images"] = [{"src": image_url}]
                self.wcapi.post("products", payload)
            
            # LOG FINAL EXIGIDO
            print(f"✅ Sincronizado Global: {sku} | MPN: {mpn} | Precio: ${final_price_str}")
            return True, "Sincronizado"
        except Exception as e:
            print(f"❌ Error sincronizando {sku}: {e}")
            return False, "Error Sincro"

    def archive_orphan(self, product_data):
        pass