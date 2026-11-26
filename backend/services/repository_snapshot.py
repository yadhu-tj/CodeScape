"""Acquire bounded, independent source snapshots without running target code."""

from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
from tempfile import TemporaryDirectory, mkdtemp
import time
from urllib.parse import urlsplit


SHOWCASE = Path(__file__).resolve().parents[1] / "test_harness" / "payflow-core"
EXCLUDED = {".git", ".hg", ".svn", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}
MAX_FILES = 2_000
MAX_ENTRIES = 10_000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_CLONE_BYTES = 64 * 1024 * 1024
CLONE_SECONDS = 40
WINDOWS_DEVICES = re.compile(r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³])", re.I)


class RepositoryInputError(ValueError):
    pass


@dataclass(frozen=True)
class Snapshot:
    name: str
    path: Path
    source_sha256: str
    source_url: str | None
    commit_sha: str | None


def _excluded(name: str) -> bool:
    name = name.casefold()
    return (
        name in EXCLUDED or name.startswith(".env") or "credentials" in name
        or name.endswith((".pem", ".key"))
    )


def _linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _portable_path(parts: tuple[str, ...]) -> str:
    path = "/".join(parts)
    if len(path) > 350 or len(parts) > 32 or any(
        part in {"", ".", ".."} or WINDOWS_DEVICES.fullmatch(part.split(".", 1)[0].rstrip(" "))
        or part.endswith((".", " ")) or re.search(r'[<>:"\\|?*\x00-\x1f\x7f]', part)
        for part in parts
    ):
        raise RepositoryInputError("Repository contains an unsupported path.")
    return path


def _local_source(source: str, import_root: Path) -> Path:
    path = Path(source)
    if ".." in path.parts or (path.anchor and not path.is_absolute()):
        raise RepositoryInputError("Use a path under the configured repository import root.")
    candidate = path if path.is_absolute() else import_root / path
    if not candidate.is_absolute() or not candidate.is_relative_to(import_root):
        raise RepositoryInputError("Use a path under the configured repository import root.")
    current = import_root
    for part in candidate.relative_to(import_root).parts:
        _portable_path((part,))
        current /= part
        if _linked(current.lstat()):
            raise RepositoryInputError("Repository paths cannot contain links or reparse points.")
    if not candidate.is_dir():
        raise RepositoryInputError("Repository path must be a directory.")
    return candidate


def _local_files(source: Path, storage: Path):
    pending = [source]
    inspected = 0
    while pending:
        directory = pending.pop()
        if directory.resolve(strict=True) != directory:
            raise RepositoryInputError("Repository directory changed during acquisition.")
        with os.scandir(directory) as entries:
            for entry in entries:
                inspected += 1
                if inspected > MAX_ENTRIES:
                    raise RepositoryInputError("Repository has too many directory entries.")
                path = Path(entry.path)
                if _excluded(entry.name) or path == storage:
                    continue
                relative = _portable_path(path.relative_to(source).parts)
                # Windows DirEntry.stat omits the device and inode needed for the identity check.
                info = path.lstat()
                if _linked(info):
                    raise RepositoryInputError("Repository contains a link or reparse point.")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    yield relative, info.st_size, path, info
                else:
                    raise RepositoryInputError("Repository contains a non-regular file.")


def _git_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
        GIT_ALLOW_PROTOCOL="https", GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
    )
    return env


def _git(directory: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=directory, env=_git_environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=True,
    ).stdout


def _local_commit(source: Path) -> str | None:
    # Read provenance without consulting local Git config or traversing worktree pointers.
    git_dir = source / ".git"
    try:
        info = git_dir.lstat()
        if _linked(info) or not stat.S_ISDIR(info.st_mode):
            return None
        head = _read_git_ref(git_dir / "HEAD")
        if head.startswith("ref: "):
            ref = head[5:]
            if not re.fullmatch(r"refs/[A-Za-z0-9_/-]+(?:[.][A-Za-z0-9_/-]+)*", ref):
                return None
            current = git_dir
            for part in ref.split("/"):
                current /= part
                try:
                    if _linked(current.lstat()):
                        return None
                except FileNotFoundError:
                    packed = git_dir / "packed-refs"
                    if packed.is_file() and not _linked(packed.lstat()):
                        with packed.open("rb") as stream:
                            contents = stream.read(MAX_FILE_BYTES).decode("ascii", errors="replace")
                        head = next(
                            (line.split(" ", 1)[0] for line in contents.splitlines() if line.endswith(f" {ref}")),
                            "",
                        )
                        break
                    return None
            else:
                head = _read_git_ref(current)
        return head if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", head) else None
    except (OSError, UnicodeError):
        return None


