from playwright.sync_api import sync_playwright, Page
import time
import os
import config

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
        
        all_products = []
        
        while True:
            # Extract products on current page
            items = self.page.locator("article.prod_item").all()
            print(f"Found {len(items)} items on current page.")
            
            for item in items:
                try:
                    product = {}
                    
                    # SKU
                    sku_elem = item.locator(".prodcod [itemprop='sku']")
                    if sku_elem.count() > 0:
                        product['sku'] = sku_elem.inner_text().strip()
                    else:
                        print("Skipping item without SKU")
                        continue
                        
                    # Title
                    name_elem = item.locator("[itemprop='name']")
                    if name_elem.count() > 0:
                        product['name'] = name_elem.inner_text().strip()
                    
                    # Price (Net)
                    price_elem = item.locator("span[itemprop='price']")
                    if price_elem.count() > 0:
                        # Try content attribute first, then text
                        price_val = price_elem.get_attribute("content")
                        if not price_val:
                            price_val = price_elem.inner_text().strip()
                        
                        # Clean price
                        price_val = ''.join(filter(str.isdigit, price_val))
                        product['net_price'] = int(price_val) if price_val else 0
                    
                    # Stock status
                    product['in_stock'] = item.locator(".enstock").count() > 0
                    
                    # Image
                    img_elem = item.locator("img[itemprop='image']")
                    if img_elem.count() > 0:
                        src = img_elem.get_attribute("src")
                        if src and not src.startswith('http'):
                            src = "https://www.cdrmedios.com" + src
                        product['image_url'] = src
                        
                    # Description
                    desc_elem = item.locator("[itemprop='description']")
                    if desc_elem.count() > 0:
                        product['description'] = desc_elem.inner_text().strip()
                    
                    all_products.append(product)
                    
                except Exception as e:
                    print(f"Error extracting item: {e}")
            
            # Pagination
            next_btn = self.page.locator(".siguiente a")
            if next_btn.count() > 0 and next_btn.is_visible():
                print("Navigating to next page...")
                next_btn.click()
                self.page.wait_for_load_state('networkidle')
                time.sleep(2) # Polite wait
            else:
                print("No more pages.")
                break
                
        return category_name, all_products

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
