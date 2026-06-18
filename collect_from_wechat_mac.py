#!/usr/bin/env python3
"""
微信公众号文章链接采集器 - Mac 版
基于 wechat-macos-proxy 适配

功能：
1. 使用 wechat-macos-proxy 导出聊天记录
2. 从截图/OCR中提取微信公众号文章链接
3. 自动入库到 cosmetic_articles.db

前置要求：
- 安装 wechat-macos-proxy: https://clawhub.ai/skills/wechat-macos-proxy
- 安装依赖: brew install steipete/tap/peekaboo jq
- 授予屏幕录制和辅助功能权限

使用方法：
1. 在微信中打开公众号聊天（文章推送）
2. 运行此脚本采集文章链接
3. 自动保存到数据库并更新网站
"""

import sqlite3
import json
import re
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 路径配置
DB_PATH = Path.home() / ".openclaw/cosmetic_articles.db"
WECHAT_PROXY = Path.home() / ".openclaw/skills/wechat-macos-proxy/scripts/wechat_proxy.sh"
TEMP_DIR = Path("/tmp/wechat_articles")

class WeChatArticleCollectorMac:
    """Mac 版微信文章采集器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.ensure_db_exists()
        self.temp_dir = TEMP_DIR
        self.temp_dir.mkdir(exist_ok=True)
    
    def ensure_db_exists(self):
        """确保数据库存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                publish_date TEXT,
                summary TEXT,
                keywords TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def run_wechat_proxy(self, command, *args):
        """运行 wechat-macos-proxy 命令"""
        if not WECHAT_PROXY.exists():
            print(f"❌ wechat-macos-proxy 未安装")
            print(f"请访问: https://clawhub.ai/skills/wechat-macos-proxy 安装")
            return None
        
        cmd = [str(WECHAT_PROXY), command] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result
        except Exception as e:
            print(f"❌ 运行 wechat_proxy 失败: {e}")
            return None
    
    def export_chat(self, contact_name, message_count=50):
        """导出聊天记录"""
        print(f"📤 正在导出 {contact_name} 的聊天记录...")
        
        result = self.run_wechat_proxy("export", contact_name, str(message_count))
        
        if result and result.returncode == 0:
            # 解析输出，找到导出文件路径
            output = result.stdout
            
            # 查找 Markdown 文件路径
            md_match = re.search(r'EXPORT_MD:(.+)', output)
            dir_match = re.search(r'EXPORT_DIR:(.+)', output)
            
            if md_match:
                md_file = md_match.group(1).strip()
                export_dir = dir_match.group(1).strip() if dir_match else None
                
                print(f"✅ 导出成功:")
                print(f"   Markdown: {md_file}")
                print(f"   截图目录: {export_dir}")
                
                return md_file, export_dir
        
        print(f"❌ 导出失败")
        if result:
            print(f"错误输出: {result.stderr}")
        return None, None
    
    def extract_links_from_chat(self, md_file, export_dir):
        """从导出的聊天记录中提取文章链接"""
        links = []
        
        # 1. 从 Markdown 文件提取链接
        if md_file and os.path.exists(md_file):
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # 匹配 mp.weixin.qq.com 链接
                pattern = r'https?://mp\.weixin\.qq\.com/s/[a-zA-Z0-9_-]+'
                found = re.findall(pattern, content)
                links.extend(found)
        
        # 2. 从截图目录提取（如果有 OCR 工具）
        if export_dir and os.path.exists(export_dir):
            # 检查是否有截图文件
            screenshots = list(Path(export_dir).glob("*.png"))
            if screenshots:
                print(f"📸 发现 {len(screenshots)} 张截图")
                print("提示: 可以使用 OCR 工具进一步提取链接")
        
        return list(set(links))  # 去重
    
    def add_article(self, title, url, source, publish_date=None, summary=""):
        """添加文章到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if not publish_date:
            publish_date = datetime.now().strftime("%Y-%m-%d")
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        if cursor.fetchone():
            print(f"⚠️  文章已存在: {title}")
            conn.close()
            return False
        
        # 插入文章
        cursor.execute("""
            INSERT INTO articles (title, url, source, publish_date, summary, keywords, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, url, source, publish_date, summary, json.dumps([]), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"✅ 已添加: {title}")
        return True
    
    def collect_from_chat(self, contact_name, source_name=None):
        """从聊天记录中采集文章"""
        if not source_name:
            source_name = contact_name
        
        print(f"\n{'='*60}")
        print(f"  采集 {source_name} 的文章")
        print(f"{'='*60}\n")
        
        # 1. 导出聊天记录
        md_file, export_dir = self.export_chat(contact_name)
        
        if not md_file:
            return 0
        
        # 2. 提取链接
        links = self.extract_links_from_chat(md_file, export_dir)
        
        if not links:
            print(f"⚠️  未找到文章链接")
            return 0
        
        print(f"✅ 找到 {len(links)} 个文章链接\n")
        
        # 3. 添加到数据库
        added = 0
        for i, url in enumerate(links, 1):
            print(f"[{i}/{len(links)}] 处理链接: {url}")
            
            # 询问标题（或自动生成）
            title = input(f"请输入文章标题 (直接回车使用默认): ").strip()
            if not title:
                title = f"{source_name} 文章 {datetime.now().strftime('%Y%m%d')}_{i}"
            
            publish_date = input(f"请输入发布日期 (YYYY-MM-DD, 默认今天): ").strip()
            
            if self.add_article(title, url, source_name, publish_date):
                added += 1
        
        print(f"\n✅ 完成！成功添加 {added}/{len(links)} 篇文章")
        return added
    
    def quick_add(self, url, title, source):
        """快速添加单篇文章"""
        if not url.startswith("http"):
            print("❌ 无效的 URL")
            return False
        
        publish_date = datetime.now().strftime("%Y-%m-%d")
        return self.add_article(title, url, source, publish_date)
    
    def get_stats(self):
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM articles")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT source) FROM articles")
        sources = cursor.fetchone()[0]
        
        cursor.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source ORDER BY count DESC")
        source_list = cursor.fetchall()
        
        conn.close()
        
        print(f"\n📊 数据库统计:")
        print(f"   总文章数: {total}")
        print(f"   公众号数: {sources}")
        print(f"\n📰 公众号列表:")
        for source, count in source_list:
            print(f"   {source}: {count}篇")
        
        return total, sources

