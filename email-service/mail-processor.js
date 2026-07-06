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
const logger = require('./logger');

// Excel解析支持
let xlsx;
try {
  xlsx = require('xlsx');
} catch (e) {
  console.log('⚠️  xlsx模块未安装，Excel附件解析将不可用');
  xlsx = null;
}

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
    // 检查数据库文件是否存在
    if (!fs.existsSync(CONFIG.dbPath)) {
      console.error('❌ 数据库文件不存在:', CONFIG.dbPath);
      reject(new Error('数据库文件不存在'));
      return;
    }

    // 检查数据库目录是否可写（WAL需要）
    const dbDir = path.dirname(CONFIG.dbPath);
    try {
      fs.accessSync(dbDir, fs.constants.W_OK);
    } catch (err) {
      console.warn('⚠️ 数据库目录不可写（WAL模式需要）:', dbDir);
    }

    // 第一步：用读写模式连接，尝试启用 WAL
    const tempDb = new sqlite3.Database(CONFIG.dbPath, sqlite3.OPEN_READWRITE, (err) => {
      if (err) {
        console.warn('⚠️ 读写模式连接失败，尝试只读模式:', err.message);
        // 如果读写模式失败，直接用只读模式
        db = new sqlite3.Database(CONFIG.dbPath, sqlite3.OPEN_READONLY, (roErr) => {
          if (roErr) {
            console.error('❌ 只读数据库连接失败:', roErr.message);
            reject(roErr);
          } else {
            console.log('✅ 数据库连接成功（只读模式，跳过WAL）');
            resolve(db);
          }
        });
        return;
      }
      
      // 尝试启用 WAL 模式
      tempDb.run('PRAGMA journal_mode=WAL;', (walErr) => {
        if (walErr) {
          console.warn('⚠️ WAL 模式启用失败:', walErr.message);
        } else {
          console.log('✅ WAL 模式已启用');
        }
        
        // 关闭读写连接
        tempDb.close(() => {
          // 第二步：用只读模式重新连接（邮件系统只需要读取）
          db = new sqlite3.Database(CONFIG.dbPath, sqlite3.OPEN_READONLY, (roErr) => {
            if (roErr) {
              console.error('❌ 只读数据库连接失败:', roErr.message);
              reject(roErr);
            } else {
              console.log('✅ 数据库连接成功（只读模式）');
              resolve(db);
            }
          });
        });
      });
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

// 查询文章（支持startDate/endDate）
function getArticlesBySourceAndDate(sourceName, days, limit, startDate, endDate) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    let sql, params;
    
    if (sourceName && startDate && endDate) {
      // 指定了开始和结束日期
      sql = `
        SELECT title, url, wechat_name as source, publish_date
        FROM articles
        WHERE wechat_name = ? AND publish_date >= ? AND publish_date <= ?
        ORDER BY publish_date DESC
        LIMIT ?
      `;
      params = [sourceName, startDate, endDate, limit || 999];
    } else if (sourceName && days) {
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
      params = [sourceName, startStr, endStr, limit || 999];
    } else if (sourceName && !days) {
      sql = `
        SELECT title, url, wechat_name as source, publish_date
        FROM articles
        WHERE wechat_name = ?
        ORDER BY publish_date DESC
        LIMIT ?
      `;
      params = [sourceName, limit || 999];
    } else {
      sql = `
        SELECT title, url, wechat_name as source, publish_date
        FROM articles
        ORDER BY publish_date DESC
        LIMIT ?
      `;
      params = [limit || 999];
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

// 获取公众号统计信息
function getSourceStats(sourceName) {
  return new Promise((resolve, reject) => {
    if (!db) {
      reject(new Error('数据库未连接'));
      return;
    }
    
    const sql = `
      SELECT COUNT(*) as total, MAX(publish_date) as latestDate
      FROM articles
      WHERE wechat_name = ?
    `;
    
    db.get(sql, [sourceName], (err, row) => {
      if (err) {
        reject(err);
      } else {
        resolve({
          total: row ? row.total : 0,
          latestDate: row && row.latestDate ? row.latestDate : '无'
        });
      }
    });
  });
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

// 发送邮件（回复原邮件线程）
async function sendReply(to, subject, body, attachmentPath = null, originalMessageId = null) {
  const transporter = nodemailer.createTransport(CONFIG.smtp);
  
  const mailOptions = {
    from: `"搜搜" <${CONFIG.smtp.auth.user}>`,
    to: to,
    subject: subject,
    text: body,
  };
  
  // 如果是回复原邮件，添加 In-Reply-To 和 References
  if (originalMessageId) {
    mailOptions.inReplyTo = originalMessageId;
    mailOptions.references = [originalMessageId];
    console.log(`   📎 回复邮件线程: ${originalMessageId}`);
  }
  
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

// 调用大模型
async function callLLM(prompt) {
  const { execSync } = require('child_process');
  
  try {
    // 将 prompt 中的特殊字符转义
    const safePrompt = prompt.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '');
    
    // 调用 OpenClaw CLI - 使用 --prompt 参数直接传入
    const result = execSync(
      `openclaw infer model run --model kimi-k2.6 --prompt "${safePrompt}"`,
      { encoding: 'utf8', timeout: 30000, maxBuffer: 1024 * 1024 }
    );
    
    // 移除输出中的英文元数据行
    let cleanResult = result.trim();
    const lines = cleanResult.split('\n');
    const filteredLines = lines.filter(line => {
      // 过滤掉英文元数据行
      if (line.startsWith('model.run') || 
          line.startsWith('provider:') || 
          line.startsWith('model:') || 
          line.startsWith('outputs:') ||
          line.trim() === '') {
        return false;
      }
      return true;
    });
    
    return filteredLines.join('\n').trim();
  } catch (err) {
    console.error('❌ 大模型调用失败:', err.message);
    throw err;
  }
}

// 解析Excel附件，使用大模型提取查询请求
// 解析Excel附件，代码直接解析（不用大模型，更可靠）
function parseExcelAttachment(attachmentBuffer) {
  if (!xlsx) {
    console.log('   ⚠️  xlsx模块未安装，无法解析Excel');
    return null;
  }
  
  try {
    const workbook = xlsx.read(attachmentBuffer, { type: 'buffer' });
    const sheetName = workbook.SheetNames[0];
    const sheet = workbook.Sheets[sheetName];
    
    // 转换为JSON数组
    const rows = xlsx.utils.sheet_to_json(sheet, { header: 1 });
    
    console.log(`   📊 Excel行数: ${rows.length}`);
    
    const requests = [];
    
    // 遍历每一行（跳过表头，从第1行开始）
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i];
      if (!row || row.length === 0) continue;
      
      // 提取公众号名称（第二列，索引1）
      const sourceName = String(row[1] || '').trim();
      if (!sourceName || sourceName === '公众号名称') continue;
      
      // 提取时间范围（第三列，索引2）
      const timeRange = String(row[2] || '').trim();
      let days = null;
      let startDate = null;
      let endDate = null;
      
      if (timeRange) {
        // 解析"最近X天"
        const daysMatch = timeRange.match(/最近(\d+)天/);
        if (daysMatch) {
          days = parseInt(daysMatch[1]);
        }
        
        // 解析"最近一个月"
        if (timeRange.includes('最近一个月') || timeRange.includes('最近1个月')) {
          days = 30;
        }
        
        // 解析"YYYY-MM-DD 到 YYYY-MM-DD"
        const dateRangeMatch = timeRange.match(/(\d{4}-\d{2}-\d{2})\s*[到~]\s*(\d{4}-\d{2}-\d{2})/);
        if (dateRangeMatch) {
          startDate = dateRangeMatch[1];
          endDate = dateRangeMatch[2];
        }
      }
      
      requests.push({
        sourceName: sourceName,
        days: days,
        startDate: startDate,
        endDate: endDate,
        limit: 999  // 不限制数量，返回全部
      });
      
      console.log(`   ✅ 解析: ${sourceName}, ${days ? '最近'+days+'天' : (startDate ? startDate+'到'+endDate : '全部时间')}`);
    }
    
    console.log(`   ✅ 共解析 ${requests.length} 个查询请求`);
    return requests;
    
  } catch (err) {
    console.error('   ❌ Excel解析失败:', err.message);
    return null;
  }
}

async function parseRequestWithAI(email) {
  const content = `${email.subject} ${email.text}`.trim();
  
  console.log(`   📝 邮件内容: ${content.slice(0, 100)}...`);
  
  const prompt = `你是一个智能邮件需求解析助手。请分析用户的邮件内容，理解用户的真实意图，提取关键信息。

用户邮件内容："""${content}"""

请仔细分析：
1. 用户想要什么？（化妆品文章/资讯/报告）
2. 用户是否指定了特定的公众号？注意：用户可能用"、"、","、"和"、"以及"等连接多个公众号名称
3. 用户想要多长时间范围的文章？
4. 用户想要多少篇文章？

可用公众号列表（只有这些公众号在数据库中，其他名称都不存在）：
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
  "requests": [
    {"sourceName": "公众号名称", "days": 数字, "limit": 数字},
    ...
  ],
  "reason": "简要说明你的判断依据"
}

规则：
- sourceName: 必须是上面列表中的名称。如果用户指定的名称不在列表中，必须原样返回用户输入的名称（不要改成null或"全部"）
- days: 时间范围（天）。今天=1，昨天=2，本周/这周=7，上周=7，本月/这个月=30，上月=30，最近X天=X。如果没有明确时间，返回null（不限制时间）
- limit: 文章数量。如果没有明确数量，默认999篇（返回全部）。如果用户说"全部"或"所有"，返回999
- 如果用户说"最新X篇"、"前X篇"，只限制数量，不限制时间（days=null）
- 如果用户指定了多个公众号，每个公众号作为一个独立的请求对象
- 如果用户说"全部公众号"或"所有公众号"，只返回一个请求：sourceName=null
- 如果用户说"A和B"、"A,B"、"A、B"，返回多个请求分别对应A和B
- 如果用户指定的公众号不在列表中，必须原样返回用户输入的名称，不要改成null或"全部"

示例：
输入："我需要最近3天 个护前沿，中国化妆品的文章"
输出：{"requests": [{"sourceName": "个护前沿", "days": 3, "limit": 999}, {"sourceName": "中国化妆品", "days": 3, "limit": 999}], "reason": "用户指定了两个公众号"}

输入："我需要最近3天 个护前沿和中国化妆品的文章"
输出：{"requests": [{"sourceName": "个护前沿", "days": 3, "limit": 999}, {"sourceName": "中国化妆品", "days": 3, "limit": 999}], "reason": "用户用'和'连接了两个公众号"}

输入："法国化妆品的全部文章"
输出：{"requests": [{"sourceName": "法国化妆品", "days": null, "limit": 999}], "reason": "用户指定了公众号'法国化妆品'，但该公众号不在列表中"}

输入："我要最近3天的文章"
输出：{"requests": [{"sourceName": null, "days": 3, "limit": 999}], "reason": "用户没有指定公众号，查询全部"}

输入："我要个护前沿的最新5篇"
输出：{"requests": [{"sourceName": "个护前沿", "days": null, "limit": 5}], "reason": "用户指定了公众号和数量，不限时间"}

示例：
输入："我需要最近3天 个护前沿，中国化妆品的文章"
输出：{"requests": [{"sourceName": "个护前沿", "days": 3, "limit": 10}, {"sourceName": "中国化妆品", "days": 3, "limit": 10}], "reason": "用户指定了两个公众号"}

输入："我要最近3天的文章"
输出：{"requests": [{"sourceName": null, "days": 3, "limit": 10}], "reason": "用户没有指定公众号，查询全部"}

输入："我要个护前沿的最新5篇"
输出：{"requests": [{"sourceName": "个护前沿", "days": null, "limit": 5}], "reason": "用户指定了公众号和数量，不限时间"}`;

  try {
    const result = await callLLM(prompt);
    
    let parsed;
    try {
      const jsonMatch = result.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        parsed = JSON.parse(jsonMatch[0]);
      }
    } catch (e) {
      console.error('   ❌ JSON解析失败，使用默认配置');
      parsed = { requests: [{ sourceName: null, days: null, limit: 10 }] };
    }
    
    // 返回数组格式，兼容单请求和多请求
    if (parsed && parsed.requests && Array.isArray(parsed.requests)) {
      return parsed.requests.map(req => ({
        sourceName: req.sourceName || null,
        days: req.days || null,
        limit: req.limit || 10
      }));
    }
    
    // 兼容旧格式（单对象）
    return [{
      sourceName: parsed.sourceName || null,
      days: parsed.days || null,
      limit: parsed.limit || 10
    }];
  } catch (err) {
    console.error('   ❌ AI解析失败:', err.message);
    return [{ sourceName: null, days: null, limit: 10 }];
  }
}

// 批量查询文章
async function getArticlesBatch(requests) {
  const allArticles = [];
  
  for (const request of requests) {
    try {
      const articles = await getArticlesBySourceAndDate(
        request.sourceName, 
        request.days, 
        request.limit,
        request.startDate,
        request.endDate
      );
      
      for (const article of articles) {
        article._querySource = request.sourceName || '全部';
        article._queryDays = request.days;
        article._queryLimit = request.limit;
      }
      
      allArticles.push(...articles);
    } catch (err) {
      console.error("❌ 查询 " + request.sourceName + " 失败:", err.message);
    }
  }
  
  return allArticles;
}

// 生成Excel内容
async function generateExcelWithAI(allArticles, requests) {
  const prompt = "你是一个数据整理助手。请将以下化妆品文章数据整理成CSV格式。\n\n查询条件：\n" + requests.map((req, i) => `${i+1}. ${req.sourceName || '全部'}, ${req.days ? '最近'+req.days+'天' : '全部时间'}, ${req.limit}篇`).join('\n') + "\n\n文章数据（共" + allArticles.length + "篇）：\n" + allArticles.map((a, i) => `${i+1}. 标题：${a.title}\n   公众号：${a.source}\n   日期：${a.publish_date}\n   链接：${a.url}`).join('\n') + "\n\n请生成CSV格式内容，包含以下列（使用中文表头）：\n序号,公众号,标题,发布日期,文章链接\n\n注意：\n1. 第一行是中文表头：序号,公众号,标题,发布日期,文章链接\n2. 使用逗号分隔\n3. 标题中包含逗号的，用双引号包裹\n4. 不要输出任何其他文字，只输出CSV内容";

  try {
    const result = await callLLM(prompt);
    return result.trim();
  } catch (err) {
    console.error('❌ 大模型生成Excel失败:', err.message);
    // 降级：手动生成CSV（中文表头）
    let csv = '序号,公众号,标题,发布日期,文章链接\n';
    allArticles.forEach((article, i) => {
      const title = article.title.includes(',') ? `"${article.title}"` : article.title;
      csv += `${i+1},${article.source},${title},${article.publish_date},${article.url}\n`;
    });
    return csv;
  }
}

// 生成回复邮件
async function generateReplyWithAI(allArticles, requests, email) {
  const prompt = `你是一个友好的邮件回复助手。用户查询化妆品文章，已找到结果，请生成一封专业的回复邮件。

用户查询："${email.subject || '无主题'}"

查询条件：
${requests.map((req, i) => `${i+1}. 公众号：${req.sourceName || '全部'}, 时间：${req.days ? '最近'+req.days+'天' : (req.startDate ? req.startDate+'到'+req.endDate : '全部时间')}`).join('\n')}

找到文章（共${allArticles.length}篇）：
${allArticles.slice(0, 5).map((a, i) => `${i+1}. ${a.title}（${a.source}，${a.publish_date}）\n   链接：${a.url}`).join('\n')}
${allArticles.length > 5 ? '\n...（共' + allArticles.length + '篇，详见附件）' : ''}

要求：
1. 语气友好、专业
2. 说明查询条件和结果数量
3. 列出前几篇文章的标题（最多5篇），每篇后面附上可点击的链接
4. 提示用户查看附件中的完整结果
5. 简短，不要冗余
6. 不要输出任何英文元数据（如 model.run、provider 等）
7. 不要在回复中显示"999篇"或数量限制信息，只显示实际找到的文章数量

请直接输出邮件正文（不要加标题、称呼等，直接输出正文内容）：`;

  try {
    const result = await callLLM(prompt);
    return result.trim();
  } catch (err) {
    console.error('❌ 大模型生成邮件失败:', err.message);
    // 降级：使用模板
    let articleList = '\n\n精选文章：\n';
    allArticles.forEach((article, i) => {
      articleList += `${i + 1}. ${article.title}\n`;
      articleList += `   ${article.source} | ${article.publish_date}\n`;
      articleList += `   ${article.url}\n\n`;
    });

    return `您好！\n\n已为您查询化妆品数据库，共找到 ${allArticles.length} 篇文章。${articleList}\n详细结果请查看附件中的 Excel 文件。\n\n---\n搜搜 - 您的化妆品信息猎犬 🔍\n处理时间：${new Date().toLocaleString('zh-CN')}\n`;
  }
}

// 生成边界情况回复（公众号不存在）
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
    return `您好！\n\n您查询的【${request.sourceName}】不在当前采集范围内。\n\n当前已采集的公众号包括：\n${allSources.map(s => `• ${s}`).join('\n')}\n\n如需扩展采集范围，请联系开发者添加该公众号。`;
  }
}

