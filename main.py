import time
import sys
import config

try:
    from scraper import CDRScraper
    from woo_manager import WooManager
except ImportError as e:
    print("❌ ERROR CRÍTICO: Faltan archivos del proyecto.")
    print(f"Detalle: {e}")
    sys.exit(1)

def main():
    print("🚀 Iniciando Sincronización CDR -> WooCommerce v2.1 (Global)...")
    
    if not getattr(config, 'TARGET_URLS', None):
        print("❌ ERROR: No hay URLs configuradas en TARGET_URLS.")
        return

    try:
        scraper = CDRScraper(headless=True)
        wm = WooManager()
    except Exception as e:
        print(f"❌ Error inicializando clases: {e}")
        return

    try:
        scraper.start()
        if not scraper.login():
            print("❌ LOGIN FALLIDO: Revisa usuario/contraseña.")
            scraper.stop()
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error durante el login: {e}")
        scraper.stop()
        return

    # Cargar todos los productos de WooCommerce de forma global antes del bucle de URLs
    existing_products_map = wm.get_all_products()

    for url in config.TARGET_URLS:
        try:
            print(f"\n--- 🔎 Procesando URL: {url} ---")
            
            try:
                cat_name, products = scraper.scrape_category(url)
            except Exception as e:
                print(f"⚠️ Error escrapeando {url}: {e}")
                continue 

            print(f"📦 Productos encontrados en proveedor (intentos): {len(products)}")
            
            if not products:
                print("Total: 0 productos. Saltando sincronización interina.")
                continue

            processed_skus = set()
            new_count = 0
            updated_count = 0
            skipped_errors = 0
            
            for p_data in products:
                if p_data.get('error'):
                    skipped_errors += 1
                    continue
                    
                sku = p_data.get('sku')
                if not sku:
                    skipped_errors += 1
                    continue
                    
                processed_skus.add(sku)
                existing = existing_products_map.get(sku)
                
                # Cero mapeos de categorías (eliminado)
                
                try:
                    success, reason = wm.sync_product(p_data, existing)
                    if success:
                        if existing:
                            updated_count += 1
                        else:
                            new_count += 1
                            # Añadir a la lista local para no duplicar si otra URL trae el mismo producto en la misma corrida
                            existing_products_map[sku] = {'id': 'temp-added', 'sku': sku} 
                    else:
                        if reason in ["Error", "Sin SKU", "Error Precio"]:
                            skipped_errors += 1
                except Exception as e:
                    print(f"❌ Error sincronizando SKU {sku}: {e}")
            
            print(f"\n📊 RESUMEN (Global loop -> {url}):")
            print(f"   ➤ Escrapeados Totales Intento: {len(products)}")
            print(f"   ➤ Nuevos: {new_count}")
            print(f"   ➤ Actualizados: {updated_count}")
            print(f"   ➤ Saltados por error de lectura: {skipped_errors}")
            
        except Exception as e:
            print(f"❌ Error general en URL {url}: {e}")
            import traceback
            traceback.print_exc()

    scraper.stop()
    print("\n✅ Proceso Finalizado Exitosamente (v2.1).")

if __name__ == "__main__":
    main()