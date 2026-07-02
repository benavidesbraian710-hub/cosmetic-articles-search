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

// 使用大模型进行边界检查（支持模糊匹配）
async function checkSourceWithAI(sourceName, allSources) {
  const prompt = `你是一个智能边界检查助手。请判断用户查询的公众号是否存在于已采集列表中，支持模糊匹配。

用户查询的公众号："${sourceName}"

已采集的公众号列表：
${allSources.map(s => `- ${s}`).join('\n')}

请分析：
1. 用户查询的公众号是否精确匹配列表中的某个名称？
2. 如果不精确匹配，是否是某个公众号的简称/别名？（如"妆研"是"妆研24小时"的简称，"原料合规"是"原料合规观察"的简称）
3. 如果是简称/别名，请匹配到完整的公众号名称
4. 如果完全不存在（连简称/别名都对不上），请明确说明

模糊匹配规则：
- 用户说"妆研" → 匹配"妆研24小时"
- 用户说"原料合规" → 匹配"原料合规观察"  
- 用户说"美业" → 匹配"美业颜究院"
- 用户说"个护" → 匹配"个护前沿"
- 用户说"未来迹" → 匹配"Fbeauty未来迹"
- 用户说"肤见" → 匹配"肤见未来实验室"
- 用户说"品观" → 匹配"化妆品观察 品观"
- 用户说"上海日化" → 匹配"上海日化协会"
- 用户说"中国化妆品" → 匹配"中国化妆品"

请用 JSON 格式返回：
{
  "exists": true/false,
  "matchedSource": "匹配到的完整公众号名称或null",
  "reason": "判断依据（说明是精确匹配还是简称匹配）"
}`;

  try {
    const result = await callLLM(prompt);
    const jsonMatch = result.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
  } catch (err) {
    console.error('❌ 大模型边界检查失败:', err.message);
  }
  
  // 降级：精确匹配
  const exactMatch = allSources.find(s => s === sourceName);
  return {
    exists: !!exactMatch,
    matchedSource: exactMatch || null,
    reason: '大模型调用失败，使用精确匹配降级'
  };
}

// 使用大模型生成边界情况回复（情况1：公众号不存在）
async function generateNotFoundReply(request, allSources) {
  const prompt = `你是一个友好的邮件回复助手。用户查询的公众号不在采集范围内，请生成一封礼貌的回复邮件。

用户查询："${request.sourceName}"
已采集公众号：${allSources.join('、')}

要求：
1. 语气友好、专业
2. 明确说明该公众号不在采集范围
3. 列出所有已采集的公众号
4. 提供建议：如需扩展采集范围，请联系开发者
5. 简短，不要冗余

请直接输出邮件正文（不要加标题、称呼等，直接输出正文内容）：`;

  try {
    const result = await callLLM(prompt);
    return result.trim();
  } catch (err) {
    console.error('❌ 大模型生成回复失败:', err.message);
    // 降级：使用模板回复
    return `您好！\n\n您查询的【${request.sourceName}】不在当前采集范围内。\n\n当前已采集的公众号包括：\n${allSources.map(s => `• ${s}`).join('\n')}\n\n如需扩展采集范围，请联系开发者添加该公众号。`;
  }
}

// 使用大模型生成空结果回复（情况2：时间范围内无文章）
async function generateEmptyReply(request, sourceStats) {
  const prompt = `你是一个友好的邮件回复助手。用户查询的公众号在指定时间范围内没有文章，请生成一封解释性的回复邮件。

用户查询："${request.sourceName}" ${request.days ? '最近 ' + request.days + ' 天' : '全部时间'}
公众号统计：共有 ${sourceStats.total} 篇文章，最新一篇是 ${sourceStats.latestDate}

要求：
1. 语气友好、专业
2. 解释该时间范围内没有文章
3. 提供该公众号的整体统计信息
4. 建议用户可以尝试其他时间范围
5. 简短，不要冗余

请直接输出邮件正文（不要加标题、称呼等，直接输出正文内容）：`;

  try {
    const result = await callLLM(prompt);
    return result.trim();
  } catch (err) {
    console.error('❌ 大模型生成回复失败:', err.message);
    // 降级：使用模板回复
    let statsInfo = '';
    if (sourceStats && sourceStats.total > 0) {
      statsInfo = `\n\n该公众号数据库中共有 ${sourceStats.total} 篇文章，最新一篇是 ${sourceStats.latestDate}。\n如需查询其他时间范围，请回复邮件说明。`;
    }
    return `您好！\n\n您查询的【${request.sourceName}】${request.days ? '最近 ' + request.days + ' 天' : ''}没有文章。${statsInfo}`;
  }
}