// 生成空结果回复（时间范围内无文章）
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
    let statsInfo = '';
    if (sourceStats && sourceStats.total > 0) {
      statsInfo = `\n\n该公众号数据库中共有 ${sourceStats.total} 篇文章，最新一篇是 ${sourceStats.latestDate}。\n如需查询其他时间范围，请回复邮件说明。`;
    }
    return `您好！\n\n您查询的【${request.sourceName}】${request.days ? '最近 ' + request.days + ' 天' : ''}没有文章。${statsInfo}`;
  }
}

// 处理单封邮件
async function processSingleEmail(client, email) {
  const startTime = Date.now();
  const emailId = logger.generateEmailId(email.fromEmail, email.subject, startTime);
  const messageId = email.messageId || null;
  
  console.log('\n📨 处理邮件:', email.subject || '(无主题)');
  console.log('   来自:', email.from);
  if (messageId) {
    console.log('   📎 Message-ID:', messageId);
  }
  
  // 记录邮件接收
  logger.emailReceived(email.fromEmail, email.subject || '(无主题)', emailId);
  
  // 确保数据库连接
  if (!db) {
    await openDatabase();
  }
  
  // 解析需求（优先检查Excel附件）
  let requests = null;
  
  // 检查是否有Excel附件
  if (email.attachments && email.attachments.length > 0) {
    const excelAttachment = email.attachments.find(att => 
      att.filename && (att.filename.endsWith('.xlsx') || att.filename.endsWith('.xls'))
    );
    
    if (excelAttachment && excelAttachment.content) {
      console.log(`   📎 发现Excel附件: ${excelAttachment.filename}`);
      requests = parseExcelAttachment(excelAttachment.content);
    }
  }
  
  // 如果没有Excel附件或解析失败，使用AI解析文本
  if (!requests || requests.length === 0) {
    requests = await parseRequestWithAI(email);
  }
  
  console.log(`   📋 解析到 ${requests.length} 个查询请求:`);
  requests.forEach((req, i) => {
    console.log(`      ${i+1}. ${req.sourceName || '全部'}, ${req.days ? req.days + '天' : '全部时间'}, ${req.limit}篇`);
  });
  
  // 记录AI解析结果（记录第一个请求）
  logger.emailParsed(requests[0].sourceName, requests[0].days, requests[0].limit, emailId);
  
  // 检查公众号是否存在
  const allSources = await getAllSources();
  const validRequests = [];
  const invalidRequests = [];
  
  for (const request of requests) {
    if (request.sourceName && !allSources.includes(request.sourceName)) {
      invalidRequests.push(request);
      logger.warn(`公众号不存在: ${request.sourceName}`, emailId);
    } else {
      validRequests.push(request);
    }
  }
  
  let replyBody = '';
  let excelPath = null;
  
  if (validRequests.length === 0) {
    // 情况1：所有公众号都不存在
    replyBody = await generateNotFoundReply(invalidRequests[0], allSources);
    logger.warn(`回复: 所有公众号不存在`, emailId);
  } else {
    // 查询数据库（批量查询）
    const articles = await getArticlesBatch(validRequests);
    console.log(`   📊 找到 ${articles.length} 篇文章`);
    
    // 记录查询结果
    logger.queryResult(articles.length, emailId);
    
    if (articles.length === 0) {
      // 情况2：时间范围内无文章
      const sourceStats = await getSourceStats(validRequests[0].sourceName);
      replyBody = await generateEmptyReply(validRequests[0], sourceStats);
      logger.info(`回复: 时间范围内无文章`, emailId);
    } else {
      // 情况3：有结果，生成Excel和回复
      try {
        const csvContent = await generateExcelWithAI(articles, validRequests);
        excelPath = path.join(__dirname, `search_result_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}T${new Date().toTimeString().slice(0, 8).replace(/:/g, '')}.csv`);
        fs.writeFileSync(excelPath, '\uFEFF' + csvContent, 'utf8');
        console.log(`   ✅ Excel 生成: ${excelPath}`);
        logger.excelGenerated(excelPath, emailId);
      } catch (err) {
        console.error('   ❌ Excel 生成失败:', err.message);
        logger.error(`Excel生成失败: ${err.message}`, emailId);
      }
      
      // 生成回复邮件
      replyBody = await generateReplyWithAI(articles, validRequests, email);
    }
  }
  
  // 如果有不存在的公众号，在回复中提示
  if (invalidRequests.length > 0) {
    const invalidNames = invalidRequests.map(r => r.sourceName).join('、');
    replyBody += `\n\n⚠️ 温馨提示：您查询的【${invalidNames}】不在当前采集范围内，已为您跳过。当前已采集的公众号包括：\n${allSources.map(s => `• ${s}`).join('\n')}`;
  }
  
  // 发送回复
  try {
    await sendReply(email.fromEmail, 'Re: ' + (email.subject || '化妆品文章查询'), replyBody, excelPath, messageId);
    logger.emailSent(email.fromEmail, true, emailId);
  } catch (err) {
    console.error('   ❌ 发送邮件失败:', err.message);
    logger.emailSent(email.fromEmail, false, emailId);
    logger.error(`发送邮件失败: ${err.message}`, emailId);
  }
  
  // 标记已读
  await markAsRead(client, email.uid);
  
  // 记录处理完成
  const duration = (Date.now() - startTime) / 1000;
  logger.emailDone(duration, emailId);
  
  console.log('   ✅ 邮件处理完成');
}

