# Redis CLI Execution via Cloud Assistant

通过阿里云 ECS 云助手（Cloud Assistant）在目标 ECS 实例上执行任意 Redis CLI 命令的详细操作指南。

> **⚠️ 安装/升级 redis-cli 的唯一权威源是 [redis-cli-install.md](./redis-cli-install.md)。**
> 本文件中所有涉及 `ensure_redis_cli` 函数的位置都必须从该文件**完整内联**，不得维护副本。

## 前提条件

- `aliyun` CLI 已安装并配置
- 目标 ECS 实例处于 `Running` 状态且 Cloud Assistant 已安装
- ECS 与 Redis 实例在同一 VPC 内，或网络可达
- `aliyun ecs` CLI 已就绪

## 执行流程一览

```
Step 1: 获取 Redis 连接地址        → aliyun r-kvstore describe-instance-attribute
Step 2: 幂等 ensure redis-cli      → aliyun ecs RunCommand (内联 ensure_redis_cli)
Step 3: 配置 REDISCLI_AUTH（可选）  → aliyun ecs RunCommand (export 即时生效)
Step 4: 执行 Redis 命令            → aliyun ecs RunCommand (redis-cli DEL/GET/SET...)
```

**推荐使用「合并执行」脚本**（Step 2 → Step 3 → Step 4 一次调用）— 见本文末尾。

---

## Step 1: 获取 Redis 连接地址

从 Redis 实例属性中自动获取连接域名：

```bash
aliyun r-kvstore describe-instance-attribute \
  --InstanceId "{{user.redis_instance_id}}" \
  --output cols=ConnectionDomain rows=InstanceAttribute.ConnectionDomain
```

赋值到变量（后续步骤使用）：

```bash
REDIS_HOST="{{user.redis_host}}"
REDIS_PORT="{{user.redis_port|6379}}"
REDIS_PASSWORD="{{user.redis_password|}}"
```

---

## Step 2: 幂等 ensure redis-cli（含检查 + 按需安装/升级）

**权威实现**：[`scripts/redis-cli-install.sh`](../scripts/redis-cli-install.sh)（344 行 bash，
通过 `bash -n` 语法检查）。详细设计、OS 支持矩阵、阿里云镜像加速、离线模式说明见
[`redis-cli-install.md`](./redis-cli-install.md)。

**独立调用方式（仅需 ensure 时使用，可选）**：在 ECS 上 source 脚本后调用主函数：

```bash
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.ecs_instance_id}}"]' \
  --CommandContent "$(
    cat alicloud-redis-ops/scripts/redis-cli-install.sh
    cat <<'BIZ'

# 业务侧显式调用（不依赖 .sh 末尾的 autorun 守卫）
REQUIRED_VERSION="${REQUIRED_VERSION:-}"
REDIS_CLI_BIN_URL="${REDIS_CLI_BIN_URL:-}"
export REQUIRED_VERSION REDIS_CLI_BIN_URL
ensure_redis_cli
exit $?
BIZ
  )" \
  --Type "RunShellScript" \
  --Name "ensure-redis-cli" \
  --Timeout 300
```

> 说明：`<<'BIZ'`（**带引号**）保证 here-doc 内不做变量插值，避免 shell 注入。
> `REQUIRED_VERSION` / `REDIS_CLI_BIN_URL` 由调用方在 **本地 shell** 中预先 `export`
> 后通过云助手脚本顶部继承；不要把用户输入直接拼到字符串里。

### Step 2 退出码

| ExitCode | 含义 | 后续动作 |
|:--------:|------|---------|
| 0  | 已存在且版本符合 / 安装升级成功 | 继续 Step 3 |
| 20 | 安装失败（pkg manager + 源码兜底都失败） | 查 `[DIAG] disk_free/mem_free/dns_test` |
| 21 | 源码编译依赖缺失且无法自动安装 | 检查 OS 包源；考虑设 `REDIS_CLI_BIN_URL` 走离线 |
| 22 | 离线 `REDIS_CLI_BIN_URL` 下载失败 | 检查 URL / 网络 |

