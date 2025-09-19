import os
import subprocess
import shutil
import time
import hashlib
from pathlib import Path


class Builder:
    """
    Sistema de build evoluído para pacotes em sandbox.
    Suporta: autotools, cmake, meson, ninja, rust, python
    """

    def __init__(
        self,
        recipe,
        sandbox_path,
        dest_path,
        build_dir="build",
        install_prefix=None,
        env=None,
        jobs=os.cpu_count(),
        verbose=False,
        dry_run=False,
        timeout=0,
    ):
        self.recipe = recipe
        self.sandbox_path = Path(sandbox_path).resolve()
        self.dest_path = Path(dest_path).resolve()
        self.build_dir = self.sandbox_path / build_dir
        self.install_prefix = Path(install_prefix or self.sandbox_path / "install")
        self.env = env or os.environ.copy()
        self.jobs = str(jobs)
        self.verbose = verbose
        self.dry_run = dry_run
        self.timeout = timeout
        self.source_in_sandbox = None
        self.start_time = None

    # ----------------------
    # Auxiliares internos
    # ----------------------

    def log(self, msg, level="info"):
        colors = {
            "info": "\033[94m",
            "ok": "\033[92m",
            "warn": "\033[93m",
            "error": "\033[91m",
            "reset": "\033[0m",
        }
        prefix = {
            "info": "[*]",
            "ok": "[✔]",
            "warn": "[!]",
            "error": "[✘]",
        }
        print(f"{colors[level]}{prefix[level]} {msg}{colors['reset']}")

    def run(self, cmd, cwd=None):
        """Executa um comando no sandbox"""
        cwd = cwd or self.build_dir
        cmd = [str(c) for c in cmd]

        if self.verbose or self.dry_run:
            self.log(f"Running: {' '.join(cmd)} (cwd={cwd})", "info")

        if self.dry_run:
            return "DRY-RUN"

        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=self.timeout if self.timeout > 0 else None,
        )

        if result.returncode != 0:
            self.log(f"Erro: {' '.join(cmd)}", "error")
            self.log(result.stdout, "warn")
            self.log(result.stderr, "error")
            raise RuntimeError(
                f"Command failed: {' '.join(cmd)} (code {result.returncode})"
            )

        return result.stdout.strip()

    def checksum(self, path):
        """Calcula hash para detectar mudanças nos sources"""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def apply_hooks(self, stage):
        """Executa hooks definidos na recipe"""
        hook = getattr(self.recipe, f"{stage}_hook", None)
        if hook and callable(hook):
            self.log(f"Hook: {stage}", "info")
            hook(self)

    # ----------------------
    # Etapas principais
    # ----------------------

    def prepare_sandbox(self):
        """Cria sandbox e copia fontes"""
        for path in (self.sandbox_path, self.build_dir, self.install_prefix):
            path.mkdir(parents=True, exist_ok=True)

        src = Path(self.recipe.source_dir).resolve()
        dst = self.sandbox_path / "src"

        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        self.source_in_sandbox = dst
        self.log(f"Fontes copiadas para {dst}", "ok")

    def build(self):
        """Pipeline de build"""
        self.start_time = time.time()
        self.prepare_sandbox()

        # Dependências
        if hasattr(self.recipe, "dependencies"):
            for dep in self.recipe.dependencies:
                self.log(f"Resolvendo dependência: {dep}", "info")
                # Aqui você pode chamar outro Builder ou package manager

        self.apply_hooks("pre_configure")
        build_system = getattr(self.recipe, "build_system", None)
        src = self.source_in_sandbox

        # ----------------------
        # Seleção do sistema
        # ----------------------
        if build_system == "autotools":
            self.run([src / "configure", f"--prefix={self.install_prefix}"], cwd=src)
            self.run(["make", f"-j{self.jobs}"], cwd=src)

        elif build_system == "cmake":
            self.run(
                ["cmake", str(src), f"-DCMAKE_INSTALL_PREFIX={self.install_prefix}"],
                cwd=self.build_dir,
            )
            self.run(["cmake", "--build", ".", f"-j{self.jobs}"], cwd=self.build_dir)

        elif build_system == "meson":
            self.run(
                ["meson", "setup", str(self.build_dir), str(src), f"--prefix={self.install_prefix}"]
            )
            self.run(["meson", "compile", "-C", str(self.build_dir), f"-j{self.jobs}"])

        elif build_system == "ninja":
            self.run(["ninja", "-C", str(self.build_dir), f"-j{self.jobs}"])

        elif build_system == "rust":
            self.run(["cargo", "build", "--release"], cwd=src)

        elif build_system == "python":
            if (src / "setup.py").exists():
                self.run(["python3", "setup.py", "build"], cwd=src)
            elif (src / "pyproject.toml").exists():
                self.run(
                    ["pip", "install", ".", "--no-deps", "--prefix", str(self.install_prefix)],
                    cwd=src,
                )
            else:
                raise RuntimeError("Nenhum setup.py ou pyproject.toml encontrado")

        else:
            raise ValueError(f"Build system não suportado: {build_system}")

        self.apply_hooks("post_build")

    def install(self):
        """Instala pacote no destino"""
        self.apply_hooks("pre_install")
        build_system = getattr(self.recipe, "build_system", None)
        src = self.source_in_sandbox

        if build_system == "autotools":
            self.run(["make", "install"], cwd=src)

        elif build_system == "cmake":
            self.run(["cmake", "--install", str(self.build_dir)], cwd=self.build_dir)

        elif build_system == "meson":
            self.run(["meson", "install", "-C", str(self.build_dir)], cwd=self.build_dir)

        elif build_system == "rust":
            self.run(["cargo", "install", "--path", str(src), "--root", str(self.install_prefix)])

        elif build_system == "python":
            if (src / "setup.py").exists():
                self.run(
                    ["python3", "setup.py", "install", f"--prefix={self.install_prefix}"],
                    cwd=src,
                )
            else:
                self.run(
                    ["pip", "install", ".", "--no-deps", "--prefix", str(self.install_prefix)],
                    cwd=src,
                )

        else:
            raise ValueError(f"Build system não suportado: {build_system}")

        self.apply_hooks("post_install")

        # Copiar instalação para destino final
        if self.dest_path.exists():
            shutil.rmtree(self.dest_path)
        shutil.copytree(self.install_prefix, self.dest_path)
        self.log(f"Instalado em {self.dest_path}", "ok")

        elapsed = round(time.time() - self.start_time, 2)
        self.log(f"Build concluído em {elapsed}s", "ok")

    def clean(self):
        """Limpa build e instalação"""
        for path in (self.build_dir, self.install_prefix):
            if path.exists():
                shutil.rmtree(path)
                self.log(f"Removido {path}", "warn")
