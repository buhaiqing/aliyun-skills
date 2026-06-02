# Redis CLI Execution via Cloud Assistant

通过阿里云 ECS 云助手（Cloud Assistant）在目标 ECS 实例上执行任意 Redis CLI 命令的详细操作指南。

## 前提条件

- `aliyun` CLI 已安装并配置
- 目标 ECS 实例处于 `Running` 状态且 Cloud Assistant 已安装
- ECS 与 Redis 实例在同一 VPC 内，或网络可达
- `aliyun ecs` CLI 已就绪

## 执行流程一览

```
Step 1: 获取 Redis 连接地址 → aliyun r-kvstore describe-instance-attribute
Step 2: 幂等检查 redis-cli   → aliyun ecs RunCommand (which redis-cli)
Step 3: 安装/升级 redis-cli   → aliyun ecs RunCommand (apt/yum/apk/source)
Step 4: 密码配置检查（可选）  → aliyun ecs RunCommand (REDISCLI_AUTH)
Step 5: 执行 Redis 命令      → aliyun ecs RunCommand (redis-cli DEL/GET/SET...)
```

**推荐使用「合并执行」脚本**（Step 2 → Step 3 → Step 5 一键完成）。

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

## Step 2: 幂等检查 redis-cli 环境

在目标 ECS 上探测 `redis-cli` 是否存在及版本：

```bash
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.ecs_instance_id}}"]' \
  --CommandContent '#!/bin/bash
set -e

# ===== DIAGNOSTIC: 检查 redis-cli 环境 =====
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=env-check"
echo "[$(date +%H:%M:%S)] [DIAG] HOSTNAME=$(hostname)"
echo "[$(date +%H:%M:%S)] [DIAG] OS=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d \")"
echo "[$(date +%H:%M:%S)] [DIAG] ARCH=$(uname -m)"

# 检查 redis-cli 是否存在
if ! command -v redis-cli &>/dev/null; then
  echo "[$(date +%H:%M:%S)] [RESULT] STATUS=NOT_INSTALLED"
  echo "[$(date +%H:%M:%S)] [DIAG] redis-cli not found in PATH"
  echo "[$(date +%H:%M:%S)] [DIAG] PATH=$PATH"
  exit 10   # exit code 10 = not installed
fi

# 检查版本
VERSION=$(redis-cli --version 2>/dev/null)
echo "[$(date +%H:%M:%S)] [RESULT] STATUS=INSTALLED"
echo "[$(date +%H:%M:%S)] [RESULT] VERSION=$VERSION"
echo "[$(date +%H:%M:%S)] [RESULT] BINARY_PATH=$(which redis-cli)"

# 检查 redis-cli 是否能正常运行
echo "[$(date +%H:%M:%S)] [DIAG] Testing redis-cli binary..."
redis-cli --version >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "[$(date +%H:%M:%S)] [RESULT] BINARY_CHECK=PASS"
else
  echo "[$(date +%H:%M:%S)] [RESULT] BINARY_CHECK=FAIL - binary may be corrupted"
  exit 11   # exit code 11 = binary broken
fi

echo "[$(date +%H:%M:%S)] [DIAG] env-check completed successfully"
' \
  --Type "RunShellScript" \
  --Name "check-redis-cli" \
  --Timeout 60
```

### ExitCode 速查

| ExitCode | 输出特征 | 含义 | 后续动作 |
|:--------:|----------|------|---------|
| 0 | `STATUS=INSTALLED` | 已存在且可用 | 执行 Step 5，跳过安装 |
| 10 | `STATUS=NOT_INSTALLED` | 未安装 | 执行 Step 3 安装 |
| 11 | `BINARY_CHECK=FAIL` | 二进制损坏 | 执行 Step 3 重装 |
| （版本 < 要求） | `VERSION=...` | 版本过低 | 执行 Step 3 升级 |

---

## Step 3: 安装/升级 redis-cli

