from dataclasses import dataclass, field


@dataclass
class FileSystemPermissions:
    read: list[str] = field(default_factory=list)
    write: list[str] = field(default_factory=list)


@dataclass
class PermissionsConfig:
    filesystem: bool | FileSystemPermissions = True
    clipboard: bool = True
