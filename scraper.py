from playwright.sync_api import sync_playwright
import time
import os
import config

class CDRScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.state_file = "state.json"
        self.browser = None

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        if os.path.exists(self.state_file):
            self.context = self.browser.new_context(storage_state=self.state_file)
        else:
            self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def stop(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()

    def login(self):
        try:
            self.page.goto("https://www.cdrmedios.com/")
            if self.page.locator(".nombre_usuario, .cerrar2").count() > 0: return True
            self.page.get_by_text("Ingresar").first.click()
            self.page.locator("#login_usuario").fill(config.CDR_USER)
            self.page.locator("#login_clave").fill(config.CDR_PASS)
            self.page.locator("#btn_login_submit").click()
            time.sleep(3)
            if self.page.locator(".nombre_usuario").count() > 0:
                self.context.storage_state(path=self.state_file)
                return True
            return False
        except: return False

    def scrape_category(self, url):
        print(f"🔎 Accediendo a categoría: {url}")
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
        except Exception as e:
            print(f"❌ Error al cargar la categoría {url}: {e}")
            return "Error", []

        category_name = self.page.title().split("-")[0].strip()
        
        product_urls = []
        # Capturamos todos los links de productos dentro de los articles
        items = self.page.locator("article.prod_item a").all()
        
        for item in items:
            href = item.get_attribute("href")
            
            # FILTRO ESTRICTO: Ignoramos javascript, vacíos, o rutas sin /catalogo/
            if not href or "javascript" in href.lower() or "/catalogo/" not in href:
                continue
                
            # Construcción segura de la URL absoluta
            if href.startswith("http"):
                full_url = href
            else:
                # Aseguramos que la ruta relativa empiece con /
                clean_href = href if href.startswith("/") else f"/{href}"
                full_url = f"https://www.cdrmedios.com{clean_href}"
            
            # Validación final de URL
            if full_url not in product_urls: 
                product_urls.append(full_url)
        
        products_data = []
        print(f"✅ Se encontraron {len(product_urls)} productos en la categoría.")

        # Procesamos los productos encontrados
        for link in product_urls:
            try:
                print(f"🔗 Procesando ficha: {link}")
                self.page.goto(link, wait_until="domcontentloaded", timeout=30000)
                
                # Esperar a que la tabla técnica esté presente para asegurar carga
                try:
                    self.page.wait_for_selector(".ficha_tecnica", timeout=10000)
                except:
                    print(f"⚠️ Tabla técnica no detectada en {link}, intentando leer igual...")

                # 1. Extracción de SKU (EQU1177, etc.)
                sku = ""
                # Selector específico para la fila 'Código'
                sku_loc = self.page.locator("tr:has-text('Código') .data span").first
                if sku_loc.count() > 0:
                    sku = sku_loc.inner_text().strip()
                
                # SI NO HAY SKU, SALTAMOS EL PRODUCTO (Evita SKUs fake/temp)
                if not sku:
                    print(f"⚠️ NO SE ENCONTRÓ SKU VÁLIDO en {link}. Saltando...")
                    continue

                # 2. Extracción de MPN (Nro de parte)
                mpn = "N/A"
                mpn_loc = self.page.locator("tr:has-text('Nro de parte') .data span").first
                if mpn_loc.count() > 0:
                    mpn = mpn_loc.inner_text().strip()

                # 3. Extracción de Precio
                price = 0.0
                try:
                    price_loc = self.page.locator(".pprecio, span[itemprop='price'], .price-value-2").first
                    if price_loc.is_visible():
                        p_text = price_loc.inner_text()
                        price_clean = "".join(c for c in p_text if c.isdigit() or c == ".").replace(",", ".")
                        price = float(price_clean)
                except Exception:
                    pass # Si falla precio, queda en 0.0

                # 4. Detección de Stock MEJORADA
                # Lógica: Botón comprar visible O indicador de stock > 0
                btn_comprar = self.page.locator("button.btn_comprar, .btn-comprar, button:has-text('COMPRAR')").first
                
                # A veces el sitio usa un input hidden o un div con la cantidad
                # Buscamos si hay un indicador explícito de "Sin Stock"
                msg_sin_stock = self.page.get_by_text("Sin Stock", exact=False)
                
                # Determinamos stock
                is_buyable = btn_comprar.count() > 0 and btn_comprar.is_visible()
                has_no_stock_msg = msg_sin_stock.count() > 0 and msg_sin_stock.first.is_visible()
                
                has_stock = is_buyable and not has_no_stock_msg

                # 5. Otros datos
                name_loc = self.page.locator("h1").first
                name = name_loc.inner_text().strip() if name_loc.count() > 0 else "Sin Nombre"
                
                image_loc = self.page.locator(".gallery img, .product-main-image img").first
                image_url = image_loc.get_attribute("src") if image_loc.count() > 0 else ""

                # Agregar producto validado
                products_data.append({
                    'name': name,
                    'sku': sku,
                    'mpn': mpn,
                    'net_price': price,
                    'in_stock': has_stock,
                    'image_url': image_url
                })
                print(f"   -> SKU: {sku} | MPN: {mpn} | Stock: {has_stock} | ${price}")

            except Exception as e:
                print(f"❌ Error procesando {link}: {e}")
                continue
                
        return category_name, products_data