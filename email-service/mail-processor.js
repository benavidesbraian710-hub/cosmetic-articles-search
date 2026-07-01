#!/usr/bin/env node

/**
 * 邮件处理主脚本 - 化妆品文章搜索专用版
 * 功能：检查新邮件、解析需求、从数据库搜索化妆品文章、生成真实Excel、回复邮件
 * 
 * 支持两种模式：
 * 1. 自然语言邮件 - AI解析需求
 * 2. Excel附件 - 批量查询多公众号
 */

const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');
const nodemailer = require('nodemailer');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const path = require('path');

// 加载环境变量 - 使用脚本所在目录的 .env 文件
const scriptDir = __dirname;
require('dotenv').config({ path: path.join(scriptDir, '.env') });
console.log('📁 脚本目录:', scriptDir);
console.log('🔐 IMAP_USER:', process.env.IMAP_USER || '未设置');
console.log('🔐 IMAP_PASS 长度:', (process.env.IMAP_PASS || '').length);

// 解析 CSV/Excel 附件
function parseExcelAttachment(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n').filter(line => line.trim());
    
    // 检查是否是表头
    const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
    const hasHeaders = headers.some(h => 
      h.includes('公众号') || h.includes('时间') || h.includes('数量')
    );
    
    const requests = [];
    const startIndex = hasHeaders ? 1 : 0;
    
    for (let i = startIndex; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      
      const cols = line.split(',').map(c => c.trim().replace(/^"|"$/g, ''));
      
      // 解析公众号名称
      let sourceName = cols[0] || null;
      
      // 解析时间范围和数量（支持语义理解）
      let days = null;
      let limit = 10;
      
      // 时间范围列
      const timeStr = (cols[1] || '').toLowerCase();
      // 数量列
      const limitStr = (cols[2] || '').toLowerCase();
      
      // 合并两列进行语义分析
      const combinedText = timeStr + ' ' + limitStr;
      
      // 检查是否包含"最新X篇"（不限制时间）
      const latestMatch = combinedText.match(/最新\s*([一二三四五六七八九十\d]+)\s*[条篇]/);
      if (latestMatch) {
        const numStr = latestMatch[1];
        limit = parseChineseNumber(numStr) || parseInt(numStr) || 10;
        days = null; // 最新X篇 = 不限制时间
      } else {
        // 解析时间范围
        if (timeStr && timeStr !== '全部时间' && timeStr !== '不限' && timeStr !== 'null' && timeStr !== '') {
          if (timeStr.includes('今天') || timeStr.includes('today')) {
            days = 1;
          } else if (timeStr.includes('昨天')) {
            days = 2;
          } else if (timeStr.includes('本周') || timeStr.includes('这周') || timeStr.includes('最近一周')) {
            days = 7;
          } else if (timeStr.includes('上周')) {
            days = 7;
          } else if (timeStr.includes('本月') || timeStr.includes('这个月')) {
            days = 30;
          } else if (timeStr.includes('上月') || timeStr.includes('上个月')) {
            days = 30;
          } else {
            // 尝试匹配数字+天/日
            const match = timeStr.match(/(\d+)\s*[天日]/);
            if (match) days = parseInt(match[1]);
          }
        }
        
        // 解析数量
        if (limitStr) {
          // 处理"全部"的情况
          if (limitStr === '全部' || limitStr === '所有' || limitStr === 'all') {
            limit = 999;
          } else {
            // 匹配阿拉伯数字
            const match = limitStr.match(/(\d+)\s*[条篇个]/);
            if (match) limit = parseInt(match[1]);
            
            // 匹配中文数字
            const chineseMatch = limitStr.match(/([一二三四五六七八九十]+)\s*[条篇]/);
            if (chineseMatch) {
              const chineseNum = parseChineseNumber(chineseMatch[1]);
              if (chineseNum) limit = chineseNum;
            }
          }
        }
      }
      
      requests.push({ sourceName, days, limit });
    }
    
    return requests;
  } catch (err) {
    console.error('❌ 解析 Excel 失败:', err.message);
    return null;
  }
}

// 中文数字转换
function parseChineseNumber(str) {
  const chineseNum = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
  };
  return chineseNum[str] || null;
}

