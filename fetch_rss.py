# fetch_rss.py
import json
import feedparser
from datetime import datetime

# 在这里配置你需要抓取的外媒 RSS 列表
RSS_URLS = {
    "Reuters_Tech": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best",
    "AP_World": "https://apnews.com/hub/world-news/feed",
    # 可以继续添加...
}

def fetch_all():
    news_data = []
    print("开始抓取 RSS...")
    for source, url in RSS_URLS.items():
        try:
            print(f"正在抓取: {source}")
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]: # 每个源取前8条
                news_data.append({
                    "source": source,
                    "title": entry.title,
                    "link": entry.link,
                    "summary": getattr(entry, 'summary', ''),
                    "published": getattr(entry, 'published', str(datetime.now()))
                })
        except Exception as e:
            print(f"Error {source}: {e}")

    # 保存结果
    with open('news_cache.json', 'w', encoding='utf-8') as f:
        json.dump(news_data, f, ensure_ascii=False, indent=2)
    print("抓取完成，已保存 news_cache.json")

if __name__ == "__main__":
    fetch_all()