"""调研 Agent 使用的提示词模板"""


def plan_prompt(user_goal: str, num_websites: int) -> str:
    """生成研究计划的 LLM 提示词"""
    return f"""你是一个专业的研究助手。请将以下研究目标分解为多个网站的调研任务。

研究目标: {user_goal}

⚠️ **重要网络环境说明**：
- 当前网络可能无法访问所有国外网站
- 必须同时提供国内和国外的备选网站
- 国内可访问且无强登录墙：CSDN、掘金、博客园、开源中国（oschina）、segmentfault、百度搜索结果页
- 国外可访问且无强登录墙：GitHub、Stack Overflow、MDN、官方文档、arXiv、维基百科

🔐 **需要登录但内容优质的站点（仅在用户问题明显需要 UGC/社区讨论时选用）**：
- 知乎 zhihu.com、微博 weibo.com、小红书 xiaohongshu.com
- Twitter/X、LinkedIn、Quora
说明：本系统支持交互式登录复用——首次访问会暂停等待用户在浏览器登录，登录态会持久化到
~/.chrome-automation/sessions/，后续调研同站可直接复用。**只有当问题明显需要这些社区的
真实用户讨论时（例如"知乎用户怎么看 X"、"小红书有哪些 X 的真实评价"）才把它们作为主站**；
通用技术/学术问题优先选无登录墙的站。

要求：
1. 选择 {num_websites} 个相关网站进行调研
2. **必须有至少 40% 是国内网站**（可访问性高）
3. 每个网站应该有明确的研究重点
4. 任务应该是可执行的（导航、搜索、提取信息）
5. **优先无登录墙站点**：除非问题明显需要社区/UGC 讨论，否则不要选知乎/微博/小红书等
6. 为每个主要网站准备 1 个备选网站（如果主站打不开就切换），备选必须是无登录墙的

请返回 JSON 格式的研究计划：
{{
  "goal": "研究目标",
  "websites": [
    {{
      "website": "网站名称",
      "url": "网站URL",
      "region": "domestic或international",
      "priority": "high或medium或low",
      "focus": "研究重点",
      "action": "具体操作（搜索什么、提取什么）",
      "fallback": {{
        "website": "备选网站名称",
        "url": "备选网站URL",
        "reason": "为什么需要备选（如：可能无法访问）"
      }}
    }}
  ]
}}

⚠️ 关键要求：
1. 必须包含国内网站（知乎、CSDN、掘金、百度等）
2. 每个国外网站都要有备选方案
3. 优先选择内容质量高、可访问性好的网站

只返回 JSON，不要其他内容。"""


