# redis-cli Install — Single Source of Truth

> **本文件是 `alicloud-redis-ops` 中 redis-cli 安装/升级逻辑的唯一权威定义。**
> `redis-cli-execution.md` 的 Step 3（独立安装）和 合并执行脚本（Step 1 ensure-redis-cli）都 **必须** 内联本文件中的 `ensure_redis_cli` 函数，不得维护副本。

## 设计目标

| 目标 | 实现方式 |
|------|---------|
| **幂等** | `ensure_redis_cli` 每次先检查存在 + 版本，符合即跳过 |
| **OS 自适应** | 9 种发行版 + 源码兜底；自动检测 `dnf`/`yum` 优先级 |
| **阿里云加速** | 检测 ECS 元数据 `100.100.100.200`，自动切换 `mirrors.cloud.aliyuncs.com` |
| **离线兜底** | 用户可通过 `REDIS_CLI_BIN_URL` 指定预编译二进制 URL |
| **源码编译鲁棒** | 自动补齐 `gcc make tar curl`；优先阿里云镜像下载源码包 |
| **结构化诊断** | 所有输出符合 [Diagnostic Logging Standard](../../docs/diagnostic-logging-standard.md) |

## 退出码契约

| Exit | 阶段 | 含义 |
|:----:|------|------|
| 0 | ensure | 已存在且版本符合，或安装/升级成功 |
| 20 | install | 安装失败（pkg manager / source / offline binary 都失败） |
| 21 | install | 源码编译依赖（gcc/make）缺失且无法自动安装 |
| 22 | install | 离线模式 `REDIS_CLI_BIN_URL` 下载失败 |

---

## 实现概览（脚本结构）

> **完整可执行脚本：[`scripts/redis-cli-install.sh`](../scripts/redis-cli-install.sh)**（380 行 bash；本节为函数索引和使用速查，**实现单一来源在 `.sh` 文件中**）

### 速览：包含的函数

| 函数 | 角色 |
|------|------|
| `version_gte` | 版本比较工具 |
| `detect_aliyun_ecs` | 探测是否为阿里云 ECS（元数据 100.100.100.200） |
| `use_aliyun_apt_mirror` / `_yum_` / `_apk_` | 切换包源到阿里云内网镜像（仅阿里云 ECS） |
| `install_build_tools` | 源码编译依赖（gcc/make）自动安装 |
| `install_from_offline_url` | 策略 0：从 `REDIS_CLI_BIN_URL` 下载 |
| `install_by_pkg_manager` | 策略 1：调系统包管理器 |
| `install_from_source` | 策略 2：源码编译兜底 |
| **`ensure_redis_cli`** | **主入口**：幂等检查 + 三层策略链 + 失败诊断 |

### 如何使用

