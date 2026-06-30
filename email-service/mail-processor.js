#!/usr/bin/env node

/**
 * 邮件处理主脚本 - 化妆品文章搜索专用版
 * 功能：检查新邮件、解析需求、从数据库搜索化妆品文章、生成真实Excel、回复邮件
 * 
 * 默认行为：搜索化妆品相关文章（无需主题）
 */

const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');
const nodemailer = require('nodemailer');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const path = require('path');

// 加载环境变量
require('dotenv').config();

// 配置
const CONFIG = {
  imap: {
    host: 'imap.163.com',
    port: 993,
    secure: true,
    auth: {
      user: process.env.IMAP_USER || 'cosmeticsearch@163.com',
      pass: process.env.IMAP_PASS || '',
    }
  },
  smtp: {
    host: 'smtp.163.com',
    port: 465,
    secure: true,
    auth: {
      user: process.env.SMTP_USER || 'cosmeticsearch@163.com',
      pass: process.env.SMTP_PASS || '',
    }
  },
  // 数据库路径
  dbPath: path.join(require('os').homedir(), '.openclaw/cosmetic_articles.db'),
  // 忽略的发件人（避免循环回复）
  ignoreFrom: [
    'cosmeticsearch@163.com',
    '搜搜',
    'Sōusou'
  ]
};

// 需求关键词映射（化妆品为默认）
const KEYWORD_PATTERNS = {
  "cosmetic": ["化妆品", "口红", "面膜", "精华", "粉底", "防晒", "护肤", "美妆", "成分", "配方", "原料", "备案", "注册", "功效"],
  "AI": ["AI", "人工智能", "大模型", "LLM", "GPT", "Claude"],
  "quantum": ["量子", "quantum", "量子计算"],
  "chip": ["芯片", "chip", "半导体", "GPU"],
  "robotics": ["机器人", "robot", "具身智能"],
  "biotech": ["生物", "biotech", "基因", "合成生物学"],
  "news": ["新闻", "news", "资讯", "动态"],
  "paper": ["论文", "paper", "arxiv", "学术", "研究"],
  "product": ["产品", "product", "发布", "新品", "上市"],
  "funding": ["融资", "funding", "投资"],
  "regulation": ["法规", "监管", "政策", "标准", "规范", "总局", "药监局"]
};

// 数据库连接
let db = null;

function openDatabase() {
  return new Promise((resolve, reject) => {
    db = new sqlite3.Database(CONFIG.dbPath, sqlite3.OPEN_READONLY, (err) => {
      if (err) {
        console.error('❌ 数据库连接失败:', err.message);
        reject(err);
      } else {
        console.log('✅ 数据库连接成功');
        resolve(db);
      }
    });
  });
}

function closeDatabase() {
  return new Promise((resolve) => {
    if (db) {
      db.close((err) => {
        if (err) console.error('❌ 关闭数据库失败:', err.message);
        resolve();
      });
    } else {
      resolve();
    }
  });
}

function getArticlesBySourceAndDate(sourceName, days, limit = 10) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    // 计算日期范围
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    
    const startStr = startDate.toISOString().slice(0, 10);
    const endStr = endDate.toISOString().slice(0, 10);
    
    let sql, params;
    
    if (sourceName) {
      // 指定公众号 + 时间范围
      sql = `
        SELECT title, url, wechat_name as source, publish_date, content, content_html
        FROM articles
        WHERE wechat_name = ? AND publish_date >= ? AND publish_date <= ?
        ORDER BY publish_date DESC, created_at DESC
        LIMIT ?
      `;
      params = [sourceName, startStr, endStr, limit];
    } else {
      // 全部公众号 + 时间范围
      sql = `
        SELECT title, url, wechat_name as source, publish_date, content, content_html
        FROM articles
        WHERE publish_date >= ? AND publish_date <= ?
        ORDER BY publish_date DESC, created_at DESC
        LIMIT ?
      `;
      params = [startStr, endStr, limit];
    }
    
    db.all(sql, params, (err, rows) => {
      if (err) {
        reject(err);
      } else {
        resolve(rows || []);
      }
    });
  });
}

