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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # 使用真实所有职位列表页面
            page.goto("[https://jobs.biontech.com/go/All-Jobs/8781301/?locale=en_US&previewCategory=true&referrerSave=false](https://jobs.biontech.com/go/All-Jobs/8781301/?locale=en_US&previewCategory=true&referrerSave=false)", timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # SAP SuccessFactors 系统典型的职位行类名
            job_rows = page.locator("tr.data-row").all()
            
            if not job_rows:
                print("警告：在 BioNTech 官网没有找到匹配的 tr.data-row 元素。")
            
            for row in job_rows:
                try:
                    # 获取标题和链接
                    title_elem = row.locator(".jobTitle a, a.jobTitle-link").first
                    title = title_elem.inner_text().strip()
                    
                    if not is_executive(title):
                        continue
                        
                    # 获取详情链接
                    url = title_elem.get_attribute("href")
                    if url and url.startswith("/"):
                        url = "[https://jobs.biontech.com](https://jobs.biontech.com)" + url
                        
                    # 获取地点
                    try:
                        location = row.locator(".jobLocation").first.inner_text().strip()
                    except:
                        location = "Unknown"
                        
                    # 获取部门/设施
                    try:
                        department = row.locator(".jobFacility").first.inner_text().strip()
                        if not department: department = "BioNTech"
                    except:
                        department = "BioNTech"
                        
                    # 获取发布日期
                    try:
                        date_str = row.locator(".jobDate").first.inner_text().strip()
                    except:
                        date_str = datetime.now().strftime("%Y-%m-%d")

                    # ==========================================
                    # 新增功能：自动进入详情页抓取职位描述 (JD)
                    # ==========================================
                    description = "暂无详细描述"
                    if url:
                        try:
                            # 用 requests 直接拉取详情页，速度更快
                            jd_res = requests.get(url, timeout=10)
                            jd_soup = BeautifulSoup(jd_res.text, "html.parser")
                            # SAP 系统通常将 JD 放在 jobdescription class 中
                            jd_elem = jd_soup.find(class_="jobdescription")
                            if jd_elem:
                                # 提取纯文本并稍微清理一下换行符
                                full_jd = jd_elem.get_text(separator=" ", strip=True)
                                # 截取前 300 个字符作为看板摘要展示
                                description = full_jd[:300] + "..." if len(full_jd) > 300 else full_jd
                        except Exception as e:
                            print(f"抓取 {title} 的 JD 失败: {e}")
                    # ==========================================

                    jobs.append({
                        "title": title,
                        "level": extract_level(title),
                        "department": department,
                        "location": location,
                        "date": date_str,
                        "status": "Active",
                        "sources": ["BioNTech"],
                        "description": description,
                        "url": url or "[https://jobs.biontech.com/go/All-Jobs/8781301/](https://jobs.biontech.com/go/All-Jobs/8781301/)"
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
    url = "[https://www.linkedin.com/jobs/search/?keywords=BioNTech%20Director&location=Worldwide&f_TPR=r2592000](https://www.linkedin.com/jobs/search/?keywords=BioNTech%20Director&location=Worldwide&f_TPR=r2592000)"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 429:
            print("警告：LinkedIn 拒绝了请求 (429 Too Many Requests)，GitHub IP 可能被暂时封禁。")
            return jobs
            
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
                    "description": "LinkedIn sourced job. Click link for details.",
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
    
    for job in all_jobs:
        unique_key = f"{job['title'].lower()}|{job['location'].lower()}"
        if unique_key in unique_jobs:
            existing_sources = unique_jobs[unique_key]["sources"]
            new_sources = job["sources"]
            unique_jobs[unique_key]["sources"] = list(set(existing_sources + new_sources))
            
            # 如果是合并数据，优先使用官网的 JD 和链接
            if "BioNTech" in new_sources and "BioNTech" not in existing_sources:
                unique_jobs[unique_key]["url"] = job["url"]
                unique_jobs[unique_key]["description"] = job["description"]
        else:
            job["id"] = len(unique_jobs) + 1
            unique_jobs[unique_key] = job
            
    final_list = list(unique_jobs.values())
    
    # 防空保护机制
    if not final_list:
        print("未抓取到任何有效数据，插入一条诊断测试数据...")
        final_list = [{
            "id": 999,
            "title": "抓取失败诊断提示 (Scraper Blocked/No Data)",
            "level": "Director",
            "department": "System Debug",
            "location": "GitHub Actions",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "status": "Closed",
            "sources": ["System"],
            "description": "当前爬虫在 GitHub 服务器中未能抓取到真实数据。这通常是因为反爬虫机制拦截，或目标官网的网页代码结构发生了变化导致脚本寻找元素失败。请查看 GitHub Actions 的后台日志 (Logs) 获取详细报错信息。",
            "url": "[https://jobs.biontech.com/go/All-Jobs/8781301/](https://jobs.biontech.com/go/All-Jobs/8781301/)"
        }]
    
    import os
    os.makedirs('public', exist_ok=True)
    
    with open('public/jobs_data.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)
        
    print(f"更新成功！最终共计 {len(final_list)} 个职位写入 jobs_data.json。")

if __name__ == "__main__":
    b_jobs = scrape_biontech()
    l_jobs = scrape_linkedin()
    merge_and_save(b_jobs, l_jobs)