// IMAP IDLE 模式
async function startIdleMode() {
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
    
    // 正常模式：启动 IDLE 监听
    console.log('📡 IMAP IDLE 模式已启动');
    console.log('⏰ 实时监听中...');
    
    // 先处理现有未读邮件
    const messages = await client.search({ unseen: true });
    if (messages.length > 0) {
      console.log(`📬 发现 ${messages.length} 封未读邮件`);
      for (const uid of messages) {
        const message = await client.fetchOne(uid, { source: true });
        if (message.source) {
          const parsed = await simpleParser(message.source);
          await processSingleEmail(client, {
            uid,
            from: parsed.from?.text || '',
            fromEmail: parsed.from?.value?.[0]?.address || '',
            subject: parsed.subject || '',
            text: parsed.text || '',
            messageId: parsed.messageId || null,
            attachments: parsed.attachments || []
          });
        }
      }
    }
    
    // 进入 IDLE 模式监听新邮件
    client.on('exists', async (data) => {
      console.log('📬 检测到新邮件！');
      logger.info('检测到新邮件');
      const newMessages = await client.search({ unseen: true });
      
      if (newMessages.length === 0) {
        console.log('   ⏭️  没有新邮件');
        return;
      }
      
      console.log(`   📬 处理 ${newMessages.length} 封新邮件`);
      
      for (const uid of newMessages) {
        // 先标记为已读，防止重复处理
        try {
          await client.messageFlagsAdd(uid, ['\\Seen']);
          console.log(`   ✅ 已标记已读: ${uid}`);
        } catch (e) {
          console.log('   ⚠️  标记已读失败:', e.message);
        }
        
        const message = await client.fetchOne(uid, { source: true });
        if (message.source) {
          const parsed = await simpleParser(message.source);
          await processSingleEmail(client, {
            uid,
            from: parsed.from?.text || '',
            fromEmail: parsed.from?.value?.[0]?.address || '',
            subject: parsed.subject || '',
            text: parsed.text || '',
            messageId: parsed.messageId || null,
            attachments: parsed.attachments || []
          });
        }
      }
    });
    
    await client.idle();
    
  } catch (err) {
    console.error('❌ IMAP 错误:', err.message);
    logger.error(`IMAP错误: ${err.message}`);
    if (client.usable) await client.logout();
    console.log('🔄 10秒后重新连接...');
    logger.info('10秒后重新连接...');
    setTimeout(startIdleMode, 10000);
  }
}