def main():
    """主函数"""
    collector = WeChatArticleCollectorMac()
    
    print("="*60)
    print("  微信公众号文章采集器 - Mac 版")
    print("  基于 wechat-macos-proxy")
    print("="*60)
    print()
    
    # 检查 wechat-macos-proxy 是否安装
    if not WECHAT_PROXY.exists():
        print("❌ wechat-macos-proxy 未安装")
        print()
        print("安装步骤:")
        print("1. 访问: https://clawhub.ai/skills/wechat-macos-proxy")
        print("2. 或运行: clawhub install wechat-macos-proxy")
        print()
        print("或使用手动模式:")
    
    while True:
        print("\n请选择操作:")
        print("1. 📤 从聊天记录采集文章")
        print("2. 📝 手动添加文章")
        print("3. 📊 查看统计信息")
        print("4. ❌ 退出")
        print()
        
        choice = input("请输入选项 (1-4): ").strip()
        
        if choice == '1':
            if not WECHAT_PROXY.exists():
                print("❌ wechat-macos-proxy 未安装，无法使用此功能")
                continue
            
            contact = input("请输入微信联系人/公众号名称: ").strip()
            if not contact:
                print("❌ 名称不能为空")
                continue
            
            source = input(f"请输入文章来源名称 (默认: {contact}): ").strip()
            if not source:
                source = contact
            
            collector.collect_from_chat(contact, source)
        
        elif choice == '2':
            url = input("请输入文章链接: ").strip()
            if not url:
                print("❌ 链接不能为空")
                continue
            
            title = input("请输入文章标题: ").strip()
            if not title:
                title = f"未命名文章_{datetime.now().strftime('%Y%m%d')}"
            
            source = input("请输入公众号名称: ").strip()
            if not source:
                source = "未知公众号"
            
            collector.quick_add(url, title, source)
        
        elif choice == '3':
            collector.get_stats()
        
        elif choice == '4':
            print("\n👋 再见!")
            break
        
        else:
            print("❌ 无效选项")

if __name__ == "__main__":
    main()