按 OS 发行版自适应安装：

```bash
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.ecs_instance_id}}"]' \
  --CommandContent '#!/bin/bash
set -e

# ===== DIAGNOSTIC: 开始安装 =====
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=install"
START_TS=$(date +%s)

# 探测 OS
echo "[$(date +%H:%M:%S)] [DIAG] Detecting OS..."
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS=$ID
  OS_VER=$VERSION_ID
  echo "[$(date +%H:%M:%S)] [DIAG] OS_ID=$ID"
  echo "[$(date +%H:%M:%S)] [DIAG] OS_VERSION=$VERSION_ID"
  echo "[$(date +%H:%M:%S)] [DIAG] OS_NAME=$PRETTY_NAME"
else
  OS=$(uname -s)
  echo "[$(date +%H:%M:%S)] [WARN] /etc/os-release not found, fallback to uname: $OS"
fi

install_redis_cli() {
  case "$OS" in
    ubuntu|debian)
      echo "[$(date +%H:%M:%S)] [INSTALL] Package manager: apt"
      echo "[$(date +%H:%M:%S)] [INSTALL] Package: redis-tools"
      apt-get update -qq && apt-get install -y -qq redis-tools
      INSTALL_EXIT=$?
      ;;
    centos|rhel|anolis|alinux)
      echo "[$(date +%H:%M:%S)] [INSTALL] Package manager: yum"
      echo "[$(date +%H:%M:%S)] [INSTALL] Package: redis"
      yum install -y -q redis
      INSTALL_EXIT=$?
      ;;
    fedora)
      echo "[$(date +%H:%M:%S)] [INSTALL] Package manager: dnf"
      dnf install -y -q redis
      INSTALL_EXIT=$?
      ;;
    opensuse*|suse)
      echo "[$(date +%H:%M:%S)] [INSTALL] Package manager: zypper"
      zypper install -y redis
      INSTALL_EXIT=$?
      ;;
    alpine)
      echo "[$(date +%H:%M:%S)] [INSTALL] Package manager: apk"
      apk add redis
      INSTALL_EXIT=$?
      ;;
    *)
      echo "[$(date +%H:%M:%S)] [INSTALL] OS=$OS not recognized by package manager"
      echo "[$(date +%H:%M:%S)] [INSTALL] Falling back to source compilation..."
      curl -fsSL https://download.redis.io/redis-stable.tar.gz -o /tmp/redis.tar.gz
      echo "[$(date +%H:%M:%S)] [INSTALL] Downloaded redis-stable.tar.gz"
      tar xzf /tmp/redis.tar.gz -C /tmp
      cd /tmp/redis-stable && make redis-cli && cp src/redis-cli /usr/local/bin/
      INSTALL_EXIT=$?
      cd / && rm -rf /tmp/redis-stable /tmp/redis.tar.gz
      ;;
  esac
  return ${INSTALL_EXIT:-$?}
}

install_redis_cli
INSTALL_RESULT=$?
DURATION=$(( $(date +%s) - START_TS ))

echo "[$(date +%H:%M:%S)] [DIAG] Install duration: ${DURATION}s"
echo "[$(date +%H:%M:%S)] [DIAG] Install exit code: $INSTALL_RESULT"

# 验证安装结果
if [ $INSTALL_RESULT -eq 0 ] && command -v redis-cli &>/dev/null; then
  echo "[$(date +%H:%M:%S)] [RESULT] INSTALL_RESULT=SUCCESS"
  echo "[$(date +%H:%M:%S)] [RESULT] VERSION=$(redis-cli --version)"
  echo "[$(date +%H:%M:%S)] [RESULT] BINARY_PATH=$(which redis-cli)"
  exit 0
else
  echo "[$(date +%H:%M:%S)] [RESULT] INSTALL_RESULT=FAILED"
  echo "[$(date +%H:%M:%S)] [DIAG] Last error from package manager above"
  # 收集系统信息辅助诊断
  echo "[$(date +%H:%M:%S)] [DIAG] Available disk: $(df -h / | tail -1 | awk "{print \$4}")"
  echo "[$(date +%H:%M:%S)] [DIAG] Memory free: $(free -h | grep Mem | awk "{print \$4}")"
  exit 20   # exit code 20 = install failed
fi
' \
  --Type "RunShellScript" \
  --Name "install-redis-cli" \
  --Timeout 300
```