> **大多数场景下应直接使用「合并执行」脚本**（见末尾），无需单独跑 Step 2。

---

## Step 3: 配置 REDISCLI_AUTH（可选）

`REDISCLI_AUTH` 是 `redis-cli` 原生支持的环境变量，设置后每个连接自动带 `AUTH`
命令，避免密码出现在 `ps aux` 或命令历史中。

> **推荐做法**：不持久化写入 `~/.bashrc`；仅在当前 `RunCommand` 进程内 `export`
> 一次即可（合并执行脚本已经这样做）。这样既符合安全最小化原则，也避免脏数据残留。

```bash
# 仅当需要持久化（例如运维人员后续手动登录使用）时才写 bashrc
if [ -n "$REDIS_PASSWORD" ] && [ "${PERSIST_AUTH:-no}" = "yes" ]; then
  if ! grep -q "REDISCLI_AUTH" ~/.bashrc 2>/dev/null; then
    echo "export REDISCLI_AUTH='$REDIS_PASSWORD'" >> ~/.bashrc
    echo "[$(date +%H:%M:%S)] [RESULT] AUTH_PERSISTED=YES"
  else
    echo "[$(date +%H:%M:%S)] [RESULT] AUTH_PERSISTED=ALREADY"
  fi
fi
```

---

## Step 4: 执行 Redis 命令（带诊断）

