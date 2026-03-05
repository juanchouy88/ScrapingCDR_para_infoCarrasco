from playwright.sync_api import sync_playwright
import time
import os
import random
import config

class CDRScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.state_file = "state.json"
        self.browser = None
        self.playwright = None
        self.context = None
        self.page = None
        # User-Agent moderno para evasión anti-bot
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        context_args = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1920, "height": 1080}
        }
        
        if os.path.exists(self.state_file):
            context_args["storage_state"] = self.state_file
            
        self.context = self.browser.new_context(**context_args)
        self.page = self.context.new_page()

    def stop(self):
        if self.context: self.context.close()
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
        items = self.page.locator("article.prod_item a").all()
        
        for item in items:
            href = item.get_attribute("href")
            
            # FILTRO ESTRICTO: Ignorar javascript:, updown_carrito, y #
            if not href or "javascript" in href.lower() or "updown_carrito" in href.lower() or "#" in href:
                continue
            if "/catalogo/" not in href:
                continue
                
            if href.startswith("http"):
                full_url = href
            else:
                clean_href = href if href.startswith("/") else f"/{href}"
                full_url = f"https://www.cdrmedios.com{clean_href}"
            
            if full_url not in product_urls: 
                product_urls.append(full_url)
        
        products_data = []
        print(f"✅ Se encontraron {len(product_urls)} productos en la categoría.")

        for link in product_urls:
            try:
                # Pausa aleatoria entre 3 y 7 segundos (SIGILO ANTI-BOT)
                pause_time = random.uniform(3, 7)
                print(f"⏳ Pausa de {pause_time:.2f}s... ", end="")
                time.sleep(pause_time)
                
                print(f"🔗 Procesando ficha: {link}")
                
                try:
                    self.page.goto(link, wait_until="domcontentloaded", timeout=45000)
                    self.page.wait_for_selector(".ficha_tecnica, .gendata", timeout=15000)
                except Exception as net_e:
                    print(f"⚠️ Error de red o Timeout al cargar {link}: {net_e}")
                    products_data.append({
                        'error': True,
                        'url': link
                    })
                    continue

                sku = ""
                mpn = "N/A"
                
                sku_loc = self.page.locator(".gendata tr:has-text('Código') .data span, .gendata tr:has-text('Código') td:nth-child(2)").first
                if sku_loc.count() > 0:
                    sku = sku_loc.inner_text().strip()

                mpn_loc = self.page.locator(".gendata tr:has-text('Nro de parte') .data span, .gendata tr:has-text('Nro de parte') td:nth-child(2)").first
                if mpn_loc.count() > 0:
                    mpn = mpn_loc.inner_text().strip()
                
                if not sku:
                    print(f"⚠️ NO SE ENCONTRÓ SKU VÁLIDO en {link}. Saltando...")
                    continue

                # Extracción de Precio con limpieza estricta
                price = 0.0
                try:
                    price_loc = self.page.locator(".pprecio, span[itemprop='price'], .price-value-2").first
                    if price_loc.is_visible():
                        p_text = price_loc.inner_text().strip()
                        # Limpieza estricta: eliminar USD, U$S, $, coma y espacios
                        p_clean = p_text.upper().replace("USD", "").replace("U$S", "").replace("$", "").replace(",", "").strip()
                        # Extraer solo numeros y punto decimal
                        p_clean = ''.join(c for c in p_clean if c.isdigit() or c == '.')
                        
                        # En caso de múltiples puntos, conservar el último si funciona como decimal, 
                        # pero si el formato es solo números, lo parseamos directo.
                        parts = p_clean.split('.')
                        if len(parts) > 2:
                            p_clean = ''.join(parts[:-1]) + '.' + parts[-1]
                            
                        price = float(p_clean) if p_clean else 0.0
                except Exception:
                    price = 0.0

                msg_sin_stock = self.page.get_by_text("Sin Stock", exact=False)
                has_no_stock_msg = msg_sin_stock.count() > 0 and msg_sin_stock.first.is_visible()
                has_stock = not has_no_stock_msg

                name_loc = self.page.locator("h1").first
                name = name_loc.inner_text().strip() if name_loc.count() > 0 else "Sin Nombre"
                
                # Sistema de Respaldo de Imágenes (Fallback)
                image_url = ""
                img_selectors = [
                    ".gallery .picture img",
                    "#main-product-img",
                    ".product-essential img",
                    ".ficha_tecnica img",
                    ".product-main-image img"
                ]
                for sel in img_selectors:
                    img_loc = self.page.locator(sel).first
                    if img_loc.count() > 0 and img_loc.is_visible():
                        src = img_loc.get_attribute("src")
                        if src:
                            # Asegurar que la URL sea absoluta
                            if not src.startswith("http"):
                                src = f"https://www.cdrmedios.com{src if src.startswith('/') else '/' + src}"
                            image_url = src
                            break

                products_data.append({
                    'error': False,
                    'name': name,
                    'sku': sku,
                    'mpn': mpn,
                    'net_price': price,
                    'in_stock': has_stock,
                    'image_url': image_url
                })

            except Exception as e:
                print(f"❌ Error interno procesando {link}: {e}")
                products_data.append({'error': True, 'url': link})
                continue
                
        return category_name, products_data