from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Load state
        context = browser.new_context(storage_state="state.json")
        page = context.new_page()
        
        # Target URL
        url = "https://www.cdrmedios.com/catalogo/notebook-pc-tablet/equipos-nuevos/notebooks/"
        print(f"Navigating to {url}...")
        try:
            page.goto(url)
            page.wait_for_load_state('networkidle')
            
            # Save full HTML
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Saved page_source.html")

        except Exception as e:
            print(f"Error: {e}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    run()
