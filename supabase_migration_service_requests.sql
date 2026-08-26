-- Supabase service_requests 表结构更新
-- 定制化深度报告三层渐进式表单字段

-- 添加新字段
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS source_content TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS report_points TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS use_case TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS focus_areas TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS delivery_format TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS page_length TEXT;
ALTER TABLE service_requests ADD COLUMN IF NOT EXISTS must_include TEXT;

-- 字段说明注释
COMMENT ON COLUMN service_requests.title IS '报告主题/标题';
COMMENT ON COLUMN service_requests.source_content IS '依据内容来源（链接/文本描述）';
COMMENT ON COLUMN service_requests.report_points IS '我希望报告包含...（3-5个要点）';
COMMENT ON COLUMN service_requests.use_case IS '报告用于...（internal/client/competitor/trend/other）';
COMMENT ON COLUMN service_requests.focus_areas IS '重点关注...（JSON数组：ingredient/brand/channel/policy/tech/other）';
COMMENT ON COLUMN service_requests.delivery_format IS '交付形式（bullet/paragraph/table/full）';
COMMENT ON COLUMN service_requests.page_length IS '篇幅期望（1-2/3-5/5-10/unlimited）';
COMMENT ON COLUMN service_requests.must_include IS '必须包含（验收标准）';

-- 保留旧字段兼容（可选，后续可删除）
-- requirement, basis, topic 字段保留，新数据使用新字段