```bash
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.ecs_instance_id}}"]' \
  --CommandContent '#!/bin/bash
set -e

# ===== DIAGNOSTIC: 开始执行 Redis 命令 =====
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=exec"
echo "[$(date +%H:%M:%S)] [DIAG] TARGET_HOST={{user.redis_host}}"
echo "[$(date +%H:%M:%S)] [DIAG] TARGET_PORT={{user.redis_port|6379}}"
echo "[$(date +%H:%M:%S)] [DIAG] HAS_PASSWORD=$([ -n "{{user.redis_password|}}" ] && echo YES || echo NO)"
echo "[$(date +%H:%M:%S)] [DIAG] COMMAND={{user.redis_command}}"

REDIS_HOST="{{user.redis_host}}"
REDIS_PORT="{{user.redis_port|6379}}"
REDIS_PASSWORD="{{user.redis_password|}}"
REDIS_COMMAND="{{user.redis_command}}"

# 网络可达性检测
echo "[$(date +%H:%M:%S)] [DIAG] Testing network connectivity..."
if timeout 5 bash -c "echo > /dev/tcp/$REDIS_HOST/$REDIS_PORT" 2>/dev/null; then
  echo "[$(date +%H:%M:%S)] [RESULT] NETWORK_REACHABLE=YES"
else
  echo "[$(date +%H:%M:%S)] [RESULT] NETWORK_REACHABLE=NO"
  echo "[$(date +%H:%M:%S)] [DIAG] Cannot connect to $REDIS_HOST:$REDIS_PORT"
  echo "[$(date +%H:%M:%S)] [DIAG] Check: same VPC? Security group? Redis whitelist?"
  exit 30   # exit code 30 = network unreachable
fi

# 执行 Redis 命令
echo "[$(date +%H:%M:%S)] [EXEC] redis-cli -h $REDIS_HOST -p $REDIS_PORT $REDIS_COMMAND"

EXEC_START=$(date +%s%N)
if [ -n "$REDIS_PASSWORD" ]; then
  REDIS_OUTPUT=$(REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" $REDIS_COMMAND 2>&1)
  CLI_EXIT=$?
else
  REDIS_OUTPUT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" $REDIS_COMMAND 2>&1)
  CLI_EXIT=$?
fi
EXEC_DURATION_MS=$(( ($(date +%s%N) - EXEC_START) / 1000000 ))

echo "[$(date +%H:%M:%S)] [DIAG] Execution duration: ${EXEC_DURATION_MS}ms"
echo "[$(date +%H:%M:%S)] [DIAG] redis-cli exit code: $CLI_EXIT"

# 诊断 Redis 错误
if [ $CLI_EXIT -ne 0 ]; then
  echo "[$(date +%H:%M:%S)] [RESULT] REDIS_COMMAND_RESULT=FAILED"
  echo "[$(date +%H:%M:%S)] [RESULT] REDIS_ERROR=$(echo "$REDIS_OUTPUT" | head -3)"

  # 错误分类
  case "$REDIS_OUTPUT" in
    *NOAUTH*)       echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=AUTH_FAILED FIX=Check redis password" ;;
    *WRONGPASS*)    echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=WRONG_PASSWORD FIX=Incorrect password" ;;
    *MOVED*)        echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=CLUSTER_MOVED FIX=Use redis-cli -c" ;;
    *ASK*)          echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=CLUSTER_ASK FIX=Use redis-cli -c" ;;
    *WRONGTYPE*)    echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=WRONG_TYPE FIX=Command not applicable" ;;
    *unknown\ command*) echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=UNKNOWN_COMMAND FIX=Check syntax" ;;
    *READONLY*)     echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=READONLY_SLAVE FIX=Connect to master" ;;
    *BUSY*)         echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=BUSY_SCRIPT FIX=Redis busy, retry later" ;;
    *OOM*)          echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=OUT_OF_MEMORY FIX=Scale up or evict" ;;
    *LOADING*)      echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=LOADING FIX=Redis loading data" ;;
    *refused*)      echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=CONNECTION_REFUSED FIX=Port closed" ;;
    *timeout*)      echo "[$(date +%H:%M:%S)] [DIAG] ERROR_TYPE=TIMEOUT FIX=Network latency" ;;
  esac

  echo "$REDIS_OUTPUT"
  exit 40   # exit code 40 = redis command failed
fi

# 成功
echo "[$(date +%H:%M:%S)] [RESULT] REDIS_COMMAND_RESULT=SUCCESS"
echo "[$(date +%H:%M:%S)] [RESULT] OUTPUT=$REDIS_OUTPUT"
echo "$REDIS_OUTPUT"
exit 0
' \
  --Type "RunShellScript" \
  --Name "exec-redis-command" \
  --Timeout 120
```

### ExitCode 速查

| ExitCode | 含义 | 人工决策要点 |
|:--------:|------|-------------|
| 0 | 命令执行成功 | 检查 `OUTPUT=...` 确认实际结果 |
| 30 | 网络不可达 | 确认 VPC、安全组、白名单配置 |
| 40 | 命令执行失败 | 查看 `ERROR_TYPE=...` 参考 `FIX=...` |

---

## 合并执行（一键完成，推荐）

**推荐使用**。`ensure_redis_cli`（来自 [`scripts/redis-cli-install.sh`](../scripts/redis-cli-install.sh)）+ `REDISCLI_AUTH` + 网络检查 + 命令执行**合并为一次云助手调用**。

> **核心设计**：本节脚本通过 `cat scripts/redis-cli-install.sh` 即时拼装，**无需手动复制粘贴**任何函数。安装逻辑改动只需修改 `scripts/redis-cli-install.sh` 一处，本文件自动跟随。

### 一键执行命令

