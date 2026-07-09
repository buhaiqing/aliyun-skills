# RAM User Group — Operations

> All group operations live here: **CreateGroup / GetGroup / ListGroups /
> AddUserToGroup / RemoveUserFromGroup / ListUsersForGroup / ListGroupsForUser
> / DeleteGroup**.
>
> For per-operation JSON paths, see
> [`api-response-reference.md`](../api-response-reference.md). For CLI
> conventions, see [`cli-usage.md`](../cli-usage.md).

---

## Operation: Create RAM User Group

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| Group name format | Regex: `^[a-zA-Z0-9_.@-]{1,64}$` | Valid | Ask for valid name |
| Duplicate | `aliyun ram GetGroup --GroupName {{user.group_name}}` | `EntityNotExist` | Ask reuse vs new name |

### Execution — CLI

```bash
aliyun ram CreateGroup \
  --GroupName "{{user.group_name}}" \
  --Comments "{{user.comments}}"
```

### Post-execution Validation

```bash
aliyun ram GetGroup --GroupName "{{user.group_name}}"
```

---

## Operation: Describe RAM User Group

### Execution — CLI

```bash
# Get single group
aliyun ram GetGroup --GroupName "{{user.group_name}}"

# List all groups (paginated)
aliyun ram ListGroups --MaxItems 100

# Extract specific fields
aliyun ram GetGroup --GroupName "{{user.group_name}}" \
  --output cols=GroupName,GroupId,CreateDate rows=Group
```

### Present to User

| Field | Path | Notes |
|-------|------|-------|
| GroupName | `$.Group.GroupName` | Plain text |
| GroupId | `$.Group.GroupId` | Plain text |
| Comments | `$.Group.Comments` | May be absent |
| CreateDate | `$.Group.CreateDate` | ISO 8601 |

---

## Operation: Add User to Group

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| Group exists | `GetGroup --GroupName {{user.group_name}}` | Success | HALT; create group first |

### Execution — CLI

```bash
aliyun ram AddUserToGroup \
  --GroupName "{{user.group_name}}" \
  --UserName "{{user.user_name}}"
```

### Post-execution Validation

```bash
aliyun ram ListUsersForGroup --GroupName "{{user.group_name}}"
```

---

## Operation: Remove User from Group

### Pre-flight Checks

| Check | Method | Expected | On Failure |
|-------|--------|----------|------------|
| User exists | `GetUser --UserName {{user.user_name}}` | Success | HALT; create user first |
| Group exists | `GetGroup --GroupName {{user.group_name}}` | Success | HALT; create group first |

### Execution — CLI

```bash
aliyun ram RemoveUserFromGroup \
  --GroupName "{{user.group_name}}" \
  --UserName "{{user.user_name}}"
```

### Post-execution Validation

```bash
aliyun ram ListUsersForGroup --GroupName "{{user.group_name}}"
```

> Expect `{{user.user_name}}` to no longer appear in the result.

---

## Operation: List Users For Group

### Execution — CLI

```bash
aliyun ram ListUsersForGroup --GroupName "{{user.group_name}}"
```

### Present to User

| Field | Path | Notes |
|-------|------|-------|
| UserName | `$.Users.User[].UserName` | Plain text |
| DisplayName | `$.Users.User[].DisplayName` | May be absent |
| JoinDate | `$.Users.User[].JoinDate` | ISO 8601 |

---

## Operation: List Groups For User

### Execution — CLI

```bash
aliyun ram ListGroupsForUser --UserName "{{user.user_name}}"
```

### Present to User

| Field | Path | Notes |
|-------|------|-------|
| GroupName | `$.Groups.Group[].GroupName` | Plain text |
| Comments | `$.Groups.Group[].Comments` | May be absent |
| JoinDate | `$.Groups.Group[].JoinDate` | ISO 8601 |

> Used during the `DeleteUser` 5-step dependency cascade
> ([`user-operations.md` §DeleteUser](user-operations.md#operation-delete-ram-user))
> to enumerate groups to clean up.

---

## Operation: Delete RAM User Group

### Pre-flight (Safety Gate)

- **MUST** obtain explicit confirmation.
- **MUST** warn that all users will be removed from the group and all attached
  policies will be detached.
- **MUST** verify no critical workflow depends on this group's policy
  bindings before deletion.

### Execution — CLI

```bash
aliyun ram DeleteGroup --GroupName "{{user.group_name}}"
```

### Post-execution Validation

1. Call `GetGroup` — expect `EntityNotExist.Group` or equivalent 404.
2. Optionally `ListUsersForGroup` — should return empty.
3. Report success.

### Failure Recovery

| Error pattern | Max retries | Backoff | Agent Action |
|---------------|-------------|---------|--------------|
| `EntityNotExist.Group` | 0 | — | HALT; group does not exist |
| `DeleteConflict.Group.User` | 0 | — | Remove all users first |
| `DeleteConflict.Group.Policy` | 0 | — | Detach all policies first |
| Throttling / 429 | 3 | exponential | Back off; respect `Retry-After` |
| `InternalError` / 5xx | 3 | 2s, 4s, 8s | Retry; then HALT with RequestId |
