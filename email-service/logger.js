/**
 * 邮件系统日志模块
 * 支持：按日期分文件、分级记录、单封邮件追踪
 */

const fs = require('fs');
const path = require('path');

const LOG_DIR = path.join(__dirname, 'logs');

// 确保日志目录存在
if (!fs.existsSync(LOG_DIR)) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
}

/**
 * 获取当前日期字符串 (YYYY-MM-DD)
 */
function getDateString() {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

/**
 * 获取当前时间字符串 (HH:MM:SS)
 */
function getTimeString() {
  const now = new Date();
  return now.toTimeString().slice(0, 8);
}

/**
 * 获取完整时间戳 (YYYY-MM-DD HH:MM:SS)
 */
function getTimestamp() {
  const now = new Date();
  return `${now.toISOString().slice(0, 10)} ${now.toTimeString().slice(0, 8)}`;
}

/**
 * 写入日志文件
 */
function writeToFile(level, message, emailId = null) {
  const dateStr = getDateString();
  const logFile = path.join(LOG_DIR, `${dateStr}.log`);
  const errorFile = path.join(LOG_DIR, 'error.log');
  
  const timestamp = getTimestamp();
  const emailTag = emailId ? `[${emailId}] ` : '';
  const logLine = `[${timestamp}] [${level}] ${emailTag}${message}\n`;
  
  // 写入当天日志文件
  fs.appendFileSync(logFile, logLine, 'utf8');
  
  // 错误级别同时写入 error.log
  if (level === 'ERROR' || level === 'WARN') {
    fs.appendFileSync(errorFile, logLine, 'utf8');
  }
}

/**
 * 生成邮件唯一标识
 */
function generateEmailId(from, subject, timestamp) {
  const hash = require('crypto')
    .createHash('md5')
    .update(`${from}_${subject}_${timestamp}`)
    .digest('hex')
    .slice(0, 8);
  return hash;
}

const logger = {
  /**
   * 系统级日志（启动、连接、关闭）
   */
  info: (message) => {
    console.log(`[INFO] ${message}`);
    writeToFile('INFO', message);
  },
  
  /**
   * 调试日志
   */
  debug: (message, emailId = null) => {
    console.log(`[DEBUG] ${message}`);
    writeToFile('DEBUG', message, emailId);
  },
  
  /**
   * 警告日志
   */
  warn: (message, emailId = null) => {
    console.warn(`[WARN] ${message}`);
    writeToFile('WARN', message, emailId);
  },
  
  /**
   * 错误日志
   */
  error: (message, emailId = null) => {
    console.error(`[ERROR] ${message}`);
    writeToFile('ERROR', message, emailId);
  },
  
  /**
   * 邮件接收日志
   */
  emailReceived: (from, subject, emailId) => {
    const message = `收到邮件 | 来自: ${from} | 主题: "${subject}"`;
    console.log(`[RECV] ${message}`);
    writeToFile('RECV', message, emailId);
  },
  
  /**
   * AI解析日志
   */
  emailParsed: (sourceName, days, limit, emailId) => {
    const message = `AI解析 | 公众号: ${sourceName || '全部'} | 天数: ${days || '不限'} | 数量: ${limit}`;
    console.log(`[PARSE] ${message}`);
    writeToFile('PARSE', message, emailId);
  },
  
  /**
   * 数据库查询日志
   */
  queryResult: (count, emailId) => {
    const message = `数据库查询 | 找到 ${count} 篇文章`;
    console.log(`[QUERY] ${message}`);
    writeToFile('QUERY', message, emailId);
  },
  
  /**
   * Excel生成日志
   */
  excelGenerated: (filePath, emailId) => {
    const message = `Excel生成 | 文件: ${path.basename(filePath)}`;
    console.log(`[EXCEL] ${message}`);
    writeToFile('EXCEL', message, emailId);
  },
  
  /**
   * 邮件发送日志
   */
  emailSent: (to, success, emailId) => {
    const status = success ? '成功' : '失败';
    const message = `回复邮件 | 发送至: ${to} | 状态: ${status}`;
    console.log(`[SEND] ${message}`);
    writeToFile('SEND', message, emailId);
  },
  
  /**
   * 邮件处理完成日志
   */
  emailDone: (duration, emailId) => {
    const message = `处理完成 | 耗时: ${duration.toFixed(1)}秒`;
    console.log(`[DONE] ${message}`);
    writeToFile('DONE', message, emailId);
  },
  
  /**
   * 生成邮件ID
   */
  generateEmailId,
  
  /**
   * 获取日志目录路径
   */
  getLogDir: () => LOG_DIR
};

module.exports = logger;
