"""Live2D 模型导入：复制模型文件夹 + 走 SDK 的 Node pipeline 生成 soullink.profile.json。"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelImporter:
    def __init__(self, sdk_dir: Path, static_l2d_dir: Path) -> None:
        self._sdk_dir = Path(sdk_dir)
        self._static_l2d_dir = Path(static_l2d_dir)

    def import_folder(self, src_dir: Path) -> dict[str, Any]:
        """同步导入（供后台线程调用）。返回 {ok, model?, error?}。"""
        src = Path(src_dir)
        model_dir = src.name

        if not src.is_dir():
            return {"ok": False, "error": "所选路径不是文件夹"}
        if not (src / f"{model_dir}.model3.json").exists():
            return {
                "ok": False,
                "error": f"缺少 {model_dir}.model3.json（文件名需与文件夹名一致）",
            }
        if not list(src.glob("*.moc3")):
            return {"ok": False, "error": "缺少 .moc3 几何文件"}
        if (self._static_l2d_dir / model_dir).exists():
            return {"ok": False, "error": f"模型 {model_dir} 已存在，请先删除或换一个文件夹名"}
        if not shutil.which("node") or not shutil.which("npm"):
            return {"ok": False, "error": "未检测到 Node/npm，请安装 Node.js（20.19+ 或 22.12+）"}

        sdk_l2d = self._sdk_dir / "l2d"
        sdk_model_dir = sdk_l2d / model_dir
        try:
            sdk_l2d.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, sdk_model_dir, dirs_exist_ok=True)

            self._register_catalog(model_dir)

            if not (self._sdk_dir / "packages" / "profile-generator" / "dist").exists():
                self._run_npm(["run", "packages:build"], timeout=600)

            self._run_npm(
                ["run", "profile:generate", "--", "--model", model_dir], timeout=180
            )

            if not (sdk_model_dir / "soullink.profile.json").exists():
                return {"ok": False, "error": "profile 生成未产出 soullink.profile.json"}

            self._static_l2d_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(sdk_model_dir, self._static_l2d_dir / model_dir)

            return {"ok": True, "model": model_dir}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "npm 命令超时"}
        except Exception as e:  # noqa: BLE001
            logger.warning("导入模型失败：%s", e)
            return {"ok": False, "error": str(e)}

    def _catalog_block(self, model_dir: str) -> str:
        return (
            "  {\n"
            f'    id: "{model_dir.lower()}",\n'
            f'    modelDir: "{model_dir}",\n'
            f'    modelFile: "{model_dir}.model3.json",\n'
            f'    displayName: "{model_dir}",\n'
            "    view: { scale: 1, x: 0, y: 0 }\n"
            "  }"
        )

    def _register_catalog(self, model_dir: str) -> None:
        """幂等地把模型注册进 model-catalog.js（profile:generate 依赖它过滤模型）。"""
        catalog = self._sdk_dir / "src" / "model-catalog.js"
        text = catalog.read_text(encoding="utf-8")
        if f'modelDir: "{model_dir}"' in text:
            return
        if "\n];" not in text:
            raise RuntimeError("model-catalog.js 结构无法识别，无法注册模型")
        block = self._catalog_block(model_dir)
        catalog.write_text(text.replace("\n];", ",\n" + block + "\n];", 1), encoding="utf-8")

    def _unregister_catalog(self, model_dir: str) -> None:
        catalog = self._sdk_dir / "src" / "model-catalog.js"
        text = catalog.read_text(encoding="utf-8")
        block = self._catalog_block(model_dir)
        if ",\n" + block in text:
            catalog.write_text(text.replace(",\n" + block, "", 1), encoding="utf-8")

    def delete_model(self, model_dir: str) -> dict[str, Any]:
        static_dir = self._static_l2d_dir / model_dir
        if not static_dir.exists():
            return {"ok": False, "error": f"模型 {model_dir} 不存在"}
        try:
            shutil.rmtree(static_dir)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"删除失败：{e}"}

        sdk_dir = self._sdk_dir / "l2d" / model_dir
        if sdk_dir.exists():
            try:
                shutil.rmtree(sdk_dir)
            except Exception:  # noqa: BLE001
                pass
        try:
            self._unregister_catalog(model_dir)
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "model": model_dir}

    def _run_npm(self, args: list[str], timeout: int) -> str:
        cmd = "npm " + subprocess.list2cmdline(args)
        proc = subprocess.run(
            cmd,
            cwd=str(self._sdk_dir),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-1200:]
            raise RuntimeError(f"npm {args[0]} 失败：{tail}")
        return proc.stdout