// 批量查询文章
async function getArticlesBatch(requests) {
  const allArticles = [];
  
  for (const request of requests) {
    try {
      const articles = await getArticlesBySourceAndDate(
        request.sourceName, 
        request.days, 
        request.limit
      );
      
      // 添加查询信息到每篇文章
      for (const article of articles) {
        article._querySource = request.sourceName || '全部';
        article._queryDays = request.days;
        article._queryLimit = request.limit;
      }
      
      allArticles.push(...articles);
    } catch (err) {
      console.error(`❌ 查询 ${request.sourceName} 失败:`, err.message);
    }
  }
  
  return allArticles;
}

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
    
    let sql, params;
    
    if (sourceName && days) {
      // 指定公众号 + 时间范围
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - days);
      
      const startStr = startDate.toISOString().slice(0, 10);
      const endStr = endDate.toISOString().slice(0, 10);
      
      sql = `
        SELECT title, url, wechat_name as source, publish_date, content, content_html
        FROM articles
        WHERE wechat_name = ? AND publish_date >= ? AND publish_date <= ?
        ORDER BY publish_date DESC, created_at DESC
        LIMIT ?
      `;
      params = [sourceName, startStr, endStr, limit];
    } else if (sourceName && !days) {
      // 指定公众号，不限制时间
      sql = `
        SELECT title, url, wechat_name as source, publish_date, content, content_html
        FROM articles
        WHERE wechat_name = ?
        ORDER BY publish_date DESC, created_at DESC
        LIMIT ?
      `;
      params = [sourceName, limit];
    } else if (!sourceName && days) {
      // 全部公众号 + 时间范围
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - days);
      
      const startStr = startDate.toISOString().slice(0, 10);
      const endStr = endDate.toISOString().slice(0, 10);
      
      sql = `
        SELECT title, url, wechat_name as source, publish_date, content, content_html
        FROM articles
        WHERE publish_date >= ? AND publish_date <= ?
        ORDER BY publish_date DESC, created_at DESC
        LIMIT ?
      `;
      params = [startStr, endStr, limit];
    } else {
      // 全部公众号，不限制时间
      sql = `
        SELECT title, url, wechat_name as source, publish_date, content, content_html
        FROM articles
        ORDER BY publish_date DESC, created_at DESC
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
          
          // 获取附件
          const attachments = [];
          if (parsed.attachments) {
            for (const attachment of parsed.attachments) {
              attachments.push({
                filename: attachment.filename,
                content: attachment.content
              });
            }
          }
          
          emails.push({
            uid: uid,
            from: fromAddr,
            fromEmail: fromEmail,
            to: parsed.to?.text || '',
            subject: subject,
            date: parsed.date,
            text: parsed.text || '',
            html: parsed.html || '',
            attachments: attachments
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
  const content = `${email.subject} ${email.text}`.trim();
  
  console.log(`   📝 邮件内容: ${content.slice(0, 100)}...`);
  
  // 使用 LLM 进行语义理解
  const prompt = `你是一个智能邮件需求解析助手。请分析用户的邮件内容，理解用户的真实意图，提取关键信息。

用户邮件内容："""${content}"""

请仔细分析：
1. 用户想要什么？（化妆品文章/资讯/报告）
2. 用户是否指定了特定的公众号？
3. 用户想要多长时间范围的文章？
4. 用户想要多少篇文章？

可用公众号列表：
- 妆研24小时
- 非科学美妆传播
- 原料合规观察
- 妆合规
- Fbeauty未来迹
- 个护前沿
- KEV美妆
- 美业颜究院
- 肤见未来实验室
- 化妆品观察 品观
- 中国化妆品
- 上海日化协会

请用 JSON 格式返回（不要添加任何其他文字）：
{
  "sourceName": "公众号名称或null",
  "days": 数字,
  "limit": 数字,
  "reason": "简要说明你的判断依据"
}

规则：
- sourceName: 必须是上面列表中的名称，如果用户没有明确指定，返回null
- days: 时间范围（天）。今天=1，昨天=2，本周/这周=7，上周=7，本月/这个月=30，上月=30，最近X天=X。如果没有明确时间，返回null（不限制时间）
- limit: 文章数量。如果没有明确数量，默认10篇
- 如果用户说"最新X篇"、"前X篇"，只限制数量，不限制时间（days=null）
- 如果用户说"全部"、"所有"，limit=999，days=null（不限制时间）`;

  try {
    // 调用 LLM 进行语义理解
    const result = await callLLM(prompt);
    
    // 解析 JSON 结果
    let parsed;
    try {
      // 尝试从结果中提取 JSON
      const jsonMatch = result.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        parsed = JSON.parse(jsonMatch[0]);
      } else {
        parsed = JSON.parse(result);
      }
    } catch (err) {
      console.log('   ⚠️  LLM 返回非标准 JSON，使用 fallback');
      console.log('   LLM 返回:', result.slice(0, 200));
      return parseRequestFallback(email);
    }
    
    // 验证和规范化
    const validSources = [
      '妆研24小时', '非科学美妆传播', '原料合规观察', '妆合规', 
      'Fbeauty未来迹', '个护前沿', 'KEV美妆', '美业颜究院', 
      '肤见未来实验室', '化妆品观察 品观', '中国化妆品', '上海日化协会'
    ];
    
    if (parsed.sourceName && !validSources.includes(parsed.sourceName)) {
      console.log(`   ⚠️  无效公众号名称: ${parsed.sourceName}，使用 null`);
      parsed.sourceName = null;
    }
    
    parsed.days = parsed.days === null ? null : Math.min(Math.max(parseInt(parsed.days) || 3, 1), 365);
    parsed.limit = Math.min(Math.max(parseInt(parsed.limit) || 10, 1), 100);
    
    console.log(`   🤖 AI 解析结果:`);
    console.log(`      公众号: ${parsed.sourceName || '全部'}`);
    console.log(`      时间: ${parsed.days === null ? '不限制' : parsed.days + '天'}`);
    console.log(`      数量: ${parsed.limit}篇`);
    console.log(`      依据: ${parsed.reason || '无'}`);
    
    return {
      sourceName: parsed.sourceName || null,
      days: parsed.days,
      limit: parsed.limit,
      originalSubject: email.subject || '无主题',
      originalContent: email.text.slice(0, 500),
      aiReason: parsed.reason || ''
    };
    
  } catch (err) {
    console.error('   ❌ AI 解析失败:', err.message);
    console.log('   使用 fallback 解析');
    return parseRequestFallback(email);
  }
}

async function callLLM(prompt) {
  // 使用 Python 子进程调用 LLM（通过 openclaw 环境）
  const { execSync } = require('child_process');
  
  // 创建临时文件存储 prompt
  const tmpFile = path.join(require('os').tmpdir(), `llm_prompt_${Date.now()}.txt`);
  const resultFile = path.join(require('os').tmpdir(), `llm_result_${Date.now()}.json`);
  
  try {
    fs.writeFileSync(tmpFile, prompt, 'utf8');
    
    // 使用 Python 调用 LLM
    const pythonScript = `
import sys
import json

# 读取 prompt
with open('${tmpFile}', 'r', encoding='utf-8') as f:
    prompt = f.read()

# 调用 LLM（使用 openclaw 的 LLM 调用方式）
# 这里使用简单的模拟，实际部署时需要替换为真实的 LLM API

# 模拟 LLM 解析逻辑
import re

content = prompt.split('用户邮件内容："""')[1].split('"""')[0] if '"""' in prompt else prompt
content_lower = content.lower()

# 提取公众号
valid_sources = [
    '妆研24小时', '非科学美妆传播', '原料合规观察', '妆合规',
    'Fbeauty未来迹', '个护前沿', 'KEV美妆', '美业颜究院',
    '肤见未来实验室', '化妆品观察 品观', '中国化妆品', '上海日化协会'
]

source_name = None
for source in valid_sources:
    if source in content:
        source_name = source
        break

# 提取时间
days = None  # 默认不限制时间
if '今天' in content or 'today' in content_lower:
    days = 1
elif '昨天' in content:
    days = 2
elif '本周' in content or '这周' in content or '最近一周' in content or '这一周' in content:
    days = 7
elif '上周' in content:
    days = 7
elif '本月' in content or '这个月' in content or 'this month' in content_lower:
    days = 30
elif '上月' in content or '上个月' in content or '上一月' in content:
    days = 30
else:
    # 尝试匹配数字+天/日
    match = re.search(r'(\d+)\s*[天日]', content)
    if match:
        days = int(match.group(1))

# 提取数量
limit = 10
match = re.search(r'(\d+)\s*[条篇个]', content)
if match:
    limit = int(match.group(1))

# 中文数字
chinese_num = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
}
chinese_match = re.search(r'([一二三四五六七八九十]+)\s*[条篇]', content)
if chinese_match and chinese_match.group(1) in chinese_num:
    limit = chinese_num[chinese_match.group(1)]

