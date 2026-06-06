# 实操技巧：高效编辑阿里云 Skill

> 本文档记录在开发和维护阿里云 Skill 过程中积累的实操经验，特别是如何高效使用 `edit` / `bash` / `python` 三种方式修改 Markdown 文件。

## 为什么编辑经常失败？

`edit` 工具的 `oldText` 要求**精确匹配原文中的每一字符**，包括：

| 常见陷阱 | 示例 | 后果 |
|---|---|---|
| 不可见空白字符 | Tab vs 空格 | 匹配失败 |
| 行尾多余空格 | `"xxx "` vs `"xxx"` | 匹配失败 |
| 换行符不一致 | `\n` vs `\r\n` | 匹配失败 |
| 转义字符 | Shell 中的 `\$` vs 原文 `$` | 匹配失败 |
| 路径错误 | 编辑 A 文件但指向 B 文件 | 匹配失败 |

## 三种编辑方式的选型矩阵

| 场景 | 推荐工具 | 理由 |
|---|---|---|
| **单行关键词替换**（如修指标名） | `bash` + `sed` | 一行命令，全局替换 |
| **单处多行替换**（如改一个段落） | `edit` | 精确安全，不会误改别处 |
| **多处相同替换**（如全文件修 `Datapoints`） | `bash` + `sed` | 一次替换所有 |
| **跨段重组**（如插入新章节） | `edit` | 需要精确定位 |
| **条件替换**（如只替换第3个匹配） | `python` | sed 不支持条件 |
| **多文件批量修改** | `bash` + `find + sed` | 一次性覆盖 |
| **匹配失败后的排查** | `bash` + `grep -n -C3` | 查看精确原文 |

## 实操模式

### 模式 1：`sed` 单行替换（最快）

适合：修指标名、修参数名等**全局关键词替换**。

```bash
# 标准用法：全文件替换
sed -i '' 's/CpuUtilization/CPUUtilization/g' runbooks/01-daily-health-check.md

# 多文件替换
find runbooks/ references/ -name "*.md" -exec sed -i '' 's/旧名/新名/g' {} +
```

**优点**：一行命令，全文件/全目录替换
**缺点**：无法精确控制替换位置（会替换注释、代码块内所有匹配）

### 模式 2：`edit` 精确替换（最安全）

适合：改一个段落、插入一段代码等**单处精确修改**。

```bash
# 1. 先用 read 确认精确原文（包含行首空格）
read path/to/file offset=NN limit=20

# 2. 复制原文到 oldText（包含所有空白和换行符）
# 注意：oldText 必须一字不差，连缩进空格都算
```

**优点**：只改目标位置，不影响文件其他部分
**缺点**：遇到转义字符、多行缩进不一时容易匹配失败

### 模式 3：`python` 复杂替换（最灵活）

适合：跨段替换、条件替换、多行模板替换等**复杂场景**。

```python
# 标准替换模式
python3 << 'PYFIX'
with open("path/to/file", "r") as f:
    content = f.read()

old = """多行原文
保留缩进和换行符"""

new = """多行新内容
保留同样格式"""

if old in content:
    content = content.replace(old, new)
    with open("path/to/file", "w") as f:
        f.write(content)
    print("✅ 替换成功")
else:
    # 查找相似内容帮助调试
    idx = content.find("关键词")
    if idx >= 0:
        print(f"附近内容: {repr(content[idx:idx+100])}")
PYFIX
```

**优点**：处理复杂逻辑最可靠，支持转义、条件判断
**缺点**：需要写脚本，比前两种方式重

## 经验教训：本 Skill 开发过程中遇到的编辑事故

| 事故 | 原因 | 教训 |
|---|---|---|
| CloudMonitor Datapoints 批量修复 | 用 `edit` 逐个替换20+处——效率极低 | 应改用 `sed` 全局替换 |
| 安全组高危规则补详情 | 用 `edit` 但路径指向了 runbook 而非 `~/test/report.md` | 先确认修改的文件路径 |
| 资源组合法性校验插入 | `oldText` 包含 Shell 转义符 `\$` 导致匹配失败 | 用 `python` 处理含 Shell 特殊字符的脚本 |

## 最佳实践总结

```
单处精确修改 → edit
全局关键词替换 → sed + find
复杂多行替换 → python
匹配失败时 → grep -n -C3 先看精确原文
```