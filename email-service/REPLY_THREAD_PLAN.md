Nick，关于「直接回复原邮件线程」功能，我直接给你方案：

**当前状态：**
- `sendReply()` 函数已添加 `inReplyTo` 和 `references` 参数支持
- 但还需要修改 2 处邮件解析逻辑，传入 `messageId`

**需要修改的地方：**
1. ✅ `sendReply()` 已支持 `originalMessageId` 参数
2. ❌ 需要修改 `startIdleMode()` 中两处 `processSingleEmail` 调用，添加 `messageId: parsed.messageId`
3. ❌ 需要修改 `processSingleEmail()` 函数签名，接收 `messageId` 并传给 `sendReply`

**Nick，你要我现在完成修改并重启邮件系统吗？**