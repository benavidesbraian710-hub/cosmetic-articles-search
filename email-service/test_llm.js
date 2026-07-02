const fs = require('fs');
const path = require('path');

async function testLLM() {
  const { execSync } = require('child_process');
  const fs = require('fs');
  const path = require('path');
  
  const prompt = `你是一个智能邮件需求解析助手。请分析用户的邮件内容，理解用户的真实意图，提取关键信息。

用户邮件内容："""我要妆研24小时最近一周关于新原料的文章，大概5篇"""

请用 JSON 格式返回：
{
  "sourceName": "公众号名称或null",
  "days": 数字,
  "limit": 数字,
  "reason": "简要说明你的判断依据"
}

规则：
- sourceName: 必须是妆研24小时、非科学美妆传播、原料合规观察、妆合规、Fbeauty未来迹、个护前沿、KEV美妆、美业颜究院、肤见未来实验室、化妆品观察、品观、中国化妆品、上海日化协会之一
- days: 今天=1，昨天=2，本周/这周=7，上周=7，本月=30，上月=30，最近X天=X。如果没有明确时间，返回null
- limit: 默认10篇。如果用户说"全部"、"所有"，limit=999
- 如果用户说"最新X篇"，只限制数量，不限制时间（days=null）`;

  const tmpFile = path.join(require('os').tmpdir(), 'llm_prompt_test.txt');
  fs.writeFileSync(tmpFile, prompt, 'utf8');
  
  try {
    const promptContent = fs.readFileSync(tmpFile, 'utf8');
    const escapedPrompt = promptContent.replace(/"/g, '\\"').replace(/\n/g, '\\n');
    const cmd = `openclaw infer model run --prompt "${escapedPrompt}" --model kimi-k2.6`;
    
    console.log('🤖 调用大模型...');
    console.log('命令:', cmd.substring(0, 100) + '...');
    
    const result = execSync(cmd, { 
      encoding: 'utf8', 
      timeout: 60000,
      maxBuffer: 1024 * 1024,
      cwd: require('os').homedir()
    });
    
    fs.unlinkSync(tmpFile);
    
    console.log('✅ 大模型返回结果:');
    console.log(result);
    
    // 解析 JSON
    const jsonMatch = result.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      console.log('\n📊 解析结果:');
      console.log('  公众号:', parsed.sourceName);
      console.log('  时间:', parsed.days);
      console.log('  数量:', parsed.limit);
      console.log('  依据:', parsed.reason);
    }
  } catch (err) {
    console.error('❌ 测试失败:', err.message);
    if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
  }
}

testLLM();