// 主函数
async function main() {
  // 修复：优先检查环境变量，兼容 cron 任务传递的 OPENCLAW_CRON
  // 同时支持 --cron 命令行参数
  const isCronMode = process.env.OPENCLAW_CRON === '1' || process.argv.includes('--cron');
  
  console.log('='.repeat(60));
  console.log('📧 化妆品文章邮件处理系统');
  if (isCronMode) {
    console.log('⏰ 单次检查模式 (cron)');
    logger.info('系统启动: 单次检查模式');
  } else {
    console.log('🚀 IMAP IDLE 实时模式');
    logger.info('系统启动: IMAP IDLE 实时模式');
  }
  console.log('='.repeat(60));
  
  try {
    await openDatabase();
    logger.info('数据库连接成功');
    
    if (isCronMode) {
      // 单次检查模式：处理所有未读邮件后退出
      await checkAndProcessEmails();
      await closeDatabase();
      logger.info('单次检查完成，退出');
      console.log('✅ 单次检查完成，退出');
      process.exit(0);
    } else {
      // 实时监听模式
      await startIdleMode();
    }
  } catch (err) {
    console.error('❌ 错误:', err.message);
    logger.error(`系统错误: ${err.message}`);
    await closeDatabase();
    if (isCronMode) process.exit(1);
  }
}

