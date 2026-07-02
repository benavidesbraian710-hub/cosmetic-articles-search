const fs = require('fs');

async function test() {
  const { execSync } = require('child_process');
  
  const allSources = ['妆研24小时', '原料合规观察', '妆合规', '美业颜究院', '个护前沿', 'Fbeauty未来迹', '肤见未来实验室', '化妆品观察 品观', '上海日化协会', '中国化妆品'];
  const sourceName = '妆研'; // 模糊匹配
  
  const prompt = `你是一个智能边界检查助手。请判断用户查询的公众号是否存在于已采集列表中，支持模糊匹配。

用户查询的公众号："${sourceName}"

已采集的公众号列表：
${allSources.map(s => '- ' + s).join('\n')}

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

  const tmpFile = require('os').tmpdir() + '/test_prompt.txt';
  fs.writeFileSync(tmpFile, prompt, 'utf8');
  
  try {
    const promptContent = fs.readFileSync(tmpFile, 'utf8');
    const escapedPrompt = promptContent.replace(/"/g, '\\"').replace(/\n/g, '\\n');
    const cmd = `openclaw infer model run --prompt "${escapedPrompt}" --model kimi-k2.6`;
    
    console.log('🤖 测试大模型模糊匹配...');
    const result = execSync(cmd, { encoding: 'utf8', timeout: 60000, maxBuffer: 1024*1024 });
    
    fs.unlinkSync(tmpFile);
    
    console.log('✅ 大模型返回:');
    console.log(result);
    
    const jsonMatch = result.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      console.log('\n📊 结果:');
      console.log('  存在:', parsed.exists);
      console.log('  匹配到:', parsed.matchedSource);
      console.log('  依据:', parsed.reason);
    }
  } catch (err) {
    console.error('❌ 测试失败:', err.message);
    if (fs.existsSync(tmpFile)) fs.unlinkSync(tmpFile);
  }
}

test();
