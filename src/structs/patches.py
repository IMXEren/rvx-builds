"""Patches types."""

from typing import Any, NotRequired, TypedDict


class OptionInfo(TypedDict):
    """Represents the option fields parsed from the cli output."""

    name: str
    description: str
    required: bool
    key: str
    default: str
    possible_values: list[str]
    type: str  ## Java/Kotlin type


class PatchInfo(TypedDict):
    """Represents the patch fields used when patching."""

    name: str
    description: str
    app: str  ## package name
    version: str  ## preferred version
    options: list[OptionInfo]
    bundle_file: str | None  ## source patch bundle filename
    enabled: NotRequired[bool]  ## CLI default enabled state


class CompatiblePackage(TypedDict):
    """Represents one compatible package parsed from the cli output and saved to `patches.json`."""

    name: str
    versions: list[str] | None
    version_codes: NotRequired[dict[str, dict[str, list[int]]]]  ## version name to arch to version codes


type LoadedOptionValue = str | bool | int | float | list[Any] | None


class LoadedOption(TypedDict):
    """Represents the fields of a single patch option, which are used to define `options.json`."""

    key: str
    value: LoadedOptionValue


class LoadedPatchOption(TypedDict):
    """Represents the fields which are used to define `options.json`."""

    patchName: str
    options: list[LoadedOption]