### ExitCode 速查

| ExitCode | 含义 |
|:--------:|------|
| 0 | 安装成功 |
| 20 | 安装失败（查看上方 `[ERROR]`/`[INSTALL]` 日志定位原因） |
| 非 0 其他 | 包管理器自身报错，日志中可见具体错误信息 |

---

## Step 4: 密码配置检查（可选）

如果有密码需要持久化配置，可执行此步骤：

```bash
# 仅在提供了密码时执行此步骤
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.ecs_instance_id}}"]' \
  --CommandContent '#!/bin/bash
REDIS_PASSWORD="{{user.redis_password}}"
if [ -n "$REDIS_PASSWORD" ]; then
  # 检查是否已配置
  if grep -q "REDISCLI_AUTH" ~/.bashrc 2>/dev/null; then
    echo "AUTH_CONFIG=ALREADY_CONFIGURED"
  else
    echo "export REDISCLI_AUTH=$REDIS_PASSWORD" >> ~/.bashrc
    echo "AUTH_CONFIG=CONFIGURED"
  fi
else
  echo "AUTH_CONFIG=NO_PASSWORD"
fi
' \
  --Type "RunShellScript" \
  --Name "configure-redis-auth" \
  --Timeout 60
```

> `REDISCLI_AUTH` 是 `redis-cli` 原生支持的环境变量，设置后每个连接会自动带 `AUTH` 命令，避免密码在进程列表或日志中泄露。

---

## Step 5: 执行 Redis 命令（带诊断）

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

## 合并执行（一键完成）

**推荐使用**。将检查 → 安装 → 执行三步合并为一次云助手调用。

