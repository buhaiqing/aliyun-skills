"""runtime_root.py — 运行时数据根目录解析 (Sprint 18)

为 Python 脚本提供统一的 RUNTIME_ROOT 解析, 避免硬编码 audit-results/cache 等路径.

Usage:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
    from runtime_root import RuntimeRoot, get_runtime_root

    # 方式 1: 直接获取根目录
    root = get_runtime_root()
    baseline = root / "baseline"
    audit = root / "audit" / "aiops-cruise"

    # 方式 2: 完整初始化 (推荐)
    rt = RuntimeRoot("alicloud-aiops-cruise")
    rt.ensure_dirs()  # 幂等创建子目录
    audit_file = rt.audit_dir / "perceive-{ts}.json"
"""
import os
import sys
from pathlib import Path
from typing import Optional


def get_runtime_root() -> Path:
    """解析运行时数据根目录.

    优先级:
      1. 环境变量 ALIYUN_SKILLS_RUNTIME_ROOT
      2. 环境变量 SKILLS_DIR -> ${SKILLS_DIR}/.runtime
      3. 从本模块路径推断 (skill 内部 .runtime, 仅作 fallback)

    Returns:
        Path 对象, 指向运行时根目录.
    """
    env_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    # Sprint 19 修复: 使用 SKILLS_DIR 环境变量 (推荐用法, 调用方显式 export)
    skills_dir_env = os.environ.get("SKILLS_DIR")
    if skills_dir_env:
        return (Path(skills_dir_env).expanduser().resolve() / ".runtime")

    # Fallback: 推断 SKILLS_DIR (skill 内部 .runtime, 不推荐)
    lib_dir = Path(__file__).resolve().parent
    skills_dir = lib_dir.parent.parent
    return (skills_dir / ".runtime").resolve()


def normalize_skill_key(skill: str) -> str:
    """规范化 skill 短名: 去掉 'alicloud-' 前缀.

    Examples:
        'alicloud-aiops-cruise' -> 'aiops-cruise'
        'aiops-cruise'         -> 'aiops-cruise'
        'alicloud-redis-ops'   -> 'redis-ops'
    """
    if skill.startswith("alicloud-"):
        return skill[len("alicloud-"):]
    return skill


class RuntimeRoot:
    """运行时数据根目录 + 子目录访问器.

    Attributes:
        root:          根目录 (Path)
        baseline_dir:  ${root}/baseline
        cache_dir:     ${root}/cache
        tmp_dir:       ${root}/tmp
        audit_dir:     ${root}/audit/<skill_key>  (按 skill 划分)
        logs_dir:      ${root}/logs/<skill_key>
    """

    def __init__(self, skill: str = "shared", root: Optional[Path] = None):
        """初始化.

        Args:
            skill: skill 短名或全名, 如 'alicloud-aiops-cruise' 或 'aiops-cruise'
            root:  自定义根目录 (默认从环境变量/SKILLS_DIR 解析)
        """
        self.skill = skill
        self.skill_key = normalize_skill_key(skill)
        self.root = Path(root) if root else get_runtime_root()
        self.baseline_dir = self.root / "baseline"
        self.cache_dir = self.root / "cache"
        self.tmp_dir = self.root / "tmp"
        self.audit_dir = self.root / "audit" / self.skill_key
        self.logs_dir = self.root / "logs" / self.skill_key

    def ensure_dirs(self) -> None:
        """幂等创建所有子目录 (idempotent, 已存在则跳过)."""
        for d in (self.baseline_dir, self.cache_dir, self.tmp_dir,
                  self.audit_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return (f"RuntimeRoot(skill={self.skill!r}, root={self.root!r}, "
                f"audit_dir={self.audit_dir!r})")


# ── 快捷函数 ──
def audit_path(skill: str, *parts: str) -> Path:
    """快速构造 audit 子目录下的路径.

    Example:
        >>> audit_path("alicloud-aiops-cruise", "perceive-20260607T100000", "configdrift.json")
        PosixPath('/path/to/.runtime/audit/aiops-cruise/perceive-20260607T100000/configdrift.json')
    """
    rt = RuntimeRoot(skill)
    return rt.audit_dir.joinpath(*parts)


def baseline_path(*parts: str) -> Path:
    """快速构造 baseline 子目录下的路径.

    Example:
        >>> baseline_path("2026-06-07", "manifest.json")
        PosixPath('/path/to/.runtime/baseline/2026-06-07/manifest.json')
    """
    rt = RuntimeRoot()
    return rt.baseline_dir.joinpath(*parts)


# ── CLI 入口 ──
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        sys.exit(0)

    skill = sys.argv[1] if len(sys.argv) > 1 else "shared"
    rt = RuntimeRoot(skill)
    rt.ensure_dirs()
    print(f"RUNTIME_ROOT     = {rt.root}")
    print(f"RUNTIME_BASELINE = {rt.baseline_dir}")
    print(f"RUNTIME_AUDIT    = {rt.audit_dir}")
    print(f"RUNTIME_CACHE    = {rt.cache_dir}")
    print(f"RUNTIME_LOGS     = {rt.logs_dir}")
    print(f"RUNTIME_TMP      = {rt.tmp_dir}")