```bash
# 必须在仓库根目录执行（脚本通过相对路径 cat .sh）
cd /path/to/aliyun-skills

# === 1. 收集运行参数到本地 shell 变量（不会进 here-doc 的字符串插值）===
export REGION="{{user.region}}"
export ECS_ID="{{user.ecs_instance_id}}"
# 以下变量由 Cloud Assistant 注入到远程 bash 环境（通过 --CommandContent 顶部 export）
export REDIS_HOST="{{user.redis_host}}"
export REDIS_PORT="{{user.redis_port|6379}}"
export REDIS_PASSWORD="{{user.redis_password|}}"
export REDIS_COMMAND="{{user.redis_command}}"
export REQUIRED_VERSION="{{user.redis_cli_version|}}"
export REDIS_CLI_BIN_URL="${REDIS_CLI_BIN_URL:-}"  # 来自 .env，未设即空

# === 2. 构造云助手脚本：env 注入头 + 安装函数库 + 业务逻辑 ===
#
# 关键安全设计：
#   - 用户输入（密码、命令、host 等）通过 `printf '%q'` 安全转义后 export
#   - 业务逻辑用 `<<'BIZ'`（带引号 here-doc）→ 远程脚本中所有 $VAR 都在远程展开
#   - 用户数据从不与脚本字符串拼接，杜绝 shell 注入
#
SCRIPT_CONTENT=$(
  # 头部：env 注入（用 printf %q 转义每个值，防注入）
  printf 'export REDIS_HOST=%q\n'        "$REDIS_HOST"
  printf 'export REDIS_PORT=%q\n'        "$REDIS_PORT"
  printf 'export REDIS_PASSWORD=%q\n'    "$REDIS_PASSWORD"
  printf 'export REDIS_COMMAND=%q\n'     "$REDIS_COMMAND"
  printf 'export REQUIRED_VERSION=%q\n'  "$REQUIRED_VERSION"
  printf 'export REDIS_CLI_BIN_URL=%q\n' "$REDIS_CLI_BIN_URL"
  echo

  # 中部：安装函数库（cat 进来，不带任何变量插值）
  echo '# ===== 来自 scripts/redis-cli-install.sh（单一权威源） ====='
  cat alicloud-redis-ops/scripts/redis-cli-install.sh
  echo

  # 尾部：业务逻辑（带引号 here-doc，远程展开变量）
  cat <<'BIZ'
# ===== 业务逻辑（远程展开 $VAR，不在本地插值）=====
OVERALL_START=$(date +%s)
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=env-snapshot"
echo "[$(date +%H:%M:%S)] [DIAG] HOSTNAME=$(hostname)"
echo "[$(date +%H:%M:%S)] [DIAG] ARCH=$(uname -m)"
echo "[$(date +%H:%M:%S)] [DIAG] TARGET=${REDIS_HOST}:${REDIS_PORT}"
echo "[$(date +%H:%M:%S)] [DIAG] HAS_PASSWORD=$([ -n "$REDIS_PASSWORD" ] && echo YES || echo NO)"
echo "[$(date +%H:%M:%S)] [DIAG] OFFLINE_BIN_URL=$([ -n "$REDIS_CLI_BIN_URL" ] && echo SET || echo NO)"

# ----- Step 1: 幂等 ensure redis-cli（显式调用，不依赖 autorun 守卫）-----
ensure_redis_cli
ENSURE_RC=$?
[ "$ENSURE_RC" -ne 0 ] && exit "$ENSURE_RC"

# ----- Step 2: 配置 REDISCLI_AUTH（进程内即时生效，不写 bashrc）-----
if [ -n "$REDIS_PASSWORD" ]; then
  export REDISCLI_AUTH="$REDIS_PASSWORD"
fi

# ----- Step 3: 网络可达性检查 -----
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=network-check"
if timeout 5 bash -c "echo > /dev/tcp/$REDIS_HOST/$REDIS_PORT" 2>/dev/null; then
  echo "[$(date +%H:%M:%S)] [RESULT] NETWORK=REACHABLE"
else
  echo "[$(date +%H:%M:%S)] [RESULT] NETWORK=UNREACHABLE"
  HOST_IP=$(getent hosts "$REDIS_HOST" 2>/dev/null | head -1 \
            || dig +short "$REDIS_HOST" 2>/dev/null \
            || echo "DNS_FAILED")
  echo "[$(date +%H:%M:%S)] [DIAG] DNS_RESULT=$HOST_IP"
  exit 30
fi

# ----- Step 4: 执行 Redis 命令 -----
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=exec"
echo "[$(date +%H:%M:%S)] [EXEC] redis-cli -h $REDIS_HOST -p $REDIS_PORT $REDIS_COMMAND"

EXEC_START=$(date +%s%N)
# 使用 eval 数组方式避免 $REDIS_COMMAND 拼接漏洞（命令是受信任输入）
REDIS_OUTPUT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" $REDIS_COMMAND 2>&1)
CLI_EXIT=$?
EXEC_DURATION_MS=$(( ($(date +%s%N) - EXEC_START) / 1000000 ))

if [ $CLI_EXIT -ne 0 ]; then
  echo "[$(date +%H:%M:%S)] [RESULT] REDIS_EXEC=FAILED"
  case "$REDIS_OUTPUT" in
    *NOAUTH*)    echo "[$(date +%H:%M:%S)] [ERROR] TYPE=AUTH_FAILED FIX=Check password" ;;
    *WRONGPASS*) echo "[$(date +%H:%M:%S)] [ERROR] TYPE=WRONG_PASSWORD FIX=Incorrect password" ;;
    *MOVED*)     echo "[$(date +%H:%M:%S)] [ERROR] TYPE=CLUSTER_MOVED FIX=Use redis-cli -c" ;;
    *ASK*)       echo "[$(date +%H:%M:%S)] [ERROR] TYPE=CLUSTER_ASK FIX=Use redis-cli -c" ;;
    *WRONGTYPE*) echo "[$(date +%H:%M:%S)] [ERROR] TYPE=WRONG_TYPE FIX=Not applicable for this key type" ;;
    *READONLY*)  echo "[$(date +%H:%M:%S)] [ERROR] TYPE=READONLY_SLAVE FIX=Connect to master" ;;
    *OOM*)       echo "[$(date +%H:%M:%S)] [ERROR] TYPE=OOM FIX=Scale up or evict" ;;
    *refused*)   echo "[$(date +%H:%M:%S)] [ERROR] TYPE=CONNECTION_REFUSED FIX=Port closed" ;;
    *timeout*)   echo "[$(date +%H:%M:%S)] [ERROR] TYPE=TIMEOUT FIX=Network issue" ;;
    *)           echo "[$(date +%H:%M:%S)] [ERROR] TYPE=UNKNOWN FIX=Review output" ;;
  esac
  echo "$REDIS_OUTPUT"
  exit 40
fi

OVERALL_DURATION=$(( $(date +%s) - OVERALL_START ))
echo "[$(date +%H:%M:%S)] [RESULT] REDIS_EXEC=SUCCESS"
echo "---"
echo "[SUMMARY] Overall: SUCCESS"
echo "[SUMMARY] Total duration: ${OVERALL_DURATION}s"
echo "[SUMMARY] Exec duration: ${EXEC_DURATION_MS}ms"
echo "[SUMMARY] Command: $REDIS_COMMAND"
echo "[SUMMARY] Result: $REDIS_OUTPUT"
echo "---"
echo "$REDIS_OUTPUT"
exit 0
BIZ
)

# === 3. 提交云助手 ===
aliyun ecs RunCommand \
  --RegionId "$REGION" \
  --InstanceIds "[\"${ECS_ID}\"]" \
  --CommandContent "$SCRIPT_CONTENT" \
  --Type "RunShellScript" \
  --Name "redis-cli-exec" \
  --Timeout 300
```

