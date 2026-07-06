import re

with open('email-service/mail-processor.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换所有 client.on('exists') 中的循环，添加防重复处理
old_pattern = r"(client\.on\('exists', async \(data\) => \{[\s\S]*?const newMessages = await client\.search\(\{ unseen: true \}\);)(\s*for \(const uid of newMessages\) \{)"

def replacement(match):
    return match.group(1) + '''
      
      if (newMessages.length === 0) {
        console.log('   ⏭️  没有新邮件');
        return;
      }
      
      console.log(`   📬 处理 ${newMessages.length} 封新邮件`);
      
      for (const uid of newMessages) {
        // 先标记为已读，防止重复处理
        try {
          await client.messageFlagsAdd(uid, ['\\\\Seen']);
          console.log(`   ✅ 已标记已读: ${uid}`);
        } catch (e) {
          console.log('   ⚠️  标记已读失败:', e.message);
        }
        '''

new_content = re.sub(old_pattern, replacement, content, count=2)

with open('email-service/mail-processor.js', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ 修改完成')