```bash
aliyun ecs RunCommand \
  --RegionId "{{user.region}}" \
  --InstanceIds '["{{user.ecs_instance_id}}"]' \
  --CommandContent '#!/bin/bash
#
# alicloud-redis-ops: Execute Redis Command via Cloud Assistant
# All diagnostic output uses structured prefix format:
#   [HH:MM:SS] [PHASE] key=value
#   PHASE: DIAG|INSTALL|EXEC|RESULT|WARN|ERROR
#

OVERALL_START=$(date +%s)

# ===== DIAGNOSTIC: 环境信息快照 =====
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=env-snapshot"
echo "[$(date +%H:%M:%S)] [DIAG] HOSTNAME=$(hostname)"
echo "[$(date +%H:%M:%S)] [DIAG] OS=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d \")"
echo "[$(date +%H:%M:%S)] [DIAG] KERNEL=$(uname -r)"
echo "[$(date +%H:%M:%S)] [DIAG] ARCH=$(uname -m)"
echo "[$(date +%H:%M:%S)] [DIAG] USER=$(whoami)"
echo "[$(date +%H:%M:%S)] [DIAG] UPTIME=$(uptime -p)"

# === 配置区 ===
REDIS_HOST="{{user.redis_host}}"
REDIS_PORT="{{user.redis_port|6379}}"
REDIS_PASSWORD="{{user.redis_password|}}"
REDIS_COMMAND="{{user.redis_command}}"
REQUIRED_VERSION="{{user.redis_cli_version|}}"

echo "[$(date +%H:%M:%S)] [DIAG] TARGET_HOST=$REDIS_HOST"
echo "[$(date +%H:%M:%S)] [DIAG] TARGET_PORT=$REDIS_PORT"
echo "[$(date +%H:%M:%S)] [DIAG] HAS_PASSWORD=$([ -n "$REDIS_PASSWORD" ] && echo YES || echo NO)"
echo "[$(date +%H:%M:%S)] [DIAG] REQUIRED_VERSION=$([ -n "$REQUIRED_VERSION" ] && echo "$REQUIRED_VERSION" || echo ANY)"

# === Step 1: 检查 / 安装 redis-cli ===
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=ensure-redis-cli"
STEP1_START=$(date +%s)

if ! command -v redis-cli &>/dev/null; then
  echo "[$(date +%H:%M:%S)] [WARN] redis-cli not found in PATH, installing..."
  echo "[$(date +%H:%M:%S)] [DIAG] PATH=$PATH"

  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_VER=$VERSION_ID
    echo "[$(date +%H:%M:%S)] [INSTALL] OS_ID=$OS"
    echo "[$(date +%H:%M:%S)] [INSTALL] OS_VERSION=$OS_VER"
  else
    OS=$(uname -s)
    echo "[$(date +%H:%M:%S)] [WARN] Cannot detect OS, fallback: $OS"
  fi

  case "$OS" in
    ubuntu|debian)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=apt pkg=redis-tools"
      apt-get update -qq && apt-get install -y -qq redis-tools; INSTALL_OK=$? ;;
    centos|rhel|anolis|alinux)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=yum pkg=redis"
      yum install -y -q redis; INSTALL_OK=$? ;;
    fedora)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=dnf pkg=redis"
      dnf install -y -q redis; INSTALL_OK=$? ;;
    alpine)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=apk pkg=redis"
      apk add redis; INSTALL_OK=$? ;;
    *)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=source"
      curl -fsSL https://download.redis.io/redis-stable.tar.gz -o /tmp/redis.tar.gz
      tar xzf /tmp/redis.tar.gz -C /tmp
      cd /tmp/redis-stable && make redis-cli && cp src/redis-cli /usr/local/bin/
      INSTALL_OK=$?; cd / && rm -rf /tmp/redis-stable /tmp/redis.tar.gz ;;
  esac

  STEP1_DURATION=$(( $(date +%s) - STEP1_START ))
  echo "[$(date +%H:%M:%S)] [DIAG] Step1 duration: ${STEP1_DURATION}s"

  if [ $INSTALL_OK -eq 0 ] && command -v redis-cli &>/dev/null; then
    echo "[$(date +%H:%M:%S)] [RESULT] INSTALL=SUCCESS"
    echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_PATH=$(which redis-cli)"
  else
    echo "[$(date +%H:%M:%S)] [RESULT] INSTALL=FAILED"
    echo "[$(date +%H:%M:%S)] [DIAG] disk_free=$(df -h / | tail -1 | awk "{print \$4}")"
    echo "[$(date +%H:%M:%S)] [DIAG] mem_free=$(free -h 2>/dev/null | grep Mem | awk "{print \$4}")"
    exit 20
  fi
else
  VERSION=$(redis-cli --version 2>/dev/null)
  echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_PRESENT=YES"
  echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_PATH=$(which redis-cli)"
  echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_VERSION=$VERSION"

  # 版本检查
  if [ -n "$REQUIRED_VERSION" ]; then
    CURRENT_VER=$(echo "$VERSION" | grep -oP "\d+\.\d+" | head -1)
    REQUIRED_VER=$(echo "$REQUIRED_VERSION" | grep -oP "\d+\.\d+" | head -1)
    if [ -n "$CURRENT_VER" ] && [ -n "$REQUIRED_VER" ]; then
      if [ "$(echo "$CURRENT_VER" | tr -d ".")" -lt "$(echo "$REQUIRED_VER" | tr -d ".")" ]; then
        echo "[$(date +%H:%M:%S)] [WARN] Version $CURRENT_VER < required $REQUIRED_VER"
      else
        echo "[$(date +%H:%M:%S)] [RESULT] VERSION_CHECK=PASS"
      fi
    fi
  fi
fi

# === Step 2: 配置 REDISCLI_AUTH ===
if [ -n "$REDIS_PASSWORD" ]; then
  export REDISCLI_AUTH="$REDIS_PASSWORD"
  echo "[$(date +%H:%M:%S)] [DIAG] REDISCLI_AUTH=configured"
fi

# === Step 3: 网络可达性检查 ===
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=network-check"
if timeout 5 bash -c "echo > /dev/tcp/$REDIS_HOST/$REDIS_PORT" 2>/dev/null; then
  echo "[$(date +%H:%M:%S)] [RESULT] NETWORK=REACHABLE"
else
  echo "[$(date +%H:%M:%S)] [RESULT] NETWORK=UNREACHABLE"
  HOST_IP=$(dig +short "$REDIS_HOST" 2>/dev/null || host "$REDIS_HOST" 2>/dev/null || echo "DNS_FAILED")
  echo "[$(date +%H:%M:%S)] [DIAG] DNS_RESULT=$HOST_IP"
  exit 30
fi

# === Step 4: 执行 Redis 命令 ===
echo "[$(date +%H:%M:%S)] [DIAG] PHASE=exec"
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

# === 成功: 输出摘要 ===
OVERALL_DURATION=$(( $(date +%s) - OVERALL_START ))
echo "[$(date +%H:%M:%S)] [RESULT] REDIS_EXEC=SUCCESS"
echo "[$(date +%H:%M:%S)] [RESULT] OUTPUT=$REDIS_OUTPUT"
echo "---"
echo "[SUMMARY] Overall: SUCCESS"
echo "[SUMMARY] Total duration: ${OVERALL_DURATION}s"
echo "[SUMMARY] Exec duration: ${EXEC_DURATION_MS}ms"
echo "[SUMMARY] Command: $REDIS_COMMAND"
echo "[SUMMARY] Result: $REDIS_OUTPUT"
echo "---"
echo "$REDIS_OUTPUT"
exit 0
' \
  --Type "RunShellScript" \
  --Name "redis-cli-exec" \
  --Timeout 300
```

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
| 0 | 整体 | ✅ 全部成功 | 检查 `[SUMMARY] Result:` |
| 10 | env-check | redis-cli 未安装 | 自动安装 |
| 11 | env-check | 二进制损坏 | 手动重装 |
| 20 | install | 安装失败 | 检查 `[DIAG] disk/mem/network` |
| 30 | network | 网络不可达 | 检查 VPC/安全组/白名单 |
| 40 | exec | 命令执行失败 | 查看 `[ERROR] TYPE=... FIX=...` |

---

## 日志解读示例

**正常删除 Key：**
```
[14:32:01] [RESULT] REDIS_CLI_PRESENT=YES    ← 跳过安装
[14:32:01] [RESULT] NETWORK=REACHABLE         ← 网络可达
[14:32:01] [EXEC] redis-cli -h host -p 6379 DEL mykey
[14:32:01] [RESULT] REDIS_EXEC=SUCCESS
[14:32:01] [SUMMARY] Result: (integer) 1       ← 删除成功
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
[14:32:01] [ERROR] TYPE=AUTH_FAILED FIX=Check redis password
exit code 40 → 人工检查密码
```

---

## Failure Recovery

| Error pattern | Diagnostic Log Signal | Agent / Human Action |
|---------------|----------------------|----------------------|
| Cloud Assistant 未安装 | Pre-flight 检查失败 | 引导安装：[官方文档](https://help.aliyun.com/zh/ecs/user-guide/install-the-cloud-assistant-agent) |
| `apt-get update` 失败 | `[INSTALL]` exit code 100 | 检查外部源；配置内部镜像源 |
| `yum install` 失败 | `[INSTALL]` exit code 1 | 尝试 `yum install -y epel-release` |
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