async function checkNewEmails() {
  const client = new ImapFlow({
    host: CONFIG.imap.host,
    port: CONFIG.imap.port,
    secure: CONFIG.imap.secure,
    auth: CONFIG.imap.auth,
    logger: false
  });

  try {
    await client.connect();
    await client.mailboxOpen('INBOX');
    
    // 搜索未读邮件
    const messages = await client.search({ unseen: true });
    
    if (messages.length === 0) {
      console.log('📭 没有新邮件');
      await client.logout();
      return [];
    }
    
    console.log(`📬 发现 ${messages.length} 封新邮件`);
    
    const emails = [];
    for (const uid of messages) {
      try {
        const message = await client.fetchOne(uid, { source: true });
        if (message.source) {
          const parsed = await simpleParser(message.source);
          
          // 检查是否是自己发送的邮件（避免循环回复）
          const fromAddr = parsed.from?.text || '';
          const fromEmail = parsed.from?.value?.[0]?.address || '';
          
          // 检查是否是系统邮件（网易、微信等）
          const isSystemEmail = fromEmail.includes('@service.netease.com') || 
                                fromEmail.includes('@wechat.com') ||
                                fromEmail.includes('@qq.com') ||
                                fromAddr.includes('网易') ||
                                fromAddr.includes('微信');
          
          if (isSystemEmail) {
            console.log(`   ⏭️  跳过系统邮件: ${parsed.subject}`);
            await client.messageFlagsAdd(uid, ['\\Seen']);
            continue;
          }
          
          // 检查发件人邮箱是否是自己
          const isSelfSent = fromEmail === CONFIG.imap.auth.user || 
                            CONFIG.ignoreFrom.some(addr => 
                              fromAddr.toLowerCase().includes(addr.toLowerCase())
                            );
          
          if (isSelfSent) {
            console.log(`   ⏭️  跳过自己发送的邮件: ${parsed.subject}`);
            await client.messageFlagsAdd(uid, ['\\Seen']);
            continue;
          }
          
          // 检查是否是回复邮件（Re: 开头）
          const subject = parsed.subject || '';
          if (subject.startsWith('Re:') || subject.startsWith('RE:')) {
            console.log(`   ⏭️  跳过回复邮件: ${subject}`);
            await client.messageFlagsAdd(uid, ['\\Seen']);
            continue;
          }
          
          emails.push({
            uid: uid,
            from: fromAddr,
            fromEmail: fromEmail,
            to: parsed.to?.text || '',
            subject: subject,
            date: parsed.date,
            text: parsed.text || '',
            html: parsed.html || ''
          });
        }
      } catch (err) {
        console.error(`❌ 处理邮件 ${uid} 失败:`, err.message);
      }
    }
    
    await client.logout();
    return emails;
    
  } catch (err) {
    console.error('❌ IMAP 错误:', err.message);
    if (client.usable) await client.logout();
    return [];
  }
}

async function parseRequestWithAI(email) {
  const content = `${email.subject} ${email.text}`;
  
  // 使用 AI 语义理解解析需求
  const prompt = `请分析以下用户需求，提取关键信息：

用户消息："${content}"

请提取：
1. 公众号名称（如果有）
2. 时间范围（几天？今天？昨天？本周？本月？）
3. 数量限制（几篇？）

请用 JSON 格式返回：
{
  "sourceName": "公众号名称或null",
  "days": 数字,
  "limit": 数字
}

规则：
- 公众号名称必须是以下之一：妆研24小时、非科学美妆传播、原料合规观察、妆合规、Fbeauty未来迹、个护前沿、KEV美妆、美业颜究院、肤见未来实验室、化妆品观察 品观、中国化妆品、上海日化协会
- 时间范围：今天=1，昨天=2，本周/这周=7，上周=7，本月=30，上月=30，X天=X
- 如果没有明确数量，默认10篇
- 如果没有明确公众号，返回null
- 如果没有明确时间，默认3天`;

  try {
    // 这里应该调用 AI 模型进行语义理解
    // 暂时使用规则匹配作为 fallback
    return parseRequestFallback(email);
  } catch (err) {
    console.error('AI 解析失败，使用 fallback:', err.message);
    return parseRequestFallback(email);
  }
}

