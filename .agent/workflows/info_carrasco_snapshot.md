---
description: Memoria Técnica - Proyecto Informática Carrasco (Sincronizador CDR a WooCommerce)
---

# Project Snapshot: Informática Carrasco (Sincronizador CDR-WooCommerce)

Este documento sirve como contexto persistente o "Skill" para que el Agente recupere las reglas fundamentales y fallos parcheados del scraper de CDR y el manager de WooCommerce. Utiliza esta memoria antes de proponer cambios sobre este código.

## 1. Lógica de Negocio
- **Cálculo de Precios**: El precio final en WooCommerce se calcula tomando el precio neto (costo de CDR), aplicándole el IVA (multiplicado por 1.22) y luego el Margen comercial (multiplicado por 1.30).  
  *Fórmula Estricta:* `round(float(net_price) * 1.22 * 1.30, 0)`. Siempre se debe redondear a 0 decimales y no permitir fracciones raras (ej. 2601.0).
- **Seguridad en la Sincronización (Safety Block)**:
  - **Precios Irreales**: Si el precio resultante (`final_price`) es menor a 10 USD, se aborta y salta el producto (evita publicar cosas rotas a 0 costo).
  - **Carencia Visual**: Si no pudo identificarse una `image_url` funcional, se aborta la actualización para que la tienda no quede rota a nivel de diseño u origen.
  - **Falsos Borradores**: Solo se puede pasar un SKU a "Borrador/Stock 0" si se detecta fehacientemente el tag `Sin Stock` en la página. Si hay problemas de timeout, caídas de conexión, falta de selectores, etc., la orden es SALTAR producto y NO alterarlo.
- **Limpieza de Strings de Precio**: Al extraer el precio original desde la web, remover rigurosamente textos basura como `USD`, `U$S`, `$`, `,` y espacios antes de pasarlo a un tipo `float`.

## 2. Selectores Críticos (Sitio CDR Medios)
- **Extracción de SKU (Código)**: `.gendata tr:has-text('Código') .data span` o `.gendata tr:has-text('Código') td:nth-child(2)`. NUNCA usar prefijos fabricados tipo "TEMP-". Si no hay un Código, ignorar el producto de raíz.
- **Extracción de MPN (Nro de parte)**: `.gendata tr:has-text('Nro de parte') .data span` o `.gendata tr:has-text('Nro de parte') td:nth-child(2)`.
- **Imágenes (Fallback Dinámico)**: Comprobar iterativamente los siguientes extractores visuales para no fallar: `.gallery .picture img`, `#main-product-img`, `.product-essential img`, `.ficha_tecnica img`, `.product-main-image img`.  
  *Nota sobre rutas*: Las URLs extraídas relativas deben convertirse obligatoriamente a absolutas (insertar `https://www.cdrmedios.com` por delante).

## 3. Patrones Anti-Bot y Estabilidad
- **Sigilo (Stealth)**: Aplicar una demora de simulación humana aleatoria con `random.uniform(3, 7)` entre cada carga de URL. 
- **User-Agent**: Es obligatorio disfrazar al headless Chromium usando un User-Agent moderno de escritorio y forzar un `viewport` grande y normal.
- **Filtrado de Enlaces**: Evitar URLs contaminadas dentro de la categoría. Si el string contiene `javascript:`, `#` o `updown_carrito`, es un link muerto u operativo de interfaz y debe ser decartado con un `continue`.

## 4. Parches de Errores Documentados
- **Error WooCommerce Categorías (`TypeError: string indices must be integers`)**:
  Al traer las categorías con la API REST de WooCommerce, el bucle general de Python intentaba llamar en todos los resultados del JSON con un slice de tipo String.  
  *Solución*: Implementar explícitamente `isinstance(c, dict)` iteración por iteración antes de solicitar a su property `.get("name")` para evadir los índices inválidos.
