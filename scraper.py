def scrape_category(self, url):
        self.page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        category_name = self.page.title().split("-")[0].strip()
        
        product_urls = []
        # Buscamos solo los links que DE VERDAD llevan a la ficha del producto
        items = self.page.locator("article.prod_item a").all()
        
        for item in items:
            href = item.get_attribute("href")
            # FILTRO CRÍTICO: Si no hay href, o es un javascript, o es el carrito, lo saltamos
            if not href or "javascript" in href or "carrito" in href or href == "#":
                continue
                
            # Construcción limpia de la URL
            if href.startswith("http"):
                full_url = href
            else:
                clean_href = href if href.startswith("/") else f"/{href}"
                full_url = f"https://www.cdrmedios.com{clean_href}"
            
            if full_url not in product_urls: 
                product_urls.append(full_url)
        
        products_data = []
        # Limitamos a 20 para no saturar, puedes subirlo luego
        for link in product_urls[:20]:
            try:
                print(f"🔗 Entrando a: {link}")
                self.page.goto(link, wait_until="domcontentloaded", timeout=15000)
                
                # SKU
                sku = ""
                sku_loc = self.page.locator("tr:has-text('Código') .data span").first
                if sku_loc.count() > 0:
                    sku = sku_loc.inner_text().strip()
                
                if not sku:
                    continue

                # PRECIO (Usando la clase .pprecio que encontraste en el inspector)
                try:
                    # Probamos primero con tu hallazgo .pprecio, luego los otros por si acaso
                    price_locator = self.page.locator(".pprecio, .product-price, .price-value-2").first
                    price_locator.wait_for(state="visible", timeout=5000)
                    p_text = price_locator.inner_text()
                    # Limpiamos todo lo que no sea número o punto
                    price_digits = "".join(c for c in p_text if c.isdigit() or c == "." or c == ",")
                    price = float(price_digits.replace(",", "."))
                except Exception:
                    print(f"⚠️ Precio no hallado en {sku}, saltando...")
                    continue

                product = {
                    'name': self.page.locator("h1").first.inner_text().strip(),
                    'sku': sku,
                    'mpn': "N/A",
                    'net_price': price,
                    'in_stock': self.page.get_by_text("Sin Stock").count() == 0,
                    'image_url': self.page.locator(".gallery img").first.get_attribute("src")
                }
                print(f"✅ SKU: {product['sku']} | Precio: ${product['net_price']}")
                products_data.append(product)

            except Exception as e:
                print(f"❌ Error en ficha: {e}")
                continue
                
        return category_name, products_data