// 单次检查并处理所有未读邮件（用于 cron 模式）
async function checkAndProcessEmails() {
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
    
    console.log('📡 已连接到邮箱');
    
    // 搜索未读邮件
    const messages = await client.search({ unseen: true });
    console.log(`📬 发现 ${messages.length} 封未读邮件`);
    
    if (messages.length === 0) {
      console.log('📭 没有新邮件，无需处理');
      await client.logout();
      return;
    }
    
    for (const uid of messages) {
      const message = await client.fetchOne(uid, { source: true });
      if (message.source) {
        const parsed = await simpleParser(message.source);
        await processSingleEmail(client, {
          uid,
          from: parsed.from?.text || '',
          fromEmail: parsed.from?.value?.[0]?.address || '',
          subject: parsed.subject || '',
          text: parsed.text || '',
            messageId: parsed.messageId || null,
            attachments: parsed.attachments || []
        });
      }
    }
    
    await client.logout();
    console.log('✅ 所有未读邮件处理完成');
    
  } catch (err) {
    console.error('❌ IMAP 错误:', err.message);
    if (client.usable) await client.logout();
    throw err;
  }
}

// IMAP IDLE 模式
async function startIdleMode() {
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
    
    // 正常模式：启动 IDLE 监听
    console.log('📡 IMAP IDLE 模式已启动');
    console.log('⏰ 实时监听中...');
    
    // 先处理现有未读邮件
    const messages = await client.search({ unseen: true });
    if (messages.length > 0) {
      console.log(`📬 发现 ${messages.length} 封未读邮件`);
      for (const uid of messages) {
        const message = await client.fetchOne(uid, { source: true });
        if (message.source) {
          const parsed = await simpleParser(message.source);
          await processSingleEmail(client, {
            uid,
            from: parsed.from?.text || '',
            fromEmail: parsed.from?.value?.[0]?.address || '',
            subject: parsed.subject || '',
            text: parsed.text || '',
            messageId: parsed.messageId || null,
            attachments: parsed.attachments || []
          });
        }
      }
    }
    
    // 进入 IDLE 模式监听新邮件
    client.on('exists', async (data) => {
      console.log('📬 检测到新邮件！');
      logger.info('检测到新邮件');
      const newMessages = await client.search({ unseen: true });
      
      if (newMessages.length === 0) {
        console.log('   ⏭️  没有新邮件');
        return;
      }
      
      console.log(`   📬 处理 ${newMessages.length} 封新邮件`);
      
      for (const uid of newMessages) {
        // 先标记为已读，防止重复处理
        try {
          await client.messageFlagsAdd(uid, ['\\Seen']);
          console.log(`   ✅ 已标记已读: ${uid}`);
        } catch (e) {
          console.log('   ⚠️  标记已读失败:', e.message);
        }
        
        const message = await client.fetchOne(uid, { source: true });
        if (message.source) {
          const parsed = await simpleParser(message.source);
          await processSingleEmail(client, {
            uid,
            from: parsed.from?.text || '',
            fromEmail: parsed.from?.value?.[0]?.address || '',
            subject: parsed.subject || '',
            text: parsed.text || '',
            messageId: parsed.messageId || null,
            attachments: parsed.attachments || []
          });
        }
      }
    });
    
    await client.idle();
    
  } catch (err) {
    console.error('❌ IMAP 错误:', err.message);
    logger.error(`IMAP错误: ${err.message}`);
    if (client.usable) await client.logout();
    console.log('🔄 10秒后重新连接...');
    logger.info('10秒后重新连接...');
    setTimeout(startIdleMode, 10000);
  }
}

main().catch(err => {
  console.error('❌ 未捕获的错误:', err.message);
  process.exit(1);
});