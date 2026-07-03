#!/usr/bin/env node

/**
 * 邮件处理脚本 - 单次处理模式 (Cron 专用)
 * 功能：检查未读邮件、解析需求、从数据库搜索化妆品文章、回复邮件
 * 处理完成后立即退出，适合定时任务调用
 */

const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');
const nodemailer = require('nodemailer');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const path = require('path');

// 加载环境变量
const scriptDir = __dirname;
require('dotenv').config({ path: path.join(scriptDir, '.env') });

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
  dbPath: path.join(require('os').homedir(), '.openclaw/cosmetic_articles.db'),
  ignoreFrom: [
    'cosmeticsearch@163.com',
    '搜搜',
    'Sōusou'
  ]
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

// 查询文章
function getArticlesBySourceAndDate(sourceName, days, limit = 10) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    let sql, params;
    
    if (sourceName && days) {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - days);
      
      const startStr = startDate.toISOString().slice(0, 10);
      const endStr = endDate.toISOString().slice(0, 10);
      
      sql = `
        SELECT title, url, wechat_name as source, publish_date
        FROM articles
        WHERE wechat_name = ? AND publish_date >= ? AND publish_date <= ?
        ORDER BY publish_date DESC
        LIMIT ?
      `;
      params = [sourceName, startStr, endStr, limit];
    } else if (sourceName && !days) {
      sql = `
        SELECT title, url, wechat_name as source, publish_date
        FROM articles
        WHERE wechat_name = ?
        ORDER BY publish_date DESC
        LIMIT ?
      `;
      params = [sourceName, limit];
    } else {
      sql = `
        SELECT title, url, wechat_name as source, publish_date
        FROM articles
        ORDER BY publish_date DESC
        LIMIT ?
      `;
      params = [limit];
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

// 发送邮件
async function sendReply(to, subject, body, attachmentPath = null) {
  const transporter = nodemailer.createTransport(CONFIG.smtp);
  
  const mailOptions = {
    from: `"搜搜" <${CONFIG.smtp.auth.user}>`,
    to: to,
    subject: subject,
    text: body,
  };
  
  if (attachmentPath && fs.existsSync(attachmentPath)) {
    mailOptions.attachments = [{
      filename: path.basename(attachmentPath),
      path: attachmentPath
    }];
  }
  
  try {
    await transporter.sendMail(mailOptions);
    console.log('   ✅ 回复邮件已发送');
  } catch (err) {
    console.error('   ❌ 发送邮件失败:', err.message);
  }
}

// 标记已读
async function markAsRead(client, uid) {
  try {
    await client.messageFlagsAdd(uid, ['\\Seen']);
  } catch (err) {
    console.error('   ❌ 标记已读失败:', err.message);
  }
}

// 处理单封邮件
async function processSingleEmail(client, email) {
  console.log('\n📨 处理邮件:', email.subject || '(无主题)');
  console.log('   来自:', email.from);
  
  // 确保数据库连接
  if (!db) {
    await openDatabase();
  }
  
  // 解析需求（简化版）
  const text = email.text || '';
  const subject = email.subject || '';
  
  // 提取公众号名称
  const sources = ['妆研24小时', '非科学美妆传播', '原料合规观察', '妆合规', 
                   'Fbeauty未来迹', '个护前沿', 'KEV美妆', '美业颜究院', 
                   '肤见未来实验室', '化妆品观察 品观', '中国化妆品', '上海日化协会'];
  
  let sourceName = null;
  for (const source of sources) {
    if (text.includes(source) || subject.includes(source)) {
      sourceName = source;
      break;
    }
  }
  
  // 提取时间范围
  let days = null;
  if (text.includes('最近一周') || text.includes('本周') || text.includes('这周')) {
    days = 7;
  } else if (text.includes('最近一个月') || text.includes('本月')) {
    days = 30;
  } else if (text.includes('最近三天') || text.includes('最近3天')) {
    days = 3;
  } else if (text.includes('今天')) {
    days = 1;
  }
  
  console.log(`   📋 查询: ${sourceName || '全部'}, ${days ? days + '天' : '全部时间'}, 10篇`);
  
  // 查询数据库
  try {
    const articles = await getArticlesBySourceAndDate(sourceName, days, 10);
    console.log(`   📊 找到 ${articles.length} 篇文章`);
    
    // 生成回复
    let replyBody = `您好！\n\n`;
    
    if (articles.length === 0) {
      replyBody += `您查询的${sourceName || '文章'}${days ? '最近' + days + '天' : ''}没有文章。\n\n`;
    } else {
      replyBody += `为您找到 ${articles.length} 篇文章：\n\n`;
      articles.forEach((article, i) => {
        replyBody += `${i + 1}. ${article.title}\n   ${article.source} | ${article.publish_date}\n   ${article.url}\n\n`;
      });
    }
    
    replyBody += `---\n搜搜 - 您的化妆品信息猎犬 🔍\n处理时间：${new Date().toLocaleString('zh-CN')}`;
    
    // 发送回复
    await sendReply(email.fromEmail, 'Re: ' + (email.subject || '化妆品文章查询'), replyBody);
    
  } catch (err) {
    console.error('   ❌ 查询失败:', err.message);
  }
  
  // 标记已读
  await markAsRead(client, email.uid);
}

// 单次处理模式 - 处理所有未读邮件后退出
async function processOnce() {
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
      console.log('📭 没有未读邮件，跳过处理');
    } else {
      console.log(`📬 发现 ${messages.length} 封未读邮件，开始处理...`);
      
      for (const uid of messages) {
        try {
          const message = await client.fetchOne(uid, { source: true });
          if (message.source) {
            const parsed = await simpleParser(message.source);
            
            // 检查是否是需要忽略的邮件
            const fromEmail = parsed.from?.value?.[0]?.address || '';
            const fromName = parsed.from?.text || '';
            
            let shouldIgnore = false;
            for (const ignore of CONFIG.ignoreFrom) {
              if (fromEmail.includes(ignore) || fromName.includes(ignore)) {
                shouldIgnore = true;
                console.log(`   ⏭️  跳过系统邮件: ${fromEmail}`);
                break;
              }
            }
            
            if (!shouldIgnore) {
              await processSingleEmail(client, {
                uid,
                from: parsed.from?.text || '',
                fromEmail: fromEmail,
                subject: parsed.subject || '',
                text: parsed.text || ''
              });
            } else {
              // 标记系统邮件为已读
              await markAsRead(client, uid);
            }
          }
        } catch (err) {
          console.error(`   ❌ 处理邮件 ${uid} 失败:`, err.message);
        }
      }
      
      console.log(`\n✅ 处理完成，共处理 ${messages.length} 封邮件`);
    }
    
    await client.logout();
    
  } catch (err) {
    console.error('❌ IMAP 错误:', err.message);
    if (client.usable) await client.logout();
    process.exit(1);
  }
}

// 主函数
async function main() {
  const now = new Date();
  console.log('='.repeat(60));
  console.log('📧 化妆品文章邮件处理系统');
  console.log('⏰ 单次处理模式 | 运行时间:', now.toLocaleString('zh-CN'));
  console.log('🗄️  数据库:', CONFIG.dbPath);
  console.log('='.repeat(60));
  
  try {
    await openDatabase();
    await processOnce();
    await closeDatabase();
    console.log('\n👋 任务完成，退出');
    process.exit(0);
  } catch (err) {
    console.error('❌ 错误:', err.message);
    await closeDatabase();
    process.exit(1);
  }
}

main().catch(err => {
  console.error('❌ 未捕获的错误:', err.message);
  process.exit(1);
});