// 获取所有已采集的公众号列表
function getAllSources() {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    const sql = `SELECT DISTINCT wechat_name FROM articles ORDER BY wechat_name`;
    db.all(sql, [], (err, rows) => {
      if (err) {
        reject(err);
      } else {
        resolve(rows.map(r => r.wechat_name));
      }
    });
  });
}

// 获取邮件内容
// 邮件回复降级方案
function generateFallbackReply(allArticles, requests, email) {
  let articleList = '\n\n精选文章：\n';
  allArticles.forEach((article, i) => {
    articleList += `${i + 1}. ${article.title}\n`;
    articleList += `   来源: ${article.source} | 时间: ${article.publish_date}\n`;
    articleList += `   链接: ${article.url}\n\n`;
  });
  
  let querySummary = '';
  requests.forEach((req, i) => {
    const timeText = req.days ? `最近 ${req.days} 天` : '全部时间';
    querySummary += `- 公众号：${req.sourceName || '全部'} | 时间：${timeText} | 数量：${req.limit} 篇\n`;
  });
  
  return `您好！\n\n收到您的需求：${email.subject || '无主题'}\n\n已为您查询化妆品数据库：\n${querySummary}\n共找到 ${allArticles.length} 篇文章。${articleList}\n详细结果请查看附件中的 Excel 文件。\n\n---\n搜搜 (Sōusou) - 您的化妆品信息猎犬 🔍\n处理时间：${new Date().toLocaleString('zh-CN')}\n`;
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

// 调用 OpenClaw 大模型进行真正的语义理解
async function callLLM(prompt) {
  try {
    const { execSync } = require('child_process');
    
    // 使用 openclaw infer model run 调用 Kimi K2.6
    // 将 prompt 写入临时文件
    const tmpFile = path.join(require('os').tmpdir(), `llm_prompt_${Date.now()}.txt`);
    fs.writeFileSync(tmpFile, prompt, 'utf8');
    
    // 读取文件内容作为参数传递
    const promptContent = fs.readFileSync(tmpFile, 'utf8');
    
    // 使用 --prompt 参数（注意转义）
    const escapedPrompt = promptContent.replace(/"/g, '\\"').replace(/\n/g, '\\n');
    const cmd = `openclaw infer model run --prompt "${escapedPrompt}" --model kimi-k2.6`;
    
    console.log('   🤖 调用大模型分析用户意图...');
    
    const result = execSync(cmd, { 
      encoding: 'utf8', 
      timeout: 60000,  // 60秒超时
      maxBuffer: 1024 * 1024,
      cwd: require('os').homedir()
    });
    
    // 清理临时文件
    fs.unlinkSync(tmpFile);
    
    return result.trim();
  } catch (err) {
    console.error('❌ 大模型调用失败:', err.message);
    throw err;
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

// 使用大模型生成 Excel 内容
async function generateExcelWithAI(articles, requests) {
  const prompt = `你是一个数据整理助手。请将以下文章数据整理成结构化的 CSV 格式。

查询需求：
${requests.map((req, i) => `${i+1}. 公众号：${req.sourceName || '全部'}, 时间：${req.days ? '最近'+req.days+'天' : '全部时间'}, 数量：${req.limit}`).join('\n')}

文章数据（共${articles.length}篇）：
${articles.map((a, i) => `${i+1}. 标题：${a.title}\n   来源：${a.source}\n   日期：${a.publish_date}\n   链接：${a.url}`).join('\n')}

要求：
1. 生成标准 CSV 格式（逗号分隔）
2. 第一行为表头：序号,查询公众号,查询时间范围,标题,来源,发布日期,链接
3. 每篇文章一行
4. 如果文章数量较多，只输出前20篇（并在最后加一行说明"共XX篇，显示前20篇"）
5. 直接输出 CSV 内容，不要加任何其他文字

请输出 CSV 内容：`;

  try {
    const result = await callLLM(prompt);
    return result.trim();
  } catch (err) {
    console.error('❌ 大模型生成 Excel 失败:', err.message);
    // 降级：使用模板生成
    return generateExcelFallback(articles, requests);
  }
}

// Excel 生成降级方案
function generateExcelFallback(articles, requests) {
  const lines = ['序号,查询公众号,查询时间范围,标题,来源,发布日期,链接'];
  
  const timeRange = requests[0].days ? '最近' + requests[0].days + '天' : '全部时间';
  const source = requests[0].sourceName || '全部';
  
  if (articles.length === 0) {
    lines.push('1,' + source + ',' + timeRange + ',暂无文章,-,-,-');
  } else {
    articles.slice(0, 20).forEach((article, i) => {
      lines.push(`${i+1},${source},${timeRange},"${article.title}",${article.source},${article.publish_date},${article.url}`);
    });
    if (articles.length > 20) {
      lines.push(`,,,,,"共${articles.length}篇，显示前20篇",`);
    }
  }
  
  return lines.join('\n');
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
  let sourceNotFound = false;  // 标记公众号是否不存在
  let sourceStats = null;      // 公众号统计信息
  let matchedSourceName = null; // 大模型匹配到的公众号名称
  
  try {
    console.log('');
    console.log('   🔍 批量查询数据库...');
    
    // 获取所有公众号列表
    const allSources = await getAllSources();
    
    // 使用大模型检查每个请求的公众号（支持模糊匹配）
    for (const request of requests) {
      if (request.sourceName) {
        const checkResult = await checkSourceWithAI(request.sourceName, allSources);
        if (!checkResult.exists) {
          sourceNotFound = true;
          console.log(`   ⚠️  公众号【${request.sourceName}】不在采集范围内`);
        } else {
          // 使用大模型匹配到的名称（可能是模糊匹配）
          matchedSourceName = checkResult.matchedSource || request.sourceName;
          request.sourceName = matchedSourceName; // 更新为匹配到的名称
          
          // 获取公众号统计信息（用于情况2）
          sourceStats = await getSourceStats(matchedSourceName);
        }
      }
    }
    
    if (!sourceNotFound) {
      allArticles = await getArticlesBatch(requests);
      console.log(`   ✅ 共找到 ${allArticles.length} 篇文章`);
    }
  } catch (err) {
    console.error(`   ❌ 数据库查询失败:`, err.message);
  }
  
  // 生成 Excel
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '');
  const excelPath = path.join(__dirname, `search_result_${timestamp}.csv`);
  
  try {
    // 使用大模型生成 Excel 内容
    const csvContent = await generateExcelWithAI(allArticles, requests);
    fs.writeFileSync(excelPath, '\uFEFF' + csvContent, 'utf8');
    console.log(`   ✅ Excel 生成: ${excelPath}`);
    console.log(`   📊 包含 ${allArticles.length} 篇文章`);
  } catch (err) {
    console.error(`   ❌ Excel 生成失败:`, err.message);
  }
  
  // 构建回复内容
  let replyBody = '';
  
  if (sourceNotFound) {
    // 情况1：公众号不在数据库中 → 使用大模型生成回复
    replyBody = await generateNotFoundReply(requests[0], allSources);
  } else if (allArticles.length === 0) {
    // 情况2：时间范围内没有文章 → 使用大模型生成回复
    replyBody = await generateEmptyReply(requests[0], sourceStats);
  } else {
    // 正常情况：使用大模型生成回复邮件
    const prompt = `你是一个友好的邮件回复助手。用户查询化妆品文章，已找到结果，请生成一封专业的回复邮件。

用户查询："${email.subject || '无主题'}"

查询条件：
${requests.map((req, i) =>> `${i+1}. 公众号：${req.sourceName || '全部'}, 时间：${req.days ? '最近'+req.days+'天' : '全部时间'}, 数量：${req.limit}篇`).join('\n')}

找到文章（共${allArticles.length}篇）：
${allArticles.slice(0, 5).map((a, i) => `${i+1}. ${a.title}（${a.source}，${a.publish_date}）`).join('\n')}
${allArticles.length > 5 ? '\n...（共' + allArticles.length + '篇，详见附件）' : ''}

要求：
1. 语气友好、专业
2. 说明查询条件和结果数量
3. 列出前几篇文章的标题（最多5篇）
4. 提示用户查看附件中的完整结果
5. 简短，不要冗余

请直接输出邮件正文（不要加标题、称呼等，直接输出正文内容）：`;

    try {
      replyBody = await callLLM(prompt);
      replyBody = replyBody.trim();
    } catch (err) {
      console.error('❌ 大模型生成邮件失败:', err.message);
      // 降级：使用模板
      replyBody = generateFallbackReply(allArticles, requests, email);
    }
  }
  
  // 提取邮箱地址
  const toAddr = email.fromEmail || email.from;
  
  // 发送回复（只有正常情况才带 Excel 附件）
  if (sourceNotFound || allArticles.length === 0) {
    await sendReply(toAddr, email.subject || '化妆品文章搜索', replyBody, null);
  } else {
    await sendReply(toAddr, email.subject || '化妆品文章搜索', replyBody, excelPath);
  }
  
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