def execute_prompt(website: str, url: str, description: str) -> str:
    """生成单任务执行计划的 LLM 提示词"""
    return f"""请在浏览器中**深度调研**以下任务：

网站: {website}
URL: {url}
任务: {description}

⚠️ 重要：不要只做表面搜索！需要深入挖掘内容！

可用的工具：
- navigate(url): 导航到URL
- browser_search(keyword): 在搜索框搜索关键词
- get_page_info(): 获取当前页面标题和URL
- get_elements(limit): 获取页面上的可交互元素（返回selector和文本）
- eval_js(code): 执行JavaScript提取数据
  ⚠️ 重要：编写可靠的 eval_js 代码
  1. 必须用 JSON.stringify 包装返回值：JSON.stringify({{result: data}})
  2. 添加容错处理：element?.textContent || '未找到'
  3. 使用通用选择器：querySelectorAll('a') 比 querySelector('.specific-class') 更可靠
  4. 限制数组大小避免超长：.slice(0,10)
- click(text, tag): 点击包含指定文本的元素（可选tag限定标签）
  ⚠️ click 工具使用模糊匹配，建议使用文本的前5-10个独特字符即可

📋 **深度调研策略**（必须包含以下步骤）：

⚠️ **关键：每一步都要验证页面是否真正加载成功！**

1. **初步搜索**：navigate到网站 → get_page_info验证页面标题
2. **列表提取**：get_elements获取搜索结果列表（limit=20）
3. **数据提取**：eval_js提取具体数据（标题、链接、摘要）- 至少前5-10条
4. **深入点击**：从列表中选择2-3个最相关的，click点击标题进入详情
5. **详情提取**：在每个详情页get_page_info + eval_js提取完整内容
6. **交叉验证**：如果结果不理想，尝试不同的关键词再次搜索

⚠️ **页面加载失败检测**：
- navigate后必须立即get_page_info检查
- 如果页面标题包含"无法访问"、"错误"、"404"、"502"等，立即报告失败
- 如果get_elements返回0个元素，等待3秒后再次尝试，仍然为0则报告失败

🔒 **登录墙处理规则**（系统会自动检测并触发交互登录）：
- 不要在登录页面（URL 含 /signin /login /passport 或标题含"登录"/"sign in"）继续点击或填表
- 一旦发现是登录墙，**不要尝试自动登录、不要手动填用户名密码、不要重复 navigate**
- 系统会暂停并等待用户在浏览器中手动完成登录，登录后自动 reload 原 URL，你只需在剩余步骤中继续即可

返回 JSON 格式（必须包含至少8-10个步骤）：
{{
  "steps": [
    {{"tool": "navigate", "args": {{"url": "..."}}, "purpose": "..."}},
    {{"tool": "get_page_info", "args": {{}}, "purpose": "..."}},
    {{"tool": "get_elements", "args": {{"limit": 20}}, "purpose": "..."}},
    {{"tool": "eval_js", "args": {{"code": "..."}}, "purpose": "..."}},
    {{"tool": "click", "args": {{"text": "...", "tag": "a"}}, "purpose": "..."}}
  ]
}}

⚠️ 关键要求：
1. 必须包含 eval_js 提取具体数据
2. 必须包含 get_elements 获取元素列表
3. 必须包含 click 深入查看至少2个详情
4. 步骤数至少8步，最多12步

只返回 JSON。"""


def extract_prompt(description: str, observations_text: str) -> str:
    """从执行观察生成提取报告的 LLM 提示词"""
    return f"""基于以下浏览器操作结果，**深度提取**关键信息：

任务: {description}

操作记录（按顺序）:
{observations_text}

⚠️ 重要：不要只总结！要提取具体数据！

请详细提取：

1. **具体数据**（必须有）：
   - 具体的标题、名称、数字（至少5-10条）
   - 具体的链接URL
   - 具体的摘要、描述、关键内容

2. **关键发现**：
   - 最重要的3-5个发现
   - 数据中体现的趋势、模式

3. **相关资源**：
   - 重要的链接（至少3-5个）
   - 论文、项目、工具名称

4. **信息缺口**：
   - 还缺少什么重要信息

格式：
## 具体数据
- [标题/名称] - [链接] - [摘要/描述]

## 关键发现
1. ...

## 相关资源
- [资源名称](链接)

## 信息缺口
- ..."""


def per_source_summary_prompt(website: str, status: str, raw_data: str) -> str:
    """单源摘要提示词"""
    return f"""请将以下调研结果总结为关键点（300字以内）：

网站: {website}
状态: {status}
原始数据:
{raw_data[:2000]}

请总结：
1. 核心发现（最多3点）
2. 关键数据（具体数字、名称）
3. 重要链接（如有）"""


def final_synthesis_prompt(research_goal: str, summaries_text: str) -> str:
    """最终综合提示词"""
    return f"""基于以下多个来源的调研总结，生成一份精简的研究综述（800字以内）：

研究目标: {research_goal}

各来源总结:
{summaries_text}

请生成：
# 研究报告

## 核心发现
(3-5个最重要的发现)

## 详细分析
(按主题分类)

## 关键资源
(重要链接)

## 结论
(总结和建议)"""
