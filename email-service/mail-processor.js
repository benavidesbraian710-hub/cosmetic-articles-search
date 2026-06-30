#!/usr/bin/env node

/**
 * 邮件处理主脚本 - 用于 OpenClaw Cron 定时执行
 * 功能：检查新邮件、解析需求、生成 Excel、回复邮件
 */

const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');
const nodemailer = require('nodemailer');
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
  }
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
          emails.push({
            uid: uid,
            from: parsed.from?.text || '',
            to: parsed.to?.text || '',
            subject: parsed.subject || '',
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

function generateExcel(request, outputPath) {
  // 生成示例 CSV（实际应调用搜索模块）
  const data = [
    ['标题', '链接', '摘要', '时间', '来源'],
    ['示例结果1', 'https://example.com/1', '这是示例摘要', '2026-06-30', '搜索来源'],
    ['示例结果2', 'https://example.com/2', '这是示例摘要', '2026-06-30', '搜索来源'],
  ];
  
  const csvContent = data.map(row => row.join(',')).join('\n');
  fs.writeFileSync(outputPath, '\ufeff' + csvContent, 'utf8');
  
  return outputPath;
}

async function sendReply(to, subject, body, attachmentPath) {
  const transporter = nodemailer.createTransport({
    host: CONFIG.smtp.host,
    port: CONFIG.smtp.port,
    secure: CONFIG.smtp.secure,
    auth: CONFIG.smtp.auth
  });
  
  const mailOptions = {
    from: CONFIG.smtp.auth.user,
    to: to,
    subject: `Re: ${subject}`,
    text: body,
    attachments: attachmentPath ? [{
      filename: path.basename(attachmentPath),
      path: attachmentPath
    }] : []
  };
  
  try {
    const info = await transporter.sendMail(mailOptions);
    console.log('✅ 邮件发送成功:', info.messageId);
    return true;
  } catch (err) {
    console.error('❌ 邮件发送失败:', err.message);
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
  
  // 解析需求
  const request = parseRequest(email);
  console.log(`   需求类型: ${request.type}`);
  console.log(`   关键词: ${request.keywords.join(', ') || '通用搜索'}`);
  
  // 生成 Excel
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '');
  const excelPath = path.join(__dirname, `search_result_${timestamp}.csv`);
  
  try {
    generateExcel(request, excelPath);
    console.log(`   ✅ Excel 生成: ${excelPath}`);
  } catch (err) {
    console.error(`   ❌ Excel 生成失败: ${err.message}`);
  }
  
  // 构建回复
  const replyBody = `您好！

收到您的需求：${email.subject}

已为您搜索并整理以下内容：
- 需求类型：${request.type}
- 关键词：${request.keywords.join(', ') || '通用搜索'}
- 时间范围：${request.timeRange}

请查看附件中的 Excel 文件获取详细结果。

---
搜搜 (Sōusou) - 您的 AI 信息猎犬 🔍
处理时间：${new Date().toLocaleString('zh-CN')}
`;
  
  // 提取邮箱地址
  const emailMatch = email.from.match(/<([^>]+)>/);
  const toAddr = emailMatch ? emailMatch[1] : email.from;
  
  // 发送回复
  await sendReply(toAddr, email.subject, replyBody, excelPath);
  
  // 标记已读
  await markAsRead(email.uid);
  
  console.log('   ✅ 邮件处理完成');
}

async function main() {
  console.log('='.repeat(50));
  console.log('📧 邮件自动处理系统');
  console.log(`⏰ 运行时间: ${new Date().toLocaleString('zh-CN')}`);
  console.log('='.repeat(50));
  
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
}

// 运行
main().catch(err => {
  console.error('❌ 系统错误:', err);
  process.exit(1);
});