### 它做了什么（5 个关键点）

| 关键点 | 实现 | 解决的问题 |
|--------|------|----------|
| **单一来源** | `cat alicloud-redis-ops/scripts/redis-cli-install.sh` 即时内联 | 安装逻辑只活在 `.sh` 一处，无副本漂移 |
| **杜绝注入** | 用户输入用 `printf '%q'` 转义后 export，业务逻辑用 `<<'BIZ'` 带引号 here-doc | 密码/命令含特殊字符不会破坏脚本 |
| **显式调用** | 业务部分明确 `ensure_redis_cli; ENSURE_RC=$?` | 不依赖 `.sh` 末尾的 autorun 守卫（已改为需 `REDIS_CLI_INSTALL_AUTORUN=1` 显式开启） |
| **远程展开** | 业务逻辑中 `$VAR` 在 Cloud Assistant **远程 bash** 展开，而非本地 | 用户值只通过 env 传递，从不参与脚本字符串拼接 |
| **审计安全** | 提交给云助手的 `--CommandContent` 里**包含密码（已转义）**——这是阿里云 ECS Cloud Assistant 的固有限制 | 见下方「关于密码进入 RunCommand 字段的说明」 |

### 关于密码进入 RunCommand 字段的说明

⚠️ **诚实声明**：即便使用 `printf '%q'` 转义，密码仍然会以**转义后的明文形式**出现在
`aliyun ecs RunCommand --CommandContent` 的参数里。这是 Cloud Assistant 架构的固有限制
（任何 RunCommand 都必须传递完整脚本内容），**无法在本方案内规避**。

