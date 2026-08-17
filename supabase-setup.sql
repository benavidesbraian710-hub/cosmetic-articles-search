-- ============================================================
-- 化妆品行业洞察平台 · 用户需求表（Supabase SQL Editor 一次性执行）
-- 管理密码：SsasmguM3SJjhVHa  （可随时改，见文件末尾注释）
-- ============================================================

-- 1. 建表
create table if not exists requests (
    id          bigint generated always as identity primary key,
    type        text not null,           -- add_wechat / add_website / other / service_facts / service_summary / service_custom
    source_name text,                    -- 来源名称 或 报告主题
    source_url  text,
    description text,
    name        text not null,           -- 联系人称呼
    email       text not null,           -- 联系邮箱
    status      text not null default 'pending',
    created_at  timestamptz not null default now()
);

-- 2. 开启行级安全：匿名用户只能写入（提交需求），不能读取
alter table requests enable row level security;

create policy "anyone_can_submit"
    on requests for insert
    to anon
    with check (true);

-- 不开任何 select 策略 => 匿名 key 读不到任何数据（用户邮箱不外泄）

-- 3. 管理员读取函数：凭密码经 RPC 读取，service_role 密钥不出现在前端
create or replace function get_requests(admin_pwd text)
returns setof requests
language plpgsql
security definer
set search_path = public
as $$
begin
    if admin_pwd is distinct from 'SsasmguM3SJjhVHa' then
        raise exception 'unauthorized';
    end if;
    return query select * from requests order by created_at desc;
end;
$$;

-- 改密码方法：把上面函数里 'SsasmguM3SJjhVHa' 换成新密码，
-- 在 SQL Editor 重跑一次第 3 段（create or replace）即可。
