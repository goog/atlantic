import asyncio
import json
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def scrape_atlantic_latest():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("https://www.theatlantic.com/latest/")
        await page.wait_for_timeout(3000)

        html = await page.content()
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen = set()

    for art in soup.find_all("article"):
        links = art.find_all("a", href=True)
        main_link = next(
            (l for l in links if re.search(r"/\d{4}/\d{2}/", l["href"])), None
        )
        if not main_link:
            continue
        href = main_link["href"]
        if href in seen:
            continue
        seen.add(href)

        title_el = art.find(["h2", "h3", "h1"])
        title = title_el.get_text(strip=True) if title_el else ""

        p_tags = art.find_all("p")
        desc = next(
            (p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 30), ""
        )[:200]

        img = art.find("img")
        img_src = ""
        if img:
            src = img.get("src", "")
            srcset = img.get("srcset", "")
            img_src = src if src and not src.endswith(".svg") else ""
            if not img_src and srcset:
                img_src = srcset.split(",")[-1].strip().split(" ")[0]

        author = ""
        for el in art.find_all(["span", "div", "a"]):
            cls = " ".join(el.get("class", []))
            txt = el.get_text(strip=True)
            if not txt:
                continue
            if any(k in cls.lower() for k in ["author", "byline", "name", "writer"]):
                author = txt
                break

        cat_match = re.match(r"^/([^/]+)/", href)
        category = cat_match.group(1).replace("-", " ").title() if cat_match else ""

        title = re.sub(r"\s+", " ", title).strip()
        author = author.replace("andEric", "and Eric").replace("andJon", "and Jon")

        articles.append({
            "title": title,
            "url": "https://www.theatlantic.com" + href if href.startswith("/") else href,
            "description": desc,
            "author": author,
            "category": category,
            "image": img_src,
        })

    with open("atlantic_articles.json", "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"✅ 共抓取 {len(articles)} 篇文章，已保存至 atlantic_articles.json")
    return articles


if __name__ == "__main__":
    asyncio.run(scrape_atlantic_latest())
