from woocommerce import API
import config
import time

class WooManager:
    def __init__(self):
        # Conectamos con la Tienda usando las claves del config
        self.wcapi = API(
            url=config.WOO_URL,
            consumer_key=config.WOO_KEY,
            consumer_secret=config.WOO_SECRET,
            version="wc/v3",
            timeout=30
        )

    def calculate_price(self, net_price):
        """
        Calcula el precio final: (Neto * IVA) * Margen
        """
        if not net_price:
            return 0
        try:
            # Usamos las variables definidas en config.py
            price_with_iva = float(net_price) * config.IVA_RATE
            final_price = price_with_iva * config.MARGIN_RATE
            return int(round(final_price, 0))
        except Exception as e:
            print(f"Error calculando precio: {e}")
            return 0

    def get_category_id_by_name(self, name):
        """
        Busca el ID de una categoría por su nombre (CORREGIDO para evitar errores)
        """
        print(f"🔍 Buscando categoría '{name}' en WooCommerce...")
        try:
            res = self.wcapi.get("products/categories", params={"search": name})
            
            if res.status_code == 200:
                cats = res.json()
                
                # --- CORRECCIÓN CRÍTICA ---
                # Verificamos si la respuesta es realmente una Lista antes de leerla.
                if isinstance(cats, list):
                    for c in cats:
                        # Verificamos que el nombre coincida
                        if c.get("name", "").lower() == name.lower():
                            return c["id"]
                    print(f"⚠️ Categoría '{name}' no encontrada en la búsqueda.")
                    return None
                else:
                    # Si Woo devuelve un diccionario (error), lo mostramos y no rompemos el script
                    print(f"⚠️ Respuesta inesperada de Woo (No es lista): {cats}")
                    return None
            else:
                print(f"❌ Error API buscando categoría ({res.status_code}): {res.text}")
                return None
                
        except Exception as e:
            print(f"❌ Excepción buscando categoría: {e}")
            return None

    def get_all_products(self, category_id=None):
        """
        Descarga todos los productos existentes para comparar (stock, precios, etc.)
        """
        products_map = {}
        page = 1
        params = {"per_page": 50}
        
        if category_id:
            params["category"] = category_id

        print(f"📥 Descargando catálogo actual (Cat ID: {category_id})...")
        
        while True:
            params["page"] = page
            try:
                res = self.wcapi.get("products", params=params)
                
                if res.status_code != 200:
                    print(f"Error leyendo productos: {res.status_code}")
                    break
                    
                data = res.json()
                if not data:
                    break # Se acabaron las páginas
                
                # Seguridad: Verificar que data sea lista
                if isinstance(data, list):
                    for p in data:
                        if p.get("sku"):
                            products_map[p["sku"]] = p
                else:
                    print(f"Error: La API devolvió datos inválidos en página {page}")
                    break

                print(f"   Página {page} cargada...")
                page += 1
                
            except Exception as e:
                print(f"Error paginación: {e}")
                break
            
        return products_map

    def sync_product(self, scraped_data, existing_product=None):
        """
        Crea o Actualiza un producto en la tienda
        """
        sku = scraped_data['sku']
        final_price = str(self.calculate_price(scraped_data.get('net_price', 0)))
        
        # Datos base del producto
        payload = {
            "sku": sku,
            "name": scraped_data['name'],
            "regular_price": final_price,
            "description": scraped_data.get('description', ''),
            "manage_stock": True,
            "stock_quantity": 10 if scraped_data['in_stock'] else 0,
            # Si hay stock -> Publicado y Visible. Si no -> Borrador y Oculto.
            "status": "publish" if scraped_data['in_stock'] else "draft", 
            "catalog_visibility": "visible" if scraped_data['in_stock'] else "hidden"
        }

        # Imágenes: Solo las agregamos si es producto NUEVO (para no ralentizar updates)
        if not existing_product and scraped_data.get('image_url'):
            payload["images"] = [{"src": scraped_data['image_url']}]

        # Categoría: Solo al crear
        if not existing_product and scraped_data.get('category_ids'):
            payload["categories"] = [{"id": cid} for cid in scraped_data['category_ids']]
        
        try:
            if existing_product:
                # --- ACTUALIZAR ---
                pid = existing_product['id']
                # Actualizamos precio, stock y estado
                self.wcapi.put(f"products/{pid}", payload)
                # print(f"🔄 Actualizado: {sku}")
            else:
                # --- CREAR ---
                res = self.wcapi.post("products", payload)
                if res.status_code in [200, 201]:
                    print(f"✨ Creado nuevo producto: {sku}")
                else:
                    print(f"❌ Falló creación {sku}: {res.text}")
                    
        except Exception as e:
            print(f"❌ Error sincronizando {sku}: {e}")

    def archive_orphan(self, product_data):
        """
        Desactiva productos que ya no existen en el proveedor
        """
        pid = product_data['id']
        sku = product_data.get('sku', 'Unknown')
        
        payload = {
            "stock_quantity": 0,
            "status": "draft",
            "catalog_visibility": "hidden"
        }
        try:
            self.wcapi.put(f"products/{pid}", payload)
            # print(f"👻 Archivado huérfano: {sku}")
        except Exception as e:
            print(f"Error archivando {sku}: {e}")

# Bloque de prueba local (opcional)
if __name__ == "__main__":
    wm = WooManager()
    print(f"Prueba de cálculo (100 + 22% + 30%): {wm.calculate_price(100)}")