**实际审计风险**：
- ✅ 阿里云审计日志（ActionTrail）**默认不记录** `--CommandContent` 字段值
  （记录调用元数据但不记录脚本内容）
- ⚠️ 本机 shell 历史（`~/.bash_history`）**会记录**完整命令——执行前请 `unset HISTFILE`
- ⚠️ CI/CD 系统的 job log 可能记录——确保 CI 配置中 mask 密码变量

**如果需要绝对零密码进入 RunCommand**：
- 方案 A：在 ECS 上预先把密码写入 `/etc/profile.d/redis-auth.sh`（chmod 600），脚本读环境变量
- 方案 B：使用阿里云 KMS Secrets Manager，脚本里 `aliyun kms get-secret-value` 拉取
- 方案 C：使用阿里云 RAM 临时凭据 + ACL 而非密码鉴权（Redis 6.0+）

这三个方案超出本 skill 范围，参考 [`alicloud-kms-ops`](../../alicloud-kms-ops/SKILL.md) 实施。

### 本地预览拼装后的完整脚本

```bash
# 不实际执行，仅查看最终拼装的脚本长什么样
cd /your/repo/root
wc -l alicloud-redis-ops/scripts/redis-cli-install.sh   # 当前约 360 行（autorun guard 之后）
# 语法检查（仅安装函数库部分）：
bash -n alicloud-redis-ops/scripts/redis-cli-install.sh && echo "✓ 安装脚本语法 OK"
# 完整拼装预览（不执行）：
( cd /your/repo/root && bash -n <(cat alicloud-redis-ops/scripts/redis-cli-install.sh) ) \
  && echo "✓ 拼装语法 OK"
```


> _上一个版本（v1.2.x）这里有一段含 `[PASTE FUNCTIONS HERE]` 占位的合并脚本骨架，已被上方「即时拼装」方案替代。如需历史版本，参见 git log。_
---

## Post-execution Validation

轮询命令执行结果并解析诊断摘要：

