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
        self.page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        category_name = self.page.title().split("-")[0].strip()
        
        product_urls = []
        # Capturamos todos los links de productos dentro de los articles
        items = self.page.locator("article.prod_item a").all()
        
        for item in items:
            href = item.get_attribute("href")
            
            # FILTRO CRÍTICO: Evitamos funciones de JavaScript que rompen el script
            if not href or "javascript" in href or "carrito" in href or href == "#":
                continue
                
            # Construcción segura de la URL completa
            if href.startswith("http"):
                full_url = href
            else:
                clean_href = href if href.startswith("/") else f"/{href}"
                full_url = f"https://www.cdrmedios.com{clean_href}"
            
            if full_url not in product_urls: 
                product_urls.append(full_url)
        
        products_data = []
        # Procesamos las primeras 20 fichas (puedes aumentar este número después)
        for link in product_urls[:20]:
            try:
                print(f"🔗 Procesando ficha: {link}")
                self.page.goto(link, wait_until="domcontentloaded", timeout=20000)
                
                # 1. Extracción de SKU (EQU1177, etc.)
                sku = ""
                sku_loc = self.page.locator("tr:has-text('Código') .data span").first
                if sku_loc.count() > 0:
                    sku = sku_loc.inner_text().strip()
                
                if not sku:
                    print(f"⚠️ Sin SKU en {link}, saltando...")
                    continue

                # 2. Extracción de Precio (USD 920)
                price = 0.0
                try:
                    # Probamos múltiples selectores incluyendo el .pprecio que vimos en el inspector
                    price_loc = self.page.locator(".pprecio, span[itemprop='price'], .price-value-2").first
                    price_loc.wait_for(state="visible", timeout=7000)
                    p_text = price_loc.inner_text()
                    # Limpiamos: dejamos solo números y puntos
                    price_clean = "".join(c for c in p_text if c.isdigit() or c == ".").replace(",", ".")
                    price = float(price_clean)
                except Exception:
                    print(f"❌ No se detectó precio para {sku}. Saltando producto.")
                    continue

                # 3. Detección de Stock (Botón Comprar)
                # Si existe el botón de compra y no hay carteles de "Sin Stock", hay existencias
                btn_comprar = self.page.locator("button:has-text('COMPRAR'), .btn-comprar, .buy-button").first
                msg_sin_stock = self.page.get_by_text("Sin Stock", exact=False)
                
                has_stock = (btn_comprar.count() > 0 and btn_comprar.is_visible()) and \
                            (msg_sin_stock.count() == 0 or not msg_sin_stock.first.is_visible())

                # 4. Otros datos (Nombre, Imagen, MPN)
                name = self.page.locator("h1").first.inner_text().strip()
                image_loc = self.page.locator(".gallery img, .product-main-image img").first
                image_url = image_loc.get_attribute("src") if image_loc.count() > 0 else ""

                products_data.append({
                    'name': name,
                    'sku': sku,
                    'mpn': "N/A",
                    'net_price': price,
                    'in_stock': has_stock,
                    'image_url': image_url
                })
                print(f"✅ {sku} | Stock: {has_stock} | Precio Base: ${price}")

            except Exception as e:
                print(f"❌ Error crítico en ficha {link}: {e}")
                continue
                
        return category_name, products_data