# .github/scripts/generate_cache.py
import sys
import os
import json

# 将 app 目录加入路径，以便导入原有的 RSS.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../app')))

from RSS import fetch_rss_content

# 这里的信源列表必须与 app/chenbao.py 中的 MORNING_SOURCES 完全一致
MORNING_SOURCES = [
    {"name": "路透社", "url": "https://www.bing.com/news/search?q=site:reuters.com&format=rss"},
    {"name": "美联社", "url": "https://www.bing.com/news/search?q=site:apnews.com&format=rss"},
    # ... 其他 7 个信源
]

def main():
    results = {}
    print("开始同步抓取逻辑...")
    
    for src in MORNING_SOURCES:
        # 调用与本地完全一样的抓取函数
        content = fetch_rss_content(src['url'], hours_limit=24, max_items_safety=50, max_length=1500)
        
        # 封装格式：必须模拟原有 RSS.py 输出的字符串结构，确保 chenbao.py 读取时无感知
        results[src['name']] = content
        print(f"完成抓取: {src['name']}")

    # 将结果存入 JSON 文件，供 github.py 通过 Raw 链接读取
    with open("news_cache.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