```bash
INVOKE_ID="{{output.invoke_id}}"

echo "[$(date +%H:%M:%S)] [DIAG] POLLING InvokeId=$INVOKE_ID"
POLL_START=$(date +%s)

for i in $(seq 1 60); do
  RESULT=$(aliyun ecs DescribeInvocationResults \
    --RegionId "{{user.region}}" \
    --InvokeId "$INVOKE_ID" \
    --InstanceId "{{user.ecs_instance_id}}" \
    --output cols=InvocationStatus,ExitCode,Output \
      rows=Invocation.InvocationResults.InvocationResult[0].{InvocationStatus,ExitCode,Output})

  STATUS=$(echo "$RESULT" | cut -d, -f1)
  EXIT_CODE=$(echo "$RESULT" | cut -d, -f2)
  OUTPUT_B64=$(echo "$RESULT" | cut -d, -f3-)

  case "$STATUS" in
    Success)
      OUTPUT=$(echo "$OUTPUT_B64" | base64 -d 2>/dev/null || echo "$OUTPUT_B64")
      SUMMARY=$(echo "$OUTPUT" | grep "^\[SUMMARY\]" || true)
      ERROR_TYPE=$(echo "$OUTPUT" | grep "\[ERROR\] TYPE=" || echo "N/A")

      echo ""
      echo "========== Diagnostic Summary =========="
      echo " Overall: $([ "$EXIT_CODE" -eq 0 ] && echo "✅ SUCCESS" || echo "❌ FAILED (exit $EXIT_CODE)")"
      [ -n "$SUMMARY" ] && echo "$SUMMARY" | sed 's/\[SUMMARY\]/ /g'
      [ -n "$ERROR_TYPE" ] && echo " Error: $(echo "$ERROR_TYPE" | sed 's/\[ERROR\]//g')"
      echo "========================================"
      echo ""
      echo "$OUTPUT"
      break
      ;;
    Failed|Timeout|Cancelled)
      OUTPUT=$(echo "$OUTPUT_B64" | base64 -d 2>/dev/null || echo "$OUTPUT_B64")
      echo "[ERROR] CloudAssistant Status=$STATUS ExitCode=$EXIT_CODE"
      echo "$OUTPUT"
      exit 1
      ;;
    *) sleep 5 ;;
  esac
done
```

---

## 退出码全表

| ExitCode | 阶段 | 含义 | 人工动作 |
|:--------:|------|------|---------|
| 0  | 整体 | ✅ 全部成功 | 检查 `[SUMMARY] Result:` |
| 20 | install | 安装失败（pkg + 源码都失败） | 检查 `[DIAG] disk/mem/dns_test` |
| 21 | install | 源码编译依赖缺失 | 设 `REDIS_CLI_BIN_URL` 走离线模式 |
| 22 | install | 离线包下载失败 | 检查 `REDIS_CLI_BIN_URL` URL / 网络 |
| 30 | network | ECS → Redis 不可达 | 检查 VPC/安全组/白名单 |
| 40 | exec | Redis 命令失败 | 查看 `[ERROR] TYPE=... FIX=...` |

> **退出码来源**：20/21/22 由 [`redis-cli-install.md`](./redis-cli-install.md) 定义；30/40 在本文件定义。两份契约对齐。

---

## 日志解读示例

**正常删除 Key（已装 redis-cli）：**
```
[14:32:01] [RESULT] SKIP_INSTALL=YES                ← 幂等命中，跳过安装
[14:32:01] [RESULT] REDIS_CLI_VERSION=6.2.6
[14:32:01] [RESULT] NETWORK=REACHABLE
[14:32:01] [EXEC] redis-cli -h host -p 6379 DEL mykey
[14:32:01] [RESULT] REDIS_EXEC=SUCCESS
[14:32:01] [SUMMARY] Result: (integer) 1            ← 删除成功
```

**首次安装（Alibaba Cloud Linux 3）：**
```
[14:32:01] [DIAG] os=alinux version=3 aliyun_ecs=yes
[14:32:01] [INSTALL] pkg_manager=dnf pkg=redis os=alinux
[14:32:08] [RESULT] INSTALL=SUCCESS
[14:32:08] [RESULT] REDIS_CLI_VERSION=6.2.7
```

**离线模式（专有云）：**
```
[14:32:01] [DIAG] aliyun_ecs=no
[14:32:01] [INSTALL] strategy=offline url=https://internal-mirror.intra/bin/redis-cli
[14:32:03] [RESULT] INSTALL=SUCCESS
```

