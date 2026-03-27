"""Patches types."""

from typing import Any, TypedDict


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


type LoadedOptionValue = str | bool | int | float | list[Any] | None


class LoadedOption(TypedDict):
    """Represents the fields of a single patch option, which are used to define `options.json`."""

    key: str
    value: LoadedOptionValue


class LoadedPatchOption(TypedDict):
    """Represents the fields which are used to define `options.json`."""

    patchName: str
    options: list[LoadedOption]
