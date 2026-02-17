import time
import sys
import config  # Importa el archivo config.py que acabamos de crear

# Intentamos importar los módulos. Si faltan, avisamos para que no te vuelvas loco.
try:
    from scraper import CDRScraper
    from woo_manager import WooManager
except ImportError as e:
    print("❌ ERROR CRÍTICO: Faltan archivos del proyecto.")
    print(f"Detalle: {e}")
    print("Asegúrate de que 'scraper.py' y 'woo_manager.py' están en la misma carpeta.")
    sys.exit(1)

def main():
    print("🚀 Iniciando Sincronización CDR -> WooCommerce...")
    
    # 1. Verificar Configuración antes de arrancar
    if not config.TARGET_URLS:
        print("❌ ERROR: No hay URLs configuradas en TARGET_URLS.")
        print("Revisa los 'Secrets' en GitHub o tu archivo .env")
        return

    # 2. Inicializar Componentes
    try:
        # headless=True es OBLIGATORIO para GitHub Actions (no tiene pantalla)
        scraper = CDRScraper(headless=True)
        wm = WooManager()
    except Exception as e:
        print(f"❌ Error inicializando clases: {e}")
        return

    # 3. Iniciar Scraping
    try:
        scraper.start()
        if not scraper.login():
            print("❌ LOGIN FALLIDO: Revisa usuario/contraseña en GitHub Secrets.")
            scraper.stop()
            sys.exit(1) # Salimos con error para que GitHub te avise por email
    except Exception as e:
        print(f"❌ Error durante el login: {e}")
        scraper.stop()
        return

    # 4. Procesar cada URL
    for url in config.TARGET_URLS:
        try:
            print(f"\n--- 🔎 Procesando URL: {url} ---")
            
            # A) Scraping
            try:
                cat_name, products = scraper.scrape_category(url)
            except Exception as e:
                print(f"⚠️ Error escrapeando {url}: {e}")
                continue # Saltamos a la siguiente URL, no paramos todo

            print(f"📂 Categoría detectada: '{cat_name}'")
            print(f"📦 Productos encontrados en proveedor: {len(products)}")
            
            if not products:
                print("Total: 0 productos. Saltando sincronización de esta categoría.")
                continue

            # B) Mapeo de Categoría en Woo
            cat_id = wm.get_category_id_by_name(cat_name)
            
            if not cat_id:
                print(f"⚠️ AVISO: La categoría '{cat_name}' no existe en tu tienda.")
                # Aquí podrías llamar a wm.create_category(cat_name) si quisieras
            else:
                print(f"✅ ID Categoría WooCommerce: {cat_id}")
            
            # C) Obtener productos existentes (para saber cuáles borrar/ocultar después)
            if cat_id:
                existing_products_map = wm.get_all_products(category_id=cat_id)
            else:
                existing_products_map = {} 

            # Contadores
            processed_skus = set()
            new_count = 0
            updated_count = 0
            
            # D) Bucle de Sincronización (Alta/Modificación)
            for p_data in products:
                sku = p_data['sku']
                processed_skus.add(sku)
                
                existing = existing_products_map.get(sku)
                
                # Asignar ID de categoría si lo tenemos
                if cat_id:
                    p_data['category_ids'] = [cat_id]
                
                try:
                    # sync_product debería manejar la lógica de PRECIOS (IVA + Ganancia) internamente
                    result = wm.sync_product(p_data, existing)
                    if existing:
                        updated_count += 1
                    else:
                        new_count += 1
                except Exception as e:
                    print(f"❌ Error sincronizando SKU {sku}: {e}")
            
            # E) Procesar Huérfanos (Productos que desaparecieron de CDR)
            orphans_count = 0
            if cat_id and existing_products_map:
                for sku, p_data in existing_products_map.items():
                    if sku not in processed_skus:
                        # Si estaba en Woo pero NO apareció en el scrape de hoy -> Stock 0 / Ocultar
                        try:
                            wm.archive_orphan(p_data)
                            orphans_count += 1
                            print(f"📉 Producto descatalogado (Stock 0): {sku}")
                        except Exception as e:
                            print(f"❌ Error archivando {sku}: {e}")

            # Reporte final de la categoría
            print(f"\n📊 RESUMEN '{cat_name}':")
            print(f"   ➤ Escrapeados: {len(products)}")
            print(f"   ➤ Nuevos: {new_count}")
            print(f"   ➤ Actualizados: {updated_count}")
            print(f"   ➤ Ocultados (Sin Stock): {orphans_count}")
            
        except Exception as e:
            print(f"❌ Error general en URL {url}: {e}")
            import traceback
            traceback.print_exc()

    # 5. Limpieza final
    scraper.stop()
    print("\n✅ Proceso Finalizado Exitosamente.")

if __name__ == "__main__":
    main()