**网络不可达：**
```
[14:32:01] [RESULT] NETWORK=UNREACHABLE
[14:32:01] [DIAG] DNS_RESULT=xxx.redis.rds.aliyuncs.com  ← DNS 解析成功但端口不通
exit code 30 → 人工排查 VPC/安全组/白名单
```

**密码错误：**
```
[14:32:01] [RESULT] NETWORK=REACHABLE
[14:32:01] [ERROR] TYPE=AUTH_FAILED FIX=Check password
exit code 40 → 人工检查密码
```

---

## Failure Recovery

| Error pattern | Diagnostic Log Signal | Agent / Human Action |
|---------------|----------------------|----------------------|
| Cloud Assistant 未安装 | Pre-flight 检查失败 | 引导安装：[官方文档](https://help.aliyun.com/zh/ecs/user-guide/install-the-cloud-assistant-agent) |
| 包管理器安装失败 | `[INSTALL]` rc≠0 → 自动 fallback 到源码 | 看是否最终 `INSTALL=SUCCESS` |
| 源码编译失败（缺 gcc） | rc=21 | 自动 `install_build_tools` 失败 → 用 `REDIS_CLI_BIN_URL` |
| 阿里云镜像源切换失败 | `[WARN] aliyun_mirror_failed` | 自动 fallback 到官方源 |
| Cloud Assistant 超时 | `InvocationStatus=Timeout` | 增加 `--Timeout` |
| 网络不可达（exit 30） | `NETWORK=UNREACHABLE` | 检查 VPC/安全组/白名单 |
| 密码错误（exit 40） | `TYPE=AUTH_FAILED` | 获取正确的 Redis 密码 |
| 命令语法错误（exit 40） | `TYPE=UNKNOWN_COMMAND` | 检查命令语法 |
| 集群 MOVED（exit 40） | `TYPE=CLUSTER_MOVED` | 使用 `-c` 参数 |
| 只读节点写入（exit 40） | `TYPE=READONLY_SLAVE` | 确认连的是主节点 |
| 磁盘不足导致安装失败 | `disk_free=...` 不足 | 清理 ECS 磁盘 |

---

## 使用示例

**示例 1：删除特定 Redis Key**
```bash
ECS_INSTANCE_ID="i-bp1xxxxx"
REDIS_HOST="r-bp1xxxxx.redis.rds.aliyuncs.com"
REDIS_PASSWORD="MyPass123"
REDIS_COMMAND="DEL 8560pfuat:gpas_lsym_funding_token"
# → 执行合并脚本
```

**示例 2：查询 Key 剩余 TTL**
```bash
REDIS_COMMAND="TTL session:token:abc123"
# Output: -1 (永不过期), -2 (已过期), >=0 (剩余秒数)
```

**示例 3：批量删除匹配前缀的 Key（生产慎用）**
```bash
REDIS_COMMAND="EVAL \"return redis.call('DEL', unpack(redis.call('KEYS', ARGV[1])))\" 0 'cache:temp:*'"
# ⚠️ 会阻塞 Redis，建议低峰期执行
```

**示例 4：bigkey 扫描**
```bash
REDIS_COMMAND="--bigkeys"
# Output: 各种 type 的 top key 报告
```

**示例 5：hotkey 扫描（需先设 maxmemory-policy 为 LFU）**
```bash
REDIS_COMMAND="--hotkeys"
# 前置：CONFIG SET maxmemory-policy allkeys-lfu
```

**示例 6：要求 redis-cli 6.0+（用于 RESP3 / TLS）**
```bash
# 通过 user.redis_cli_version 触发版本检查
# 当前版本不达标时会自动 upgrade
```

**示例 7：专有云离线模式**
```bash
# 在 .env 中：
#   REDIS_CLI_BIN_URL=https://internal-mirror.intra/bin/redis-cli-6.2-musl-amd64
# 合并脚本会优先尝试离线 URL，跳过外网拉取
```
