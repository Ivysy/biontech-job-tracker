import json
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# 目标高管职级关键词
EXECUTIVE_KEYWORDS = ["director", "vice president", "vp", "chief", "head"]

def is_executive(title):
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in EXECUTIVE_KEYWORDS)

def extract_level(title):
    title_lower = title.lower()
    if "vice president" in title_lower or "vp" in title_lower:
        return "Vice President"
    elif "executive director" in title_lower:
        return "Executive Director"
    elif "senior director" in title_lower:
        return "Senior Director"
    elif "director" in title_lower:
        return "Director"
    return "Executive"

def scrape_biontech():
    print("开始抓取 BioNTech 官网...")
    jobs = []
    # 使用 Playwright 模拟真实浏览器打开页面
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # 访问 BioNTech 职位搜索页 (这里使用其常规 ATS 域名作为示例)
            page.goto("[https://jobs.biontech.com/search/?q=&locationsearch=](https://jobs.biontech.com/search/?q=&locationsearch=)", timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # 这里的选择器基于常见的职位列表结构，可能需要根据官网实际 DOM 微调
            job_rows = page.locator("tr.data-row, li.job-tile").all()
            
            for row in job_rows:
                try:
                    title = row.locator(".jobTitle, .job-title").inner_text().strip()
                    if not is_executive(title):
                        continue
                        
                    location = row.locator(".jobLocation, .location").inner_text().strip()
                    url = row.locator("a").first.get_attribute("href")
                    if url and url.startswith("/"):
                        url = "[https://jobs.biontech.com](https://jobs.biontech.com)" + url

                    jobs.append({
                        "title": title,
                        "level": extract_level(title),
                        "department": "Unknown", # 官网列表通常不直接显式展示部门，需进入详情页
                        "location": location,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "status": "Active",
                        "sources": ["BioNTech"],
                        "description": "Click 'Details' to view full job description on BioNTech careers page.",
                        "url": url or "[https://www.biontech.com/int/en/home/careers/professionals.html](https://www.biontech.com/int/en/home/careers/professionals.html)"
                    })
                except Exception as e:
                    continue
        except Exception as e:
            print(f"BioNTech 抓取遇到问题: {e}")
        finally:
            browser.close()
            
    print(f"BioNTech 官网抓取完成，找到 {len(jobs)} 个高管职位。")
    return jobs

def scrape_linkedin():
    print("开始抓取 LinkedIn 公开接口...")
    jobs = []
    # LinkedIn 免登录公开搜索 URL (搜 BioNTech, 过滤出包含 Director/VP 的岗位)
    url = "[https://www.linkedin.com/jobs/search/?keywords=BioNTech%20Director&location=Worldwide&f_TPR=r2592000](https://www.linkedin.com/jobs/search/?keywords=BioNTech%20Director&location=Worldwide&f_TPR=r2592000)"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        job_cards = soup.find_all("div", class_="base-card")
        
        for card in job_cards:
            try:
                title_elem = card.find("h3", class_="base-search-card__title")
                title = title_elem.text.strip() if title_elem else ""
                
                if not is_executive(title):
                    continue
                    
                loc_elem = card.find("span", class_="job-search-card__location")
                location = loc_elem.text.strip() if loc_elem else "Unknown"
                
                url_elem = card.find("a", class_="base-card__full-link")
                job_url = url_elem["href"].split("?")[0] if url_elem else url

                jobs.append({
                    "title": title,
                    "level": extract_level(title),
                    "department": "LinkedIn Sourced",
                    "location": location,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "Active",
                    "sources": ["LinkedIn"],
                    "description": "Sourced from LinkedIn publicly available job postings.",
                    "url": job_url
                })
            except Exception as e:
                continue
    except Exception as e:
         print(f"LinkedIn 抓取受限或报错: {e}")
         
    print(f"LinkedIn 抓取完成，找到 {len(jobs)} 个高管职位。")
    return jobs

def merge_and_save(biontech_jobs, linkedin_jobs):
    print("开始合并与去重数据...")
    all_jobs = biontech_jobs + linkedin_jobs
    unique_jobs = {}
    
    # 根据 职位名+地点 进行去重合并
    for job in all_jobs:
        # 创建一个唯一标识符 (全小写以防大小写差异)
        unique_key = f"{job['title'].lower()}|{job['location'].lower()}"
        
        if unique_key in unique_jobs:
            # 如果已经存在，合并 sources
            existing_sources = unique_jobs[unique_key]["sources"]
            new_sources = job["sources"]
            # 集合去重
            unique_jobs[unique_key]["sources"] = list(set(existing_sources + new_sources))
            # 优先保留官网的 URL 和描述
            if "BioNTech" in new_sources:
                unique_jobs[unique_key]["url"] = job["url"]
        else:
            # 分配一个新的 ID
            job["id"] = len(unique_jobs) + 1
            unique_jobs[unique_key] = job
            
    final_list = list(unique_jobs.values())
    
    # 确保存放数据的文件夹存在 (如果是在 GitHub Actions 里，public 文件夹可能不存在)
    import os
    os.makedirs('public', exist_ok=True)
    
    # 保存为 JSON
    with open('public/jobs_data.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)
        
    print(f"更新成功！最终共计 {len(final_list)} 个职位写入 jobs_data.json。")

if __name__ == "__main__":
    b_jobs = scrape_biontech()
    l_jobs = scrape_linkedin()
    merge_and_save(b_jobs, l_jobs)