def _read_git_ref(path: Path) -> str:
    info = path.lstat()
    if _linked(info) or not stat.S_ISREG(info.st_mode) or info.st_size > 1024:
        return ""
    with path.open("rb") as stream:
        return stream.read(1024).decode("ascii").strip()


def _remote_url(source: str, git_hosts: str) -> str:
    allowed = {host.strip().lower() for host in git_hosts.split(",") if host.strip()}
    try:
        url = urlsplit(source)
        if (
            not source.startswith("https://") or source != url.geturl() or url.netloc.lower() not in allowed
            or url.netloc.lower() != url.hostname or url.query or url.fragment
            or not re.fullmatch(r"(?:/[A-Za-z0-9_.-]+){2,}", url.path)
            or any(part in {".", ".."} for part in url.path.split("/"))
        ):
            raise ValueError
    except ValueError:
        raise RepositoryInputError("Use a credential-free HTTPS Git URL on a configured host.") from None
    return source


def _clone(url: str, destination: Path) -> None:
    command = [
        "git", "-c", "http.followRedirects=false", "-c", "credential.helper=",
        "clone", "--no-checkout", "--no-tags", "--depth=1", "--single-branch",
        "--template=", "--", url, str(destination),
    ]
    with subprocess.Popen(
        command, cwd=destination.parent, env=_git_environment(), stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=os.name != "nt",
    ) as process:
        deadline = time.monotonic() + CLONE_SECONDS
        try:
            while process.poll() is None:
                objects = destination / ".git" / "objects"
                size = 0
                for path in objects.glob("*/*"):
                    try:
                        size += path.stat().st_size
                    except FileNotFoundError:
                        continue  # Git can rename the pack while it is being written.
                if size > MAX_CLONE_BYTES or time.monotonic() >= deadline:
                    raise RepositoryInputError("Git clone exceeded its size or time limit.")
                time.sleep(0.05)
            if process.returncode:
                raise RepositoryInputError("Unable to clone the configured Git repository.")
            if sum(path.stat().st_size for path in (destination / ".git" / "objects").glob("*/*")) > MAX_CLONE_BYTES:
                raise RepositoryInputError("Git clone exceeded its size limit.")
        finally:
            if process.poll() is None:
                _stop_clone(process)