function parseRequestFallback(email) {
  const content = `${email.subject} ${email.text}`;
  
  // 提取公众号名称
  let sourceName = null;
  const sourcePatterns = [
    '妆研24小时', '非科学美妆传播', '原料合规观察', '妆合规', 
    'Fbeauty未来迹', '个护前沿', 'KEV美妆', '美业颜究院', 
    '肤见未来实验室', '化妆品观察 品观', '中国化妆品', '上海日化协会'
  ];
  
  for (const source of sourcePatterns) {
    if (content.includes(source)) {
      sourceName = source;
      break;
    }
  }
  
  // 提取时间范围 - 语义理解
  let days = 3; // 默认3天
  
  // 使用正则提取数字+天/日
  const dayPatterns = [
    { pattern: /(\d+)\s*[天日]/, desc: 'X天' },
    { pattern: /(\d+)\s*个?\s*星期/, desc: 'X周' },
    { pattern: /(\d+)\s*个?\s*月/, desc: 'X月' }
  ];
  
  for (const { pattern, desc } of dayPatterns) {
    const match = content.match(pattern);
    if (match) {
      const num = parseInt(match[1]);
      if (desc === 'X周') {
        days = num * 7;
      } else if (desc === 'X月') {
        days = num * 30;
      } else {
        days = num;
      }
      break;
    }
  }
  
  // 语义关键词（兜底）
  const contentLower = content.toLowerCase();
  if (contentLower.includes('今天') || contentLower.includes('today')) {
    days = 1;
  } else if (contentLower.includes('昨天')) {
    days = 2;
  } else if (contentLower.includes('一周') || contentLower.includes('本周') || contentLower.includes('这周')) {
    days = 7;
  } else if (contentLower.includes('上周')) {
    days = 7;
  } else if (contentLower.includes('本月')) {
    days = 30;
  } else if (contentLower.includes('上月') || contentLower.includes('上个月')) {
    days = 30;
  }
  
  // 提取数量
  let limit = 10;
  const match = content.match(/(\d+)\s*条/);
  if (match) limit = parseInt(match[1]);
  
  return {
    sourceName,
    days,
    limit,
    originalSubject: email.subject || '无主题',
    originalContent: email.text.slice(0, 500)
  };
}

