from __future__ import annotations

import os
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "agent" / "skills"


def workspace_root() -> Path:
    """返回 skills 的目标工作区根目录。

    优先级：环境变量 AI_WORKSPACE_ROOT > 与 agent.core.settings 相同的跨平台默认值。
    默认值沿用项目所在盘符下的 `ai_workspace`（Linux 则为项目上级目录），
    避免写死某个本机盘符。
    """

    configured = os.environ.get("AI_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path(PROJECT_ROOT.drive + os.sep) / "ai_workspace"
    return (PROJECT_ROOT.parent / "ai_workspace").resolve()


def sync_skills() -> Path:
    target_dir = workspace_root() / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)
    for source in SOURCE_DIR.iterdir():
        if not source.is_dir():
            continue
        target = target_dir / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    return target_dir


def main() -> None:
    target_dir = sync_skills()
    print(f"skills synced to: {target_dir}")


if __name__ == "__main__":
    main()