见下方 [「调用契约」](#调用契约--被引用方必读) 章节，三种方式：`cat` 拼装、`source` 调用、`bash` 直接执行。

### 速看脚本

```bash
cat alicloud-redis-ops/scripts/redis-cli-install.sh   # 或 bat / less (如已安装)
```
---

## OS 支持矩阵

| OS / 发行版 | 检测 ID | 包管理器 | 包名 | 阿里云镜像加速 | 备注 |
|------------|---------|---------|------|-------------|------|
| Ubuntu / Debian | `ubuntu` `debian` | apt | `redis-tools` | ✅ `mirrors.cloud.aliyuncs.com` | 默认 5.0-7.0 |
| Alibaba Cloud Linux 2 | `alinux` (ver=2) | yum | `redis` | ✅ 自带 | epel 自动可用 |
| Alibaba Cloud Linux 3 | `alinux` (ver=3) | dnf | `redis` | ✅ 自带 | redis 6.x |
| Anolis OS | `anolis` | dnf | `redis` | ✅ 自带 | 优先 dnf |
| CentOS 7 / RHEL 7 | `centos` `rhel` | yum + epel | `redis` | ✅ | 需 `epel-release` |
| CentOS 8+ / RHEL 8+ | `centos` `rhel` | dnf | `redis` | ✅ | 直接安装 |
| Fedora | `fedora` | dnf | `redis` | ➖ | 国内可用 |
| openSUSE / SLES | `opensuse*` `suse` `sles` | zypper | `redis` | ➖ | 修复了原脚本遗漏 |
| Alpine | `alpine` | apk | `redis` | ✅ `mirrors.aliyun.com` | musl libc |
| 未知 OS | `*` | 源码编译 | redis-stable | ✅ 镜像下载源码 | 自动装 gcc/make |

---

## 用户配置指南（必读）

> 本节面向**首次使用者**和**运维实施人员**。脚本本身开箱即用——**不配置任何环境变量也能跑**（默认走包管理器 + 公网官方源 + 源码兜底）。下面两个可选能力是为特定场景准备的。

### 我该不该配置？30 秒决策树

```
你的 ECS 跳板机在哪里？
│
├─ 在阿里云上（VPC 公网或专有网络都算）
│   │
│   ├─ ECS 能访问公网吗？(curl baidu.com 通)
│   │   ├─ ✅ 能 → 强烈建议开启「镜像加速」（更快、更稳）
│   │   └─ ❌ 不能（纯内网/VPC 无公网网关） → 用「离线模式」
│   │
│   └─ 如果不确定 → 什么都不配也能跑（自动探测，对你无副作用）
│
├─ 在自建 IDC / 其他云 / 混合云
│   │
│   ├─ 能访问公网 → 什么都不配，默认走公网官方源
│   └─ 不能访问公网 → 用「离线模式」
│
└─ 在专有云 / 金融云 / 政务云
    └─ 99% 用「离线模式」（请联系你的云架构师确认）
```

**一句话总结**：

| 场景 | 推荐配置 | 期望效果 |
|------|---------|---------|
| 阿里云 ECS + 公网通 | ✅ **开镜像加速** | 安装时间从 30-60s 降到 5-15s |
| 阿里云 ECS + 公网不通 | ✅ **用离线模式** | 否则连包源都拉不到，必败 |
| 非阿里云 + 公网通 | ❌ **什么都不配** | 默认行为已足够 |
| 任何环境 + 公网不通 | ✅ **用离线模式** | 唯一可行路径 |

---

### 能力 1：阿里云内网镜像加速

#### 这是什么？

阿里云 ECS 内部对官方包源（Ubuntu / Debian / CentOS / Alpine）做了镜像，URL 是
`mirrors.cloud.aliyuncs.com` —— **只在阿里云 VPC 内可达**（外面访问不到）。
本脚本在安装前会**自动探测**当前机器是不是阿里云 ECS，如果是就把 apt/yum/apk
源临时切到这个内网地址。

#### 我需要做什么？

**默认开启，无需操作**。脚本通过访问元数据接口 `100.100.100.200`（1 秒超时）
判断环境：

| 探测结果 | 脚本行为 | 是否需要你介入 |
|---------|---------|-------------|
| 探测到阿里云 ECS | 自动切换到内网镜像源 | ❌ 不需要 |
| 不是阿里云 ECS | 跳过切换，走原系统配置 | ❌ 不需要 |
| 元数据接口超时（极少见） | 跳过切换，走原系统配置 | ❌ 不需要 |

#### 我能关掉它吗？

**目前没提供开关**（设计上认为没场景需要关）。如果你确实需要禁用（比如想强制
测试公网源），可以临时改 hosts：

```bash
# 在执行 ensure_redis_cli 前
echo "127.0.0.1 mirrors.cloud.aliyuncs.com" >> /etc/hosts
# 这样镜像探测会失败，自动 fallback 到官方源
```

如果你需要"内置可关闭开关"作为功能，请告诉我们。

#### 怎么验证它生效了？

执行后看日志，**有这一行说明加速生效**：

```
[14:32:01] [DIAG] aliyun_ecs=yes
[14:32:01] [INSTALL] apt_mirror=aliyun-internal     ← 这里说明已切换
[14:32:08] [RESULT] INSTALL=SUCCESS
[14:32:08] [DIAG] install_duration=7s              ← 通常 < 15s
```

**没切换的情况**（也是正常的，仅速度慢一些）：

```
[14:32:01] [DIAG] aliyun_ecs=no                    ← 不是阿里云 ECS
[14:32:01] [INSTALL] pkg_manager=apt pkg=redis-tools
[14:32:38] [RESULT] INSTALL=SUCCESS
[14:32:38] [DIAG] install_duration=37s             ← 走的公网官方源
```

#### 副作用？

| 场景 | 影响 |
|------|------|
| 阿里云 ECS | sources.list 会被**自动备份**到 `.bak.redis-install` 再修改；后续手动可恢复 |
| 非阿里云环境 | 探测 1 秒后超时 → 跳过切换，**零副作用** |
| 已经手动配过镜像的机器 | 脚本检测到现有 `mirrors.cloud.aliyuncs.com` 引用，**跳过切换，不破坏你的配置** |

恢复原 sources（如果你想还原）：

```bash
# Ubuntu/Debian
mv /etc/apt/sources.list.bak.redis-install /etc/apt/sources.list

# CentOS/RHEL
for f in /etc/yum.repos.d/*.bak.redis-install; do
  mv "$f" "${f%.bak.redis-install}"
done

# Alpine
mv /etc/apk/repositories.bak.redis-install /etc/apk/repositories
```

---

### 能力 2 — 离线模式 `REDIS_CLI_BIN_URL`

#### 这是什么？

让你**自己准备一份 `redis-cli` 二进制文件**，放在你内网能访问的地方（OSS、
Nexus、HTTP 服务器、共享存储 HTTP 暴露…都行）。脚本会**优先**从你给的 URL 下载，
完全跳过包管理器 + 公网。

#### 什么时候必须用？

| 情况 | 是否必须用离线模式 |
|------|----------------|
| 金融云 / 政务云 / 专有云 | ✅ 通常**必须**（无公网且内部源不一定有 redis） |
| 自建 IDC，无公网出口 | ✅ **必须**（公网源拉不到） |
| 网闸隔离的生产环境 | ✅ **必须** |
| 容器镜像基于 distroless / scratch 等 minimal 镜像 | ✅ 推荐（包管理器都没有） |
| 强合规要求"软件供应链审计"（必须用自审过的二进制） | ✅ 推荐 |
| 阿里云 ECS + 公网通 | ❌ 不需要 |

#### 完整准备步骤（4 步）

**Step 1：选一份 redis-cli 二进制**

按目标 ECS 的 OS 和架构选择。最稳的是用 `musl` 静态链接版本（一份二进制走天下）：

| 来源 | 优点 | 缺点 |
|------|------|------|
| 阿里云内部已有镜像仓库 | 速度最快、合规 | 需要内部同事提供 |
| 自己编译（musl 静态） | 最可控 | 需要一台编译机 |
| GitHub 开源构建（如 [redis-cli-static](https://github.com/sapcc/docker-redis-static)） | 现成可用 | 需评估安全性 |

**最简单的"自编译"方法（产出 amd64 静态二进制）**：

```bash
# 在任意一台 Linux 机器（或本机 docker）：
docker run --rm -v $(pwd):/out alpine:3.19 sh -c '
  apk add --no-cache build-base curl &&
  curl -fsSL https://download.redis.io/redis-stable.tar.gz | tar xz -C /tmp &&
  cd /tmp/redis-stable &&
  make redis-cli MALLOC=libc CFLAGS="-static" LDFLAGS="-static" -j2 &&
  cp src/redis-cli /out/redis-cli-7.2-musl-amd64
'
# 产物：./redis-cli-7.2-musl-amd64（约 1.5MB，静态链接，几乎所有 Linux 通用）
```

**Step 2：上传到内网可达的位置**

| 方案 | 示例 URL | 推荐场景 |
|------|---------|---------|
| 阿里云 OSS（VPC 内网域名） | `https://my-bucket.oss-cn-hangzhou-internal.aliyuncs.com/bin/redis-cli` | 阿里云内网 |
| 阿里云 OSS（公网，签名 URL） | `https://my-bucket.oss-cn-hangzhou.aliyuncs.com/bin/redis-cli?Signature=...` | 有外网或临时分享 |
| 内部 Nexus / Artifactory | `https://nexus.intra/repository/raw/redis-cli` | 已有制品库 |
| 内部 HTTP 服务器 | `http://10.0.0.5/bin/redis-cli` | IDC 简易方案 |
| ECS 内置（少见） | 用 user-data 在创建时拷贝到 `/usr/local/bin/redis-cli`，本脚本会直接 `SKIP_INSTALL=YES` | 镜像预装 |

**Step 3：把 URL 配到 `.env`**

```bash
# 在项目根 .env 文件中追加（推荐方式）
cat >> .env <<'EOF'

# redis-cli 离线下载源 (alicloud-redis-ops/references/redis-cli-install.md)
# 适用：专有云 / 无公网环境 / 合规审计要求
REDIS_CLI_BIN_URL=https://my-bucket.oss-cn-hangzhou-internal.aliyuncs.com/bin/redis-cli-7.2-musl-amd64
EOF
```

> 注意：`.env` 文件**已在 .gitignore 中**，不会被提交。如果你需要团队共享 URL，
> 把它放到 `.env.example` 里作为注释模板。

**Step 4：验证**

```bash
# 4.1 本地能拉到这个 URL 吗？
curl -fsSL -m 10 "$(grep REDIS_CLI_BIN_URL .env | cut -d= -f2-)" -o /tmp/test-redis-cli
file /tmp/test-redis-cli  # 应输出 ELF 64-bit LSB executable
/tmp/test-redis-cli --version  # 应输出 redis-cli 7.x.x

# 4.2 跑一次合并脚本，看日志里有这两行：
#   [INSTALL] strategy=offline url=https://...
#   [RESULT] INSTALL=SUCCESS
```

#### 三种配置方式对比

脚本通过环境变量 `REDIS_CLI_BIN_URL` 读取，**任何能把这个变量传到 ECS 上 bash
进程**的方式都行：

| 方式 | 步骤 | 适用场景 | 安全性 |
|------|------|---------|--------|
| **A. `.env` 文件（推荐）** | 1. 改 `.env`<br>2. Agent 自动加载 | 日常运维、开发 | ⭐⭐⭐（.env 不入 git） |
| **B. ECS user-data 注入** | 创建 ECS 时在 user-data 写 `export REDIS_CLI_BIN_URL=...` | 永久预置、批量机器 | ⭐⭐⭐ |
| **C. RunCommand 即时传入** | 调用时拼接 `export ...; <script>` | 临时一次性调试 | ⭐⭐（命令历史可见） |

#### 二进制要求清单

```text
✓ 可执行格式：ELF (Linux)
✓ 架构：与目标 ECS 一致（amd64 / arm64 / aarch64）
✓ 链接方式：推荐静态链接（musl），避免 glibc 版本不兼容
✓ 版本：≥ 5.0（要支持 --bigkeys --hotkeys 需 ≥ 6.0）
✓ 大小：通常 1-3 MB
✗ macOS 的 redis-cli 不能用（Mach-O 格式）
✗ Windows 的 .exe 不能用
```

#### 怎么验证它生效了？

**生效**的日志：

```
[14:32:01] [DIAG] OFFLINE_BIN_URL=SET
[14:32:01] [INSTALL] strategy=offline url=https://my-bucket.../redis-cli-7.2-musl-amd64
[14:32:02] [RESULT] INSTALL=SUCCESS
[14:32:02] [RESULT] REDIS_CLI_VERSION=7.2.4
```

**失败的常见原因**：

| 日志特征 | 原因 | 解决 |
|---------|------|------|
| `[ERROR] TYPE=OFFLINE_DOWNLOAD_FAILED` | URL 不可达 / 鉴权失败 | 在 ECS 上 `curl -v <URL>` 看具体错误 |
| `Exec format error` (执行时) | 架构不匹配（armv7 拉了 amd64） | 准备对应架构的二进制 |
| `version 'GLIBC_2.28' not found` | glibc 太老 | 改用 musl 静态二进制 |
| 下载到 0 字节 | OSS 签名过期 / 私有桶无权限 | 重新生成签名 URL，或改为公开读 |

---

### 两个能力的优先级关系

脚本内部按以下顺序尝试，**前一个成功就跳过后面的**：

```
1. REDIS_CLI_BIN_URL 已设置？        → 用离线模式（不走包管理器）
   ↓ (未设置或下载失败)
2. 探测到阿里云 ECS？                  → 切换内网镜像源 → 走包管理器
   ↓ (非阿里云或镜像切换失败)
3. 走原系统的包管理器（公网官方源）     → 装 redis-tools / redis
   ↓ (包管理器没有 redis 包)
4. 源码编译（自动装 gcc make）         → 阿里云源码镜像 → 官方源
   ↓ (全部失败)
5. exit 20/21/22 + 失败诊断日志
```

> **关键**：四层兜底**全自动**。用户只在「特殊场景」需要主动开能力 2（离线模式）。
> 能力 1（镜像加速）**永远是被动开启的**，没有"用户配置"概念。

---

### 常见问答（FAQ）

**Q1：我什么都不配，会不会出问题？**
A：99% 场景下不会。默认会自动探测环境并尽力安装。**只在"无公网 + 内部源没有 redis"**时才会失败（你会看到 exit 21/22），此时必须配 `REDIS_CLI_BIN_URL`。

**Q2：阿里云镜像加速会不会污染我的系统？**
A：会修改 `/etc/apt/sources.list`（或对应文件），但**改之前会备份**到 `.bak.redis-install`，且只在**确实是阿里云 ECS**时才动。本节"恢复原 sources"小节有还原命令。

**Q3：我能不能把 `REDIS_CLI_BIN_URL` 设成 ECS 本地路径（`file://`）？**
A：不行，脚本用 `curl` 下载，只支持 `http://` / `https://`。如果文件已经在 ECS 上，直接把它 `cp /path/redis-cli /usr/local/bin/`，下次跑脚本会 `SKIP_INSTALL=YES`。

**Q4：多台 ECS 要共用一份 redis-cli，每次都下载好慢？**
A：两个方案：(1) 把二进制放进 ECS 镜像（自定义镜像），新创建的实例都自带；(2) 用 OSS 的 VPC 内网域名（`oss-cn-xxx-internal.aliyuncs.com`），同 region ECS 拉取 <1s。

**Q5：我担心安全——脚本会从外网下载未签名的二进制？**
A：默认行为只用**包管理器的官方源**（GPG 签名验证）。源码兜底的下载 URL 是 `download.redis.io`（官方）和阿里云镜像。**只有当你主动设了 `REDIS_CLI_BIN_URL`**，才会从你给的 URL 下载——这个 URL 由你掌控，你自己负责签名/审计。

**Q6：能不能要求脚本"只允许离线模式，禁止任何外网"？**
A：当前没有"严格模式"开关。如果你设了 `REDIS_CLI_BIN_URL` 且下载失败，脚本**会自动 fallback 到包管理器**（这是友好默认）。如果你需要"失败即停止"的严格模式（合规场景），请告诉我们，可以加 `REDIS_CLI_STRICT_OFFLINE=yes` 这种开关。

---

## 调用契约 — 被引用方必读

> **v1.2.0 起，安装脚本已抽取为独立文件 [`scripts/redis-cli-install.sh`](../scripts/redis-cli-install.sh)。被引用方不再需要复制粘贴函数体。**

被引用文件（如 `redis-cli-execution.md`、未来的 `aiops` skill 等）在云助手脚本中应：

1. **优先方式：拼装时 `cat` 进来**（推荐，无需手动维护副本）
   ```bash
   SCRIPT="$(cat alicloud-redis-ops/scripts/redis-cli-install.sh)
   <你的业务逻辑>"
   aliyun ecs RunCommand --CommandContent "$SCRIPT" ...
   ```

2. **本地调用方式：`source` 后调用函数**
   ```bash
   source alicloud-redis-ops/scripts/redis-cli-install.sh
   REQUIRED_VERSION=6.0 ensure_redis_cli || exit $?
   ```

3. **直接执行（测试/排查）**
   ```bash
   bash alicloud-redis-ops/scripts/redis-cli-install.sh
   # 退出码 0 = 成功；20/21/22 见上方退出码契约
   ```

4. **使用环境变量传参**（不要硬编码）
   ```bash
   export REQUIRED_VERSION="6.0"                    # 可选
   export REDIS_CLI_BIN_URL="https://..."            # 可选，离线模式
   ```

5. **不得用 `set -e` 包住 `ensure_redis_cli`**；函数内部已用 `set +e/-e` 管理子命令退出码。

6. **本文件（install.md）是设计规范 + 用户文档**；任何对**实现**的修改请改 `scripts/redis-cli-install.sh`，本文件随之更新对应说明。

---

## 变更日志

| Version | Date | Change |
|---------|------|--------|
| 1.3.0 | 2026-06-12 | **修复 5 个 P0/P1 bug**：(1) `use_aliyun_yum_mirror` 的 sed 表达式因 `#` 分隔符冲突导致 `bad flag` 错误，改用 `\|`（实测通过）；(2) 移除 `.sh` 末尾不可靠的 `BASH_SOURCE` 守卫，改为显式 `REDIS_CLI_INSTALL_AUTORUN=1` 开关；(3) 修复 `execution.md` Step 2 残留的"从 install.md 复制函数"过时文档；(4) 合并脚本改用 `printf %q` 转义 + `<<'BIZ'` 带引号 here-doc 杜绝 shell 注入；(5) 实测 source/autorun/直跑三种模式行为正确。本次实际验证：sed 在 mock CentOS repo 上跑通；mirrorlist 正确注释、baseurl 正确替换为 Aliyun。 |
| 1.2.0 | 2026-06-12 | **安装脚本抽取为独立可执行文件 `scripts/redis-cli-install.sh`**（344 行 bash）；调用契约简化为 `cat`/`source`/`bash` 三种方式；本 .md 文件保留为「设计规范 + 用户配置指南」；`redis-cli-execution.md` 合并脚本改为即时拼装，**无需手动复制粘贴函数**。 |
| 1.1.0 | 2026-06-12 | 新增「用户配置指南」章节：30 秒决策树、能力 1（镜像加速）和能力 2（离线模式）的完整使用说明、4 步配置流程、6 条 FAQ、副作用与还原方法、二进制自编译命令 |
| 1.0.0 | 2026-06-12 | 抽取为单一权威源；新增 SUSE/zypper 支持；新增阿里云镜像源加速；新增离线模式（`REDIS_CLI_BIN_URL`）；新增源码编译依赖自动安装；统一退出码契约（20/21/22） |
