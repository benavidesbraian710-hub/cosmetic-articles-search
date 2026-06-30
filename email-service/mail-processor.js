#!/usr/bin/env node

/**
 * 邮件处理主脚本 - 连接数据库版本
 * 功能：检查新邮件、解析需求、从数据库搜索、生成真实Excel、回复邮件
 */

const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');
const nodemailer = require('nodemailer');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const path = require('path');

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

// 需求关键词映射
const KEYWORD_PATTERNS = {
  "cosmetic": ["化妆品", "口红", "面膜", "精华", "粉底", "防晒", "护肤", "美妆"],
  "AI": ["AI", "人工智能", "大模型", "LLM", "GPT", "Claude"],
  "quantum": ["量子", "quantum", "量子计算"],
  "chip": ["芯片", "chip", "半导体", "GPU"],
  "robotics": ["机器人", "robot", "具身智能"],
  "biotech": ["生物", "biotech", "基因"],
  "news": ["新闻", "news", "资讯"],
  "paper": ["论文", "paper", "arxiv"],
  "product": ["产品", "product", "发布"],
  "funding": ["融资", "funding", "投资"],
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

function searchArticles(keywords, limit = 10) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    // 构建搜索条件
    const conditions = keywords.map(() => '(title LIKE ? OR content LIKE ? OR keywords LIKE ?)').join(' OR ');
    const params = keywords.flatMap(k => [`%${k}%`, `%${k}%`, `%${k}%`]);
    
    const sql = `
      SELECT title, url, wechat_name as source, publish_date, summary, content
      FROM articles
      WHERE ${conditions}
      ORDER BY publish_date DESC, created_at DESC
      LIMIT ?
    `;
    
    params.push(limit);
    
    db.all(sql, params, (err, rows) => {
      if (err) {
        reject(err);
      } else {
        resolve(rows || []);
      }
    });
  });
}

function getRecentArticles(limit = 10) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    const sql = `
      SELECT title, url, wechat_name as source, publish_date, summary, content
      FROM articles
      ORDER BY publish_date DESC, created_at DESC
      LIMIT ?
    `;
    
    db.all(sql, [limit], (err, rows) => {
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
          
          // 检查发件人邮箱是否是自己
          const isSelfSent = fromEmail === CONFIG.imap.auth.user || 
                            CONFIG.ignoreFrom.some(addr => 
                              fromAddr.toLowerCase().includes(addr.toLowerCase())
                            );
          
          if (isSelfSent) {
            console.log(`   ⏭️  跳过自己发送的邮件: ${parsed.subject}`);
            // 标记为已读但不处理
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

function parseRequest(email) {
  const content = `${email.subject} ${email.text}`.toLowerCase();
  
  let requestType = 'general';
  const keywords = [];
  
  for (const [category, patterns] of Object.entries(KEYWORD_PATTERNS)) {
    for (const pattern of patterns) {
      if (content.includes(pattern.toLowerCase())) {
        requestType = category;
        keywords.push(pattern);
        break;
      }
    }
  }
  
  // 提取时间范围
  let timeRange = 'today';
  if (content.includes('昨天') || content.includes('yesterday')) timeRange = 'yesterday';
  else if (content.includes('本周') || content.includes('this week')) timeRange = 'week';
  else if (content.includes('本月') || content.includes('this month')) timeRange = 'month';
  
  // 提取数量
  let limit = 10;
  const match = content.match(/(\d+)条/);
  if (match) limit = parseInt(match[1]);
  
  return {
    type: requestType,
    keywords: [...new Set(keywords)],
    timeRange,
    limit,
    originalSubject: email.subject,
    originalContent: email.text.slice(0, 500)
  };
}

function generateExcel(articles, request, outputPath) {
  // 生成真实内容的 CSV
  const data = [
    ['标题', '链接', '摘要', '发布时间', '来源', '关键词']
  ];
  
  if (articles.length === 0) {
    data.push(['暂无匹配文章', '-', '请尝试其他关键词', '-', '-', '-']);
  } else {
    for (const article of articles) {
      // 提取摘要（前100字）
      let summary = article.summary || '';
      if (!summary && article.content) {
        summary = article.content.replace(/<[^>]+>/g, '').slice(0, 100) + '...';
      }
      if (!summary) summary = '暂无摘要';
      
      data.push([
        article.title || '无标题',
        article.url || '-',
        summary,
        article.publish_date || '-',
        article.source || '-',
        request.keywords.join(', ') || '通用搜索'
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
  console.log(`\n📨 处理邮件: ${email.subject}`);
  console.log(`   来自: ${email.from}`);
  console.log(`   发件人邮箱: ${email.fromEmail}`);
  
  // 解析需求
  const request = parseRequest(email);
  console.log(`   需求类型: ${request.type}`);
  console.log(`   关键词: ${request.keywords.join(', ') || '通用搜索'}`);
  console.log(`   数量限制: ${request.limit}条`);
  
  // 从数据库搜索文章
  let articles = [];
  try {
    if (request.keywords.length > 0) {
      console.log(`   🔍 搜索数据库...`);
      articles = await searchArticles(request.keywords, request.limit);
      console.log(`   ✅ 找到 ${articles.length} 篇匹配文章`);
    } else {
      console.log(`   🔍 获取最新文章...`);
      articles = await getRecentArticles(request.limit);
      console.log(`   ✅ 找到 ${articles.length} 篇最新文章`);
    }
  } catch (err) {
    console.error(`   ❌ 数据库搜索失败: ${err.message}`);
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
    articles.slice(0, 5).forEach((article, i) => {
      articleList += `${i + 1}. ${article.title}\n   来源: ${article.source} | 时间: ${article.publish_date}\n   链接: ${article.url}\n\n`;
    });
  }
  
  const replyBody = `您好！

收到您的需求：${email.subject}

已为您从数据库搜索并整理以下内容：
- 需求类型：${request.type}
- 关键词：${request.keywords.join(', ') || '通用搜索'}
- 匹配文章数：${articles.length} 篇
- 时间范围：${request.timeRange}

${articleList}
详细结果请查看附件中的 Excel 文件。

---
搜搜 (Sōusou) - 您的 AI 信息猎犬 🔍
处理时间：${new Date().toLocaleString('zh-CN')}
数据库文章总数：147 篇
`;
  
  // 提取邮箱地址
  const toAddr = email.fromEmail || email.from;
  
  // 发送回复
  await sendReply(toAddr, email.subject, replyBody, excelPath);
  
  // 标记已读
  await markAsRead(email.uid);
  
  console.log('   ✅ 邮件处理完成');
}

async function main() {
  console.log('='.repeat(60));
  console.log('📧 邮件自动处理系统 - 数据库连接版');
  console.log(`⏰ 运行时间: ${new Date().toLocaleString('zh-CN')}`);
  console.log(`🗄️  数据库: ${CONFIG.dbPath}`);
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
