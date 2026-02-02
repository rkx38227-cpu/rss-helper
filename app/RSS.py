# app/RSS.py (修复时区版)
import feedparser
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime, timedelta, timezone  # [新增] 引入 timezone

# 尝试导入 trafilatura
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

# Jina Reader
JINA_PREFIX = "https://r.jina.ai/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def clean_text(text):
    """清洗文本，去除多余空行"""
    if not text: return ""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

def fetch_content_local(url, timeout=15):
    """本地直接抓取"""
    try:
        resp = cffi_requests.get(url, headers=HEADERS, impersonate="chrome110", timeout=timeout, allow_redirects=True)
        if resp.status_code != 200: return None

        if HAS_TRAFILATURA:
            text = trafilatura.extract(resp.content, include_comments=False)
            if text: return clean_text(text)
        
        soup = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'aside']):
            tag.decompose()
        
        article = soup.find('article')
        if article: return clean_text(article.get_text(separator='\n'))
        
        ps = soup.find_all('p')
        text = '\n'.join([p.get_text() for p in ps if len(p.get_text()) > 20])
        return clean_text(text)
    except Exception as e:
        print(f"本地抓取失败 {url}: {e}")
        return None

def fetch_content_jina(url):
    """Jina 兜底"""
    try:
        target = f"{JINA_PREFIX}{url}"
        headers = HEADERS.copy()
        headers['x-respond-with'] = 'markdown'
        resp = cffi_requests.get(target, headers=headers, impersonate="chrome110", timeout=20)
        if resp.status_code == 200 and len(resp.text) > 100:
            return clean_text(resp.text.replace("Input the URL to scrape another page.", ""))
    except: pass
    return None

def fetch_url_smart(url):
    """智能路由: 本地 -> Jina"""
    content = fetch_content_local(url)
    if content and len(content) > 100: return content
    print(f"🔄 本地失败，尝试 Jina: {url[:50]}...")
    return fetch_content_jina(url)

def fetch_rss_content(rss_url, hours_limit=12, max_items_safety=50, max_length=5000):
    """
    抓取 RSS 并提取内容 (已修复时区问题)
    """
    print(f"🚀 开始任务: {rss_url}")
    try:
        # 1. 获取 RSS
        try:
            rss_resp = cffi_requests.get(rss_url, headers=HEADERS, impersonate="chrome110", timeout=15)
            feed = feedparser.parse(rss_resp.content)
        except:
            rss_text = fetch_content_jina(rss_url)
            feed = feedparser.parse(rss_text)

        if not feed.entries:
            return "RSS源为空或无法访问。"

        # 2. 时间筛选 (统一使用 UTC)
        now = datetime.now(timezone.utc) # [修正] 获取当前 UTC 时间
        target_entries = []
        
        # print(f"🕒 [时间基准] UTC Now: {now}") # 调试用

        for entry in feed.entries:
            pub_date = None
            try:
                # [修正] 直接将 struct_time 转换为 UTC aware datetime
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pub_date = None
            
            title = entry.get('title', '无标题')
            
            if pub_date:
                diff = now - pub_date
                # 筛选逻辑
                if diff < timedelta(hours=hours_limit) and diff > timedelta(days=-1): # 防止未来时间(误报)
                    target_entries.append(entry)
                    print(f"  ✅ 采纳: {title[:15]}... | 距今: {diff}")
                else:
                    # print(f"  ❌ 丢弃(超时): {title[:15]}... | 距今: {diff}")
                    pass
            else:
                # 无时间戳的保底策略：只取前5条，防止全是旧文
                if len(target_entries) < 5:
                    target_entries.append(entry)
                    print(f"  ⚠️ 采纳(无时间): {title[:15]}...")

        if not target_entries:
            print("⚠️ 警告: 没有符合时间范围的文章，将强制使用最新的 3 篇。")
            target_entries = feed.entries[:3]
        
        # 3. 数量截断
        target_entries = target_entries[:max_items_safety]
        print(f"📊 最终命中 {len(target_entries)} 篇，开始并发抓取...")

        # 4. 并发抓取正文
        results_map = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_idx = {
                executor.submit(fetch_url_smart, entry.link): i 
                for i, entry in enumerate(target_entries)
            }
            
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results_map[idx] = future.result()

        # 5. 组装结果
        context = f"【情报汇总】(来源: {feed.feed.get('title', 'RSS')})\n\n"
        success_c = 0
        for i, entry in enumerate(target_entries):
            title = entry.get('title', '无标题')
            link = entry.get('link', '')
            content = results_map.get(i)
            
            if not content:
                desc = entry.get('summary', '') or entry.get('description', '')
                try: clean_desc = BeautifulSoup(desc, "html.parser").get_text(strip=True)
                except: clean_desc = desc[:200]
                content = f"[抓取失败] 摘要: {clean_desc}"
            else:
                success_c += 1
                if len(content) > max_length:
                    content = content[:max_length] + "..."

            context += f"=== {i+1}. {title} ===\n链接: {link}\n发布时间: {entry.get('published', '未知')}\n内容:\n{content}\n\n"
            
        print(f"🏁 完成: {success_c}/{len(target_entries)}")
        return context

    except Exception as e:
        return f"系统错误: {e}"
