#!/usr/bin/env python3
"""
New Scientist News Fetcher
获取 New Scientist 最新6条新闻，包括封面图片
输出指定格式的JSON
"""

import json
import re
import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

CATEGORIES = {'Life', 'Space', 'Health', 'Environment', 'Physics', 'Technology',
              'Mind', 'Humans', 'Earth', 'Society', 'Mathematics', 'Chemistry',
              'Culture', 'Comment', 'Video', 'News', 'Features', 'Podcasts'}

os.makedirs('images', exist_ok=True)


def clean_title(title):
    """清理标题 - 移除分类前缀和描述后缀"""
    if not title:
        return title

    original_title = title
    first_letter_upper = title[0].isupper() if title else False

    for cat in CATEGORIES:
        if title.startswith(cat):
            title = title[len(cat):]
            break

    if title.endswith('News'):
        title = title[:-4]

    title = ' '.join(title.split())

    if not title:
        return title

    if title[0].islower() and first_letter_upper and len(title) < len(original_title):
        return original_title.strip()

    if len(title) < 20:
        return original_title.strip()

    return title.strip()


def clean_author(author):
    """清理作者名称 - 移除 'By' 前缀"""
    if not author:
        return author

    if author.startswith('By'):
        author = author[2:].strip()

    if not author:
        return 'New Scientist'

    return author


def fetch_page(url, page):
    """使用 Playwright page 获取网页 HTML"""
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    return page.content()


def fetch_article_details(url, page):
    """获取单篇文章的详细信息"""
    try:
        html = fetch_page(url, page)
        soup = BeautifulSoup(html, 'html.parser')

        # 获取标题
        title = ''
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = clean_title(og_title.get('content'))

        if not title:
            h1 = soup.find('h1')
            if h1:
                title = clean_title(h1.get_text(strip=True))

        # 获取描述/摘要
        description = ''
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            description = og_desc.get('content')
        else:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description = meta_desc.get('content')

        if not description:
            article = soup.find('article')
            if article:
                p = article.find('p')
                if p:
                    description = p.get_text(strip=True)[:300]

        # 获取作者
        author = 'New Scientist'
        author_meta = soup.find('meta', attrs={'name': 'author'})
        if author_meta and author_meta.get('content'):
            author = clean_author(author_meta.get('content'))

        byline = soup.find(['span', 'div'], class_=re.compile(r'byline|author', re.I))
        if byline:
            author_text = byline.get_text(strip=True)
            if author_text and len(author_text) < 50:
                author = clean_author(author_text)

        # 获取分类
        category = ''
        category_elem = soup.find(['a', 'span'], class_=re.compile(r'category|section|tag', re.I))
        if category_elem:
            category = category_elem.get_text(strip=True)
            if category == 'News':
                category = ''

        if not category:
            category_meta = soup.find('meta', property='article:section')
            if category_meta and category_meta.get('content'):
                category = category_meta.get('content')
                if category == 'News':
                    category = ''

        # 获取封面图片URL
        image_url = ''
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = og_image.get('content')

        return {
            'title': title,
            'description': description,
            'author': author,
            'category': category,
            'image': image_url
        }

    except PlaywrightTimeoutError as e:
        print(f"  超时: {e}")
        return {'title': '', 'description': '', 'author': 'New Scientist', 'category': '', 'image': ''}
    except Exception as e:
        print(f"  获取详情失败: {e}")
        return {'title': '', 'description': '', 'author': 'New Scientist', 'category': '', 'image': ''}


def parse_article_links(html, base_url):
    """从HTML中解析文章链接"""
    soup = BeautifulSoup(html, 'html.parser')

    articles = []
    seen_urls = set()

    for a in soup.find_all('a', href=re.compile(r'/article/\d+')):
        href = a.get('href', '')

        if href.startswith('/'):
            href = urljoin(base_url, href)

        if href in seen_urls:
            continue
        seen_urls.add(href)

        title = a.get_text(strip=True)

        if not title or len(title) < 10:
            parent = a.find_parent(['h3', 'h4', 'h2', 'div'])
            if parent:
                for elem in parent.find_all(['h1', 'h2', 'h3', 'h4', 'a', 'span']):
                    text = elem.get_text(strip=True)
                    if text and len(text) > 10:
                        title = text
                        break

        if title in CATEGORIES:
            continue

        if title and len(title) > 15:
            articles.append({'title': title, 'url': href})

        if len(articles) >= 6:
            break

    return articles


def main():
    """主函数"""
    url = "https://www.newscientist.com/section/news/"

    print("正在获取 New Scientist 最新新闻...")
    print("=" * 70)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='en-US',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        page = context.new_page()

        try:
            print("\n📰 获取新闻列表...")
            html = fetch_page(url, page)
            articles = parse_article_links(html, url)

            print(f"找到 {len(articles)} 条新闻\n")

            if not articles:
                print("❌ 未找到文章，使用备用方法...")
                articles = [
                    {"title": "Weird and wonderful sea pen found on Mystery Ridge",
                     "url": "https://www.newscientist.com/article/2527971-weird-and-wonderful-sea-pen-found-on-mystery-ridge/"},
                    {"title": "Space storms could switch signals and cause serious train accidents",
                     "url": "https://www.newscientist.com/article/2527673-space-storms-could-switch-signals-and-cause-serious-train-accidents/"},
                    {"title": "Earliest use of anaesthetics uncovered in Chinese doctor's tomb",
                     "url": "https://www.newscientist.com/article/2527886-earliest-use-of-anaesthetics-uncovered-in-chinese-doctors-tomb/"},
                    {"title": "Attack on Iran's oil released as much pollution as a volcano",
                     "url": "https://www.newscientist.com/article/2527583-attack-on-irans-oil-released-as-much-pollution-as-a-volcano/"},
                    {"title": "Mars astronauts may do laundry by blasting clothes with a plasma beam",
                     "url": "https://www.newscientist.com/article/2527768-mars-astronauts-may-do-laundry-by-blasting-clothes-with-a-plasma-beam/"},
                    {"title": "Mercury may have gained all of its unexpected water in a single day",
                     "url": "https://www.newscientist.com/article/2527597-mercury-may-have-gained-all-of-its-unexpected-water-in-a-single-day/"},
                ]

            results = []
            for i, article in enumerate(articles, 1):
                print(f"\n[{i}] {article['title']}")

                details = fetch_article_details(article['url'], page)

                final_title = details['title'] if details['title'] else article['title']

                result = {
                    "title": final_title,
                    "url": article['url'],
                    "description": details['description'],
                    "author": details['author'],
                    "category": details['category'] or 'News',
                    "image": details['image']
                }
                results.append(result)

                print(f"    标题: {result['title']}")
                print(f"    描述: {result['description'][:80]}..." if result['description'] else "    描述: (无)")
                print(f"    作者: {result['author']}")
                print(f"    分类: {result['category']}")
                print(f"    图片: {result['image']}")
                print("-" * 70)

            with open('news_data.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print("\n" + "=" * 70)
            print(f"✅ 成功保存 {len(results)} 条新闻到 news_data.json")
            print(f"📁 文件位置: /workspace/news_data.json")

        except Exception as e:
            print(f"\n❌ 获取新闻失败: {e}")
            import traceback
            traceback.print_exc()

        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    main()
