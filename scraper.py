def scrape_category(self, url):
        self.page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        category_name = self.page.title().split("-")[0].strip()
        
        product_urls = []
        # Selector más específico para evitar basura
        items = self.page.locator("article.prod_item a").all()
        
        for item in items:
            href = item.get_attribute("href")
            if href and len(href) > 2 and not href.startswith(("javascript:", "#")):
                # Construcción segura de URL
                if href.startswith("http"):
                    full_url = href
                else:
                    # Limpiamos posibles barras dobles
                    clean_href = href if href.startswith("/") else f"/{href}"
                    full_url = f"https://www.cdrmedios.com{clean_href}"
                
                if full_url not in product_urls: 
                    product_urls.append(full_url)
        
        products_data = []
        for link in product_urls[:20]:
            try:
                # Si el link es inválido, Page.goto fallará aquí; por eso el try/except
                self.page.goto(link, wait_until="domcontentloaded", timeout=20000)
                
                # SKU
                sku = ""
                sku_loc = self.page.locator("tr:has-text('Código') .data span").first
                if sku_loc.count() > 0:
                    sku = sku_loc.inner_text().strip()
                
                if not sku:
                    continue

                # --- PRECIO CON MANEJO DE TIMEOUT ---
                try:
                    price_locator = self.page.locator(".product-price, .price-value-2").first
                    # Esperamos máximo 5 segundos por el precio
                    price_locator.wait_for(state="visible", timeout=5000)
                    p_text = price_locator.inner_text()
                    price = float(p_text.replace("USD", "").replace("$", "").replace(",", "").strip())
                except Exception:
                    print(f"⚠️ No se pudo obtener precio para {sku}, saltando...")
                    continue

                product = {
                    'name': self.page.locator("h1").first.inner_text().strip(),
                    'sku': sku,
                    'mpn': "N/A", # Puedes mejorar la captura del MPN igual que el SKU
                    'net_price': price,
                    'in_stock': self.page.get_by_text("Sin Stock").count() == 0,
                    'image_url': self.page.locator(".gallery img").first.get_attribute("src")
                }
                print(f"✅ {product['sku']} | ${product['net_price']}")
                products_data.append(product)

            except Exception as e:
                print(f"❌ Error procesando ficha {link}: {e}")
                continue
                
        return category_name, products_data