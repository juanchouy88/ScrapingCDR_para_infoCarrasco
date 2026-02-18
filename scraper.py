from playwright.sync_api import sync_playwright, Page
import time
import os
import config
import uuid

class CDRScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.state_file = "state.json"

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        # Load state if exists
        if os.path.exists(self.state_file):
            print(f"Loading session from {self.state_file}")
            self.context = self.browser.new_context(storage_state=self.state_file)
        else:
            self.context = self.browser.new_context()
        
        self.page = self.context.new_page()

    def stop(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def login(self):
        print("Attempting login...")
        try:
            self.page.goto("https://www.cdrmedios.com/")
            self.page.wait_for_load_state('networkidle')
            
            # Check if already logged in
            if self.page.locator(".nombre_usuario").is_visible() or self.page.locator(".cerrar2").is_visible():
                print("Already logged in (Session active).")
                return True

            # Click Ingresar
            print("Clicking Ingresar...")
            ingresar_btn = self.page.get_by_text("Ingresar", exact=False).first
            if ingresar_btn.is_visible():
                ingresar_btn.click()
                self.page.wait_for_load_state('networkidle')
            else:
                print("Ingresar button not found and not logged in?")
                self.page.screenshot(path="login_debug.png")
                return False

            # Check if we are on login page (inputs exist)
            if self.page.locator("#login_usuario").is_visible():
                print("Filling credentials...")
                self.page.locator("#login_usuario").fill(config.CDR_USER)
                self.page.locator("#login_clave").fill(config.CDR_PASS)
                self.page.locator("#btn_login_submit").click()
                
                print("Submitted login. Waiting for navigation...")
                self.page.wait_for_load_state('networkidle')
                # Wait a bit for redirect
                time.sleep(3)
                
                # Verify login success
                if self.page.locator(".nombre_usuario").is_visible() or self.page.locator(".cerrar2").is_visible():
                    self.context.storage_state(path=self.state_file)
                    print("Login successful. Session saved.")
                    return True
                else:
                    print("Login failed after submit.")
                    return False
            else:
                print("Login inputs not found after clicking Ingresar.")
                return False
                
        except Exception as e:
            print(f"Login failed: {e}")
            self.page.screenshot(path="login_exception.png")
            return False

    def scrape_category(self, url):
        print(f"Scraping category: {url}")
        self.page.goto(url)
        self.page.wait_for_load_state('networkidle')
        
        # Get Category Name
        category_name = self.page.title().replace(" - CDR Medios", "").strip()
        # Clean specific suffixes if any
        if " - " in category_name:
             category_name = category_name.split(" - ")[0]
        
        print(f"Detected Category Name: {category_name}")
        
        product_urls = []
        
        # 1. Collect all product URLs
        while True:
            # Extract product links on current page
            # Assuming product links are inside "article.prod_item"
            items = self.page.locator("article.prod_item")
            count = items.count()
            print(f"Found {count} items on page to collect links.")
            
            for i in range(count):
                try:
                    # Finds the first <a> inside the product article
                    link_el = items.nth(i).locator("a").first
                    if link_el.count() > 0:
                        link = link_el.get_attribute("href")
                        if link:
                            if not link.startswith('http'):
                                link = "https://www.cdrmedios.com" + link
                            if link not in product_urls:
                                product_urls.append(link)
                except Exception as e:
                    print(f"Error extracting link: {e}")
            
            # Pagination
            next_btn = self.page.locator(".siguiente a")
            if next_btn.count() > 0 and next_btn.is_visible():
                print("Navigating to next page for links...")
                next_btn.click()
                self.page.wait_for_load_state('networkidle')
                time.sleep(2)
            else:
                break
        
        print(f"Collected {len(product_urls)} product URLs. Starting detail scraping...")
        
        products_data = []
        
        # 2. Visit each product page
        for link in product_urls:
            try:
                self.page.goto(link)
                self.page.wait_for_load_state('domcontentloaded')
                
                product = {}
                
                # Name: h1
                if self.page.locator("h1").count() > 0:
                    product['name'] = self.page.locator("h1").first.inner_text().strip()
                else:
                    product['name'] = "Unknown Product"

                # SKU
                # Search for specific text "Código"
                sku = "N/A"
                try:
                    # Look for element containing "Código"
                    sku_elem = self.page.locator("*:has-text('Código')").last
                    if sku_elem.count() > 0:
                        text = sku_elem.inner_text()
                        # Extract text after "Código"
                        # Example: "Código: 12345"
                        if "Código" in text:
                            sku = text.split("Código")[-1].replace(":", "").strip()
                except:
                    pass
                
                if not sku or len(sku) < 2 or " " in sku: # Basic validation
                     sku = f"TEMP-{uuid.uuid4().hex[:8]}"
                product['sku'] = sku

                # MPN - CRITICAL
                mpn = "N/A"
                mpn_loc = self.page.locator("tr:has-text('Nro de parte') .data span").first
                if mpn_loc.count() > 0:
                    mpn = mpn_loc.inner_text().strip()
                product['mpn'] = mpn
                
                # Price
                price_val = 0
                price_loc = self.page.locator(".product-price")
                if price_loc.count() == 0:
                     price_loc = self.page.locator(".price-value-2")
                
                if price_loc.count() > 0:
                    p_text = price_loc.first.inner_text()
                    # Clean: USD, $, ,
                    p_clean = p_text.replace("USD", "").replace("$", "").replace(",", "").strip()
                    # Filter digits
                    p_clean = ''.join(filter(str.isdigit, p_clean))
                    if p_clean:
                        price_val = int(p_clean)
                product['net_price'] = price_val
                    
                # Stock
                in_stock = True
                if self.page.get_by_text("Sin Stock").count() > 0:
                    in_stock = False
                product['in_stock'] = in_stock
                
                # Image
                img_url = ""
                img_loc = self.page.locator(".gallery .picture img").first
                if img_loc.count() == 0:
                     img_loc = self.page.locator("#main-product-img").first
                
                if img_loc.count() > 0:
                    src = img_loc.get_attribute("src")
                    if src:
                        if not src.startswith('http'):
                            img_url = "https://www.cdrmedios.com" + src
                        else:
                            img_url = src
                product['image_url'] = img_url
                
                # Description (keeping as optional/name for now as logic wasn't specified but good to have)
                product['description'] = product['name']

                print(f"✅ Leído: {product['sku']} | MPN: {product['mpn']} | $ {product['net_price']}")
                products_data.append(product)
                    
            except Exception as e:
                print(f"❌ Error scraping {link}: {e}")
                continue
                
        return category_name, products_data

if __name__ == "__main__":
    scraper = CDRScraper(headless=True)
    scraper.start()
    if scraper.login():
        print("Login Successful!")
        # Test scraping first category
        if config.TARGET_URLS:
            cat_name, products = scraper.scrape_category(config.TARGET_URLS[0])
            print(f"Category: {cat_name}")
            print(f"Total products scraped: {len(products)}")
            print("Sample product:", products[0] if products else "None")
    else:
        print("Login Failed.")
    scraper.stop()