def _stop_clone(process: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=True,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        if process.poll() is None:
            process.kill()


def _git_files(clone: Path):
    # Enumerate tree records incrementally so an oversized tree cannot fill memory.
    with subprocess.Popen(
        ["git", "ls-tree", "-rlz", "HEAD"], cwd=clone, env=_git_environment(),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        pending = b""
        count = 0
        try:
            while chunk := process.stdout.read1(8192):
                records = (pending + chunk).split(b"\0")
                pending = records.pop()
                if len(pending) > 16_384:
                    raise RepositoryInputError("Repository contains an unsupported path.")
                for record in records:
                    count += 1
                    if count > MAX_ENTRIES:
                        raise RepositoryInputError("Repository has too many tree entries.")
                    header, _, name = record.partition(b"\t")
                    parts = tuple(name.decode("utf-8").split("/"))
                    if any(_excluded(part) for part in parts):
                        continue
                    relative = _portable_path(parts)
                    mode, _, oid, size = header.split()
                    if mode not in {b"100644", b"100755"}:
                        raise RepositoryInputError("Git repository contains links or submodules.")
                    yield relative, int(size), oid.decode("ascii"), None
            if pending or process.wait(timeout=5):
                raise RepositoryInputError("Unable to enumerate the Git repository.")
        finally:
            if process.poll() is None:
                process.kill()


def _inventory(files):
    inventory = []
    spellings: dict[str, str] = {}
    total = 0
    for entry in files:
        relative, size, _, _ = entry
        total += size
        if len(inventory) >= MAX_FILES or size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise RepositoryInputError("Repository exceeded its file count or size limit.")
        path = Path(relative)
        for component in (path, *path.parents):
            spelling = component.as_posix()
            if spellings.setdefault(spelling.casefold(), spelling) != spelling:
                raise RepositoryInputError("Repository paths differ only by letter case.")
        inventory.append(entry)
    if not any(relative.lower().endswith(".py") for relative, *_ in inventory):
        raise RepositoryInputError("Repository has no included Python files.")
    return sorted(inventory)


def _copy_files(destination: Path, files, clone: Path | None = None) -> str:
    process = subprocess.Popen(
        ["git", "cat-file", "--batch"], cwd=clone, env=_git_environment(),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) if clone else nullcontext()
    digest = hashlib.sha256()
    with process as git:
        for relative, size, source, info in files:
            if git:
                contents = _read_git_blob(git, source, size)
            else:
                contents = _read_local_file(source, info, size)
            if len(contents) != size:
                raise RepositoryInputError("Repository changed during acquisition.")
            name = relative.encode("utf-8")
            digest.update(len(name).to_bytes(4, "big") + name + size.to_bytes(8, "big"))
            digest.update(contents)
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(contents)
    return digest.hexdigest()


def _read_git_blob(git: subprocess.Popen, source: str, size: int) -> bytes:
    git.stdin.write(f"{source}\n".encode("ascii"))
    git.stdin.flush()
    if git.stdout.readline(128).strip().split() != [source.encode("ascii"), b"blob", str(size).encode("ascii")]:
        raise RepositoryInputError("Unable to read a Git source file.")
    contents = git.stdout.read(size)
    if git.stdout.read(1) != b"\n":
        raise RepositoryInputError("Unable to read a complete Git source file.")
    return contents


def _read_local_file(source: Path, info: os.stat_result, size: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(source, flags), "rb") as stream:
        current = os.fstat(stream.fileno())
        if (not os.path.samestat(info, current) or current.st_mtime_ns != info.st_mtime_ns
                or source.resolve(strict=True) != source):
            raise RepositoryInputError("Repository changed during acquisition.")
        contents = stream.read(size + 1)
        if os.fstat(stream.fileno()).st_mtime_ns != info.st_mtime_ns:
            raise RepositoryInputError("Repository changed during acquisition.")
    return contents


def discard_snapshot(path: Path, storage: Path) -> None:
    if path.parent == storage and path.resolve() == path and path.is_dir():
        shutil.rmtree(path)


def acquire_snapshot(source: str | None, storage: Path, import_root: Path, git_hosts: str) -> Snapshot:
    destination = None
    try:
        url = _remote_url(source, git_hosts) if source and "://" in source else None
        local = None if url else _local_source(source, import_root) if source else SHOWCASE
        if local and local.is_relative_to(storage):
            raise RepositoryInputError("Import from outside managed snapshot storage.")
        name = (url.rsplit("/", 1)[-1].removesuffix(".git") if url else local.name)[:150]
        storage.mkdir(parents=True, exist_ok=True)
        destination = Path(mkdtemp(prefix="repo-", dir=storage))
        if len(str(destination)) > 500:
            raise RepositoryInputError("Managed snapshot path exceeds the storage limit.")
        if url:
            with TemporaryDirectory(prefix="clone-", dir=storage) as temporary:
                clone = Path(temporary) / "source"
                _clone(url, clone)
                commit = _git(clone, "rev-parse", "HEAD").decode("ascii").strip()
                digest = _copy_files(destination, _inventory(_git_files(clone)), clone)
        else:
            commit = _local_commit(local) if source else None
            digest = _copy_files(destination, _inventory(_local_files(local, storage)))
        return Snapshot(name, destination, digest, url, commit)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        if destination:
            discard_snapshot(destination, storage)
        if isinstance(exc, RepositoryInputError):
            raise
        raise RepositoryInputError("Unable to read or snapshot the specified repository.") from None