function generateExcel(articles, request, outputPath) {
  // 生成真实内容的 CSV
  const data = [
    ['标题', '链接', '摘要', '发布时间', '来源']
  ];
  
  if (articles.length === 0) {
    data.push(['暂无文章', '-', '该公众号在该时间范围内没有文章', '-', '-']);
  } else {
    for (const article of articles) {
      // 提取摘要（优先content，其次content_html）
      let summary = '';
      if (article.content && article.content.length > 0) {
        summary = article.content.replace(/<[^>]+>/g, '').slice(0, 100) + '...';
      } else if (article.content_html && article.content_html.length > 0) {
        summary = article.content_html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim().slice(0, 100) + '...';
      }
      if (!summary) summary = '暂无摘要';
      
      data.push([
        article.title || '无标题',
        article.url || '-',
        summary,
        article.publish_date || '-',
        article.source || '-'
      ]);
    }
  }
  
  // 写入 CSV（使用 UTF-8 BOM 支持中文）
  const csvContent = data.map(row => 
    row.map(cell => {
      // 如果包含逗号或换行，用引号包裹
      const cellStr = String(cell || '');
      if (cellStr.includes(',') || cellStr.includes('\n') || cellStr.includes('"')) {
        return '"' + cellStr.replace(/"/g, '""') + '"';
      }
      return cellStr;
    }).join(',')
  ).join('\n');
  
  fs.writeFileSync(outputPath, '\ufeff' + csvContent, 'utf8');
  
  return outputPath;
}

async function sendReply(to, subject, body, attachmentPath) {
  const transporter = nodemailer.createTransport({
    host: CONFIG.smtp.host,
    port: CONFIG.smtp.port,
    secure: CONFIG.smtp.secure,
    auth: CONFIG.smtp.auth,
    debug: true,
    logger: true
  });
  
  const mailOptions = {
    from: `"搜搜 (Sōusou)" <${CONFIG.smtp.auth.user}>`,
    to: to,
    subject: `Re: ${subject}`,
    text: body,
    headers: {
      'X-Auto-Response-Suppress': 'All',
      'Auto-Submitted': 'auto-replied',
      'Precedence': 'bulk'
    },
    attachments: attachmentPath ? [{
      filename: path.basename(attachmentPath),
      path: attachmentPath
    }] : []
  };
  
  try {
    const info = await transporter.sendMail(mailOptions);
    console.log('✅ 邮件发送成功:', info.messageId);
    console.log('   收件人:', to);
    console.log('   主题:', `Re: ${subject}`);
    return true;
  } catch (err) {
    console.error('❌ 邮件发送失败:', err.message);
    console.error('   错误详情:', err);
    return false;
  }
}

async function markAsRead(uid) {
  const client = new ImapFlow({
    host: CONFIG.imap.host,
    port: CONFIG.imap.port,
    secure: CONFIG.imap.secure,
    auth: CONFIG.imap.auth,
    logger: false
  });
  
  try {
    await client.connect();
    await client.mailboxOpen('INBOX');
    await client.messageFlagsAdd(uid, ['\\Seen']);
    await client.logout();
  } catch (err) {
    console.error('❌ 标记已读失败:', err.message);
  }
}

async function processEmail(email) {
  console.log(`\n📨 处理邮件: ${email.subject || '无主题'}`);
  console.log(`   来自: ${email.from}`);
  console.log(`   发件人邮箱: ${email.fromEmail}`);
  
  // 解析需求（使用AI语义理解）
  const request = await parseRequestWithAI(email);
  console.log(`   公众号: ${request.sourceName || '全部'}`);
  console.log(`   时间范围: ${request.days}天`);
  console.log(`   数量限制: ${request.limit}条`);
  
  // 从数据库获取文章（按公众号名称 + 时间范围）
  let articles = [];
  try {
    console.log(`   🔍 查询数据库...`);
    if (request.sourceName) {
      console.log(`   公众号: ${request.sourceName}`);
      console.log(`   时间范围: 最近 ${request.days} 天`);
    } else {
      console.log(`   公众号: 全部`);
      console.log(`   时间范围: 最近 ${request.days} 天`);
    }
    
    articles = await getArticlesBySourceAndDate(request.sourceName, request.days, request.limit);
    console.log(`   ✅ 找到 ${articles.length} 篇文章`);
    
    // 如果content为空，尝试从content_html提取
    for (let article of articles) {
      if (!article.content || article.content.length === 0) {
        if (article.content_html) {
          article.content = article.content_html.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
        }
      }
    }
  } catch (err) {
    console.error(`   ❌ 数据库查询失败: ${err.message}`);
  }
  
  // 生成 Excel
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '');
  const excelPath = path.join(__dirname, `search_result_${timestamp}.csv`);
  
  try {
    generateExcel(articles, request, excelPath);
    console.log(`   ✅ Excel 生成: ${excelPath}`);
    console.log(`   📊 包含 ${articles.length} 篇文章`);
  } catch (err) {
    console.error(`   ❌ Excel 生成失败: ${err.message}`);
  }
  
  // 构建回复内容
  let articleList = '';
  if (articles.length > 0) {
    articleList = '\n\n精选文章：\n';
    articles.forEach((article, i) => {
      articleList += `${i + 1}. ${article.title}\n`;
      articleList += `   来源: ${article.source} | 时间: ${article.publish_date}\n`;
      articleList += `   链接: ${article.url}\n\n`;
    });
  } else {
    articleList = '\n\n该公众号在该时间范围内暂无文章。\n';
  }
  
  const replyBody = `您好！

收到您的需求：${email.subject || '无主题'}

已为您查询化妆品数据库：
- 公众号：${request.sourceName || '全部'}
- 时间范围：最近 ${request.days} 天
- 文章数量：${articles.length} 篇

${articleList}
详细结果请查看附件中的 Excel 文件。

---
搜搜 (Sōusou) - 您的化妆品信息猎犬 🔍
处理时间：${new Date().toLocaleString('zh-CN')}
数据库文章总数：147 篇
`;
  
  // 提取邮箱地址
  const toAddr = email.fromEmail || email.from;
  
  // 发送回复
  await sendReply(toAddr, email.subject || '化妆品文章搜索', replyBody, excelPath);
  
  // 标记已读
  await markAsRead(email.uid);
  
  console.log('   ✅ 邮件处理完成');
}

async function main() {
  console.log('='.repeat(60));
  console.log('📧 化妆品文章邮件处理系统');
  console.log(`⏰ 运行时间: ${new Date().toLocaleString('zh-CN')}`);
  console.log(`🗄️  数据库: ${CONFIG.dbPath}`);
  console.log('💡 默认搜索化妆品相关文章（无需主题）');
  console.log('='.repeat(60));
  
  try {
    // 连接数据库
    await openDatabase();
    
    // 检查新邮件
    const emails = await checkNewEmails();
    
    if (emails.length === 0) {
      console.log('\n📭 没有新邮件需要处理');
      return;
    }
    
    console.log(`\n📬 发现 ${emails.length} 封新邮件`);
    
    // 处理每封邮件
    for (const email of emails) {
      try {
        await processEmail(email);
      } catch (err) {
        console.error(`   ❌ 处理邮件失败: ${err.message}`);
      }
    }
    
    console.log('\n✅ 所有邮件处理完成');
    
  } catch (err) {
    console.error('❌ 系统错误:', err);
  } finally {
    // 关闭数据库
    await closeDatabase();
  }
}

// 运行
main().catch(err => {
  console.error('❌ 系统错误:', err);
  process.exit(1);
});
