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
        self.page.goto(url)
        time.sleep(2)
        category_name = self.page.title().split("-")[0].strip()
        
        product_urls = []
        items = self.page.locator("article.prod_item a").all()
        for item in items:
            href = item.get_attribute("href")
            if href:
                full_url = "https://www.cdrmedios.com" + href if not href.startswith("http") else href
                if full_url not in product_urls: product_urls.append(full_url)
        
        products_data = []
        for link in product_urls[:20]:
            try:
                self.page.goto(link)
                
                # --- EXTRACCIÓN MEJORADA ---
                # SKU (Código del proveedor, ej: NOT3091)
                sku = ""
                sku_loc = self.page.locator("tr:has-text('Código') .data span").first
                if sku_loc.count() > 0:
                    sku = sku_loc.inner_text().strip()
                
                # Si no hay SKU real, NO lo procesamos para evitar duplicados TEMP
                if not sku:
                    print(f"⚠️ Saltando producto sin SKU claro en: {link}")
                    continue

                # MPN (Número de parte)
                mpn = "N/A"
                mpn_loc = self.page.locator("tr:has-text('Nro de parte') .data span").first
                if mpn_loc.count() > 0:
                    mpn = mpn_loc.inner_text().strip()
                
                # Precio (Corregido para manejar decimales)
                p_text = self.page.locator(".product-price, .price-value-2").first.inner_text()
                price = float(p_text.replace("USD", "").replace("$", "").replace(",", "").strip())
                
                product = {
                    'name': self.page.locator("h1").first.inner_text().strip(),
                    'sku': sku,
                    'mpn': mpn,
                    'net_price': price,
                    'in_stock': self.page.get_by_text("Sin Stock").count() == 0,
                    'image_url': self.page.locator(".gallery img").first.get_attribute("src")
                }
                print(f"✅ {product['sku']} | MPN: {product['mpn']} | ${product['net_price']}")
                products_data.append(product)
            except Exception as e:
                print(f"❌ Error leyendo ficha: {e}")
                continue
        return category_name, products_data