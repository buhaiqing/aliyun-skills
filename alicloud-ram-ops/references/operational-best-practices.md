# Operational Best Practices — RAM

- **Least privilege:** Scope policies to specific actions, resources, and conditions. Avoid `Action: "*"` and `Resource: "*"`.
- **Rotate access keys:** Rotate access keys every 90 days. Use the rotation flow documented in SKILL.md.
- **Enable MFA:** Require MFA for console access, especially for privileged users.
- **Use roles for applications:** Prefer STS AssumeRole over long-term access keys for applications and services.
- **Monitor unused identities:** Regularly audit and delete unused users, roles, and access keys.
- **Password policy:** Enforce strong password policies via `SetPasswordPolicy`.
- **No root account for daily ops:** Create dedicated RAM users with minimal permissions for all operational tasks.