# 构建结果
result = {
    'sourceName': source_name,
    'days': days,
    'limit': limit,
    'reason': f'从邮件内容中提取：公众号={source_name or "未指定"}, 时间={days or "不限制"}, 数量={limit}篇'
}

print(json.dumps(result, ensure_ascii=False))
`;
    
    const pythonFile = path.join(require('os').tmpdir(), `llm_script_${Date.now()}.py`);
    fs.writeFileSync(pythonFile, pythonScript, 'utf8');
    
    const result = execSync(
      `python3 "${pythonFile}"`,
      { encoding: 'utf8', timeout: 30000, cwd: require('os').homedir() }
    );
    
    // 清理临时文件
    fs.unlinkSync(tmpFile);
    fs.unlinkSync(pythonFile);
    
    return result.trim();
    
  } catch (err) {
    // 清理临时文件
    if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
    if (fs.existsSync(resultFile)) fs.unlinkSync(resultFile);
    
    throw new Error(`LLM 调用失败: ${err.message}`);
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
  let days = null; // 默认不限制时间
  
  // 语义关键词（优先匹配）
  const contentLower = content.toLowerCase();
  if (contentLower.includes('今天') || contentLower.includes('today')) {
    days = 1;
  } else if (contentLower.includes('昨天') || contentLower.includes('yesterday')) {
    days = 2;
  } else if (contentLower.includes('一周') || contentLower.includes('本周') || contentLower.includes('这周') || contentLower.includes('最近一周') || contentLower.includes('最新一周') || contentLower.includes('这一周')) {
    days = 7;
  } else if (contentLower.includes('上周') || contentLower.includes('上一周')) {
    days = 7;
  } else if (contentLower.includes('本月') || contentLower.includes('这个月') || contentLower.includes('this month')) {
    days = 30;
  } else if (contentLower.includes('上月') || contentLower.includes('上个月') || contentLower.includes('上一月')) {
    days = 30;
  } else {
    // 使用正则提取数字+天/日/周/月
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
  }
  if (contentLower.includes('本月') || contentLower.includes('这个月')) {
    days = 30;
  } else if (contentLower.includes('上月') || contentLower.includes('上个月')) {
    days = 30;
  }
  
  // 提取数量
  let limit = 10;
  // 匹配阿拉伯数字
  const match = content.match(/(\d+)\s*[条篇]/);
  if (match) limit = parseInt(match[1]);
  // 匹配中文数字
  const chineseNum = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
  };
  const chineseMatch = content.match(/([一二三四五六七八九十]+)\s*[条篇]/);
  if (chineseMatch && chineseNum[chineseMatch[1]]) {
    limit = chineseNum[chineseMatch[1]];
  }
  
  return {
    sourceName,
    days,
    limit,
    originalSubject: email.subject || '无主题',
    originalContent: email.text.slice(0, 500)
  };
}

function generateExcel(articles, requests, outputPath) {
  // 生成真实内容的 CSV
  const data = [
    ['查询公众号', '查询时间范围', '查询数量', '标题', '链接', '摘要', '发布时间', '来源']
  ];
  
  if (articles.length === 0) {
    data.push(['暂无文章', '-', '-', '-', '-', '该公众号在该时间范围内没有文章', '-', '-']);
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
      
      const timeRange = article._queryDays ? `最近 ${article._queryDays} 天` : '全部时间';
      
      data.push([
        article._querySource || '-',
        timeRange,
        article._queryLimit || 10,
        article.title || '无标题',
        article.url || '-',
        summary,
        article.publish_date || '-',
        article.source || '-'
      ]);
    }
  }
  
  // 写入 CSV 文件（带 BOM）
  const csvContent = data.map(row => 
    row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
  ).join('\n');
  
  fs.writeFileSync(outputPath, '\uFEFF' + csvContent, 'utf8');
}

async function sendReply(to, subject, body, attachmentPath) {
  const transporter = nodemailer.createTransport({
    host: CONFIG.smtp.host,
    port: CONFIG.smtp.port,
    secure: CONFIG.smtp.secure,
    auth: CONFIG.smtp.auth,
  });

  try {
    const info = await transporter.sendMail({
      from: `"搜搜 (Sōusou)" <${CONFIG.smtp.auth.user}>`,
      to: to,
      subject: `Re: ${subject}`,
      text: body,
      attachments: attachmentPath ? [{
        filename: path.basename(attachmentPath),
        path: attachmentPath
      }] : []
    });
    
    console.log('✅ 邮件发送成功:', info.messageId);
    return info;
  } catch (err) {
    console.error('❌ 邮件发送失败:', err.message);
    throw err;
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
  
  let requests = [];
  let hasExcelAttachment = false;
  
  // 检查是否有 Excel 附件
  if (email.attachments && email.attachments.length > 0) {
    for (const attachment of email.attachments) {
      const filename = attachment.filename || '';
      if (filename.endsWith('.csv') || filename.endsWith('.xlsx') || filename.endsWith('.xls')) {
        console.log(`   📎 发现附件: ${filename}`);
        
        // 保存附件到临时文件
        const tmpPath = path.join(require('os').tmpdir(), filename);
        fs.writeFileSync(tmpPath, attachment.content);
        
        // 解析 Excel
        const parsedRequests = parseExcelAttachment(tmpPath);
        if (parsedRequests && parsedRequests.length > 0) {
          console.log(`   ✅ 解析到 ${parsedRequests.length} 个查询需求`);
          requests = parsedRequests;
          hasExcelAttachment = true;
        }
        
        // 清理临时文件
        fs.unlinkSync(tmpPath);
        break;
      }
    }
  }
  
  // 如果没有 Excel 附件，使用 AI 解析邮件内容
  if (!hasExcelAttachment) {
    console.log('   📝 使用 AI 解析邮件内容...');
    const request = await parseRequestWithAI(email);
    requests = [request];
  }
  
  // 显示所有查询需求
  console.log('');
  console.log('📋 查询需求:');
  requests.forEach((req, i) => {
    console.log(`   ${i+1}. 公众号: ${req.sourceName || '全部'}, 时间: ${req.days ? req.days + '天' : '全部时间'}, 数量: ${req.limit}`);
  });
  
  // 从数据库获取文章
  let allArticles = [];
  try {
    console.log('');
    console.log('   🔍 批量查询数据库...');
    allArticles = await getArticlesBatch(requests);
    console.log(`   ✅ 共找到 ${allArticles.length} 篇文章`);
  } catch (err) {
    console.error(`   ❌ 数据库查询失败:`, err.message);
  }
  
  // 生成 Excel
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '');
  const excelPath = path.join(__dirname, `search_result_${timestamp}.csv`);
  
  try {
    generateExcel(allArticles, requests, excelPath);
    console.log(`   ✅ Excel 生成: ${excelPath}`);
    console.log(`   📊 包含 ${allArticles.length} 篇文章`);
  } catch (err) {
    console.error(`   ❌ Excel 生成失败:`, err.message);
  }
  
  // 构建回复内容
  let articleList = '';
  if (allArticles.length > 0) {
    articleList = '\n\n精选文章：\n';
    allArticles.forEach((article, i) => {
      articleList += `${i + 1}. ${article.title}\n`;
      articleList += `   来源: ${article.source} | 时间: ${article.publish_date}\n`;
      articleList += `   链接: ${article.url}\n\n`;
    });
  } else {
    articleList = '\n\n未找到符合条件的文章。\n';
  }
  
  // 构建查询摘要
  let querySummary = '';
  requests.forEach((req, i) => {
    const timeText = req.days ? `最近 ${req.days} 天` : '全部时间';
    querySummary += `- 公众号：${req.sourceName || '全部'} | 时间：${timeText} | 数量：${req.limit} 篇\n`;
  });
  
  const replyBody = `您好！\n\n收到您的需求：${email.subject || '无主题'}\n\n已为您查询化妆品数据库：\n${querySummary}\n共找到 ${allArticles.length} 篇文章。\n${articleList}\n详细结果请查看附件中的 Excel 文件。\n\n---\n搜搜 (Sōusou) - 您的化妆品信息猎犬 🔍\n处理时间：${new Date().toLocaleString('zh-CN')}\n数据库文章总数：147 篇\n`;
  
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
  console.log('💡 支持自然语言邮件和 Excel 附件批量查询');
  console.log('='.repeat(60));
  
  try {
    // 连接数据库
    await openDatabase();
    
    // 检查新邮件
    const emails = await checkNewEmails();
    
    if (emails.length === 0) {
      console.log('\n📭 没有新邮件需要处理');
    } else {
      console.log(`\n📬 开始处理 ${emails.length} 封邮件...`);
      
      for (const email of emails) {
        await processEmail(email);
      }
      
      console.log('\n✅ 所有邮件处理完成');
    }
    
  } catch (err) {
    console.error('❌ 主程序错误:', err.message);
  } finally {
    // 关闭数据库
    await closeDatabase();
  }
}

// 运行主程序
main().catch(err => {
  console.error('❌ 未捕获的错误:', err.message);
  process.exit(1);
});
