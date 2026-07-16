"""Revanced Parser."""

import re
from subprocess import PIPE, STDOUT, Popen
from time import perf_counter
from typing import Any, Self

from loguru import logger
from ruamel.yaml import YAML

from src._bundle_selector import entry_matches as _entry_matches_fn
from src.app import APP
from src.cli_args import DEFAULT_PATCH_ARGS, append_cli_argument, is_arg_enabled
from src.config import RevancedConfig
from src.exceptions import PatchingFailedError
from src.patches import Patches
from src.structs.patches import LoadedOption, LoadedOptionValue, LoadedPatchOption, PatchInfo
from src.utils import possible_archs


class Parser(object):
    """Revanced Parser."""

    def __init__(self: Self, patcher: Patches, config: RevancedConfig) -> None:
        # list[str] -> list of args for the patch
        # str -> patch name
        self._PATCHES: list[str | list[str]] = []
        self._BUNDLE_PATCHES: dict[str | None, list[str | list[str]]] = {}
        self._EXCLUDED: list[str] = []
        self._bundle_index_map: dict[str, int] = {}
        self.patcher = patcher
        self.config = config
        # We initialize with default patch argument templates and update them per app profile when needed.
        self._patch_args: dict[str, list[str]] = dict(DEFAULT_PATCH_ARGS)
        # These cached templates keep include/exclude logic simple and profile-aware.
        self._options_arg: list[str] = self._patch_args["OPTIONS"]
        self._enable_arg: list[str] = self._patch_args["ENABLED"]
        self._disable_arg: list[str] = self._patch_args["DISABLED"]

    def _format_option_value(self: Self, value: LoadedOptionValue) -> str:
        if isinstance(value, bool):
            fvalue = f"{str(value).lower()}"
        elif isinstance(value, (int, float)):
            fvalue = f"{value}"  # Numbers should not be quoted
        elif isinstance(value, list):
            formatted_list = ",".join(map(self._format_option_value, value))
            fvalue = f'"[{formatted_list}]"'  # Preserve list format
        elif value:
            fvalue = f'"{value}"'
            if self.is_env_option_value(value):
                env_key = self.get_env_option_value(value)
                logger.info(f"[OPTIONS] Getting option value from env var: '{env_key}'")
                raw_value = self.config.env.str(env_key, None)
                if raw_value is not None:
                    fvalue = raw_value
                else:
                    logger.warning(
                        f"[OPTIONS] Failed to get option value from env var: '{env_key}'! Maybe it is not set?",
                    )
        else:
            fvalue = "null"
        return fvalue

    def is_env_option_value(self: Self, value: LoadedOptionValue) -> bool:
        """If the loaded option value supposed to be an env str."""
        return isinstance(value, str) and value.startswith("$__") and value.endswith("__")

    def get_env_option_value(self: Self, value: str) -> str:
        """Return the env key, extracted from the value."""
        return value[3:-2]

    def format_option(self: Self, opt: LoadedOption) -> str:
        """
        The function `include` adds a given patch to the front of a list of patches.

        Parameters
        ----------
        opt : LoadedOption
            The `opt` parameter is a dictionary that represents the key-value pair of options
            of the patch to be included.
        """
        pair: str = opt["key"]
        if value := opt.get("value"):
            pair += f"={self._format_option_value(value)}"
        return pair

    def _configure_patch_args(self: Self, app: APP) -> None:
        """Load per-app patch argument templates before constructing commands."""
        # We copy app-resolved mapping so local mutations never alter APP-level configuration.
        self._patch_args = dict(app.cli_p_args)
        # These templates are reused in multiple methods and must match the current app profile.
        self._options_arg = self._patch_args["OPTIONS"]
        self._enable_arg = self._patch_args["ENABLED"]
        self._disable_arg = self._patch_args["DISABLED"]

    def include(self: Self, patch: PatchInfo, options_list: list[LoadedPatchOption]) -> None:
        """
        The function `include` adds a given patch to the front of a list of patches.

        Parameters
        ----------
        patch : PatchInfo
            The patch dict to be included.
        options_list : list[LoadedPatchOption]
            Then `options_list` parameter is a list of dictionary that represents the options for all patches.
        """
        bundle_id = patch.get("bundle_file")
        if bundle_id is not None and bundle_id not in self._BUNDLE_PATCHES:
            self._BUNDLE_PATCHES[bundle_id] = []

        options_dict = self.fetch_patch_options(patch["name"], options_list)
        options = None
        if options_dict:
            options = options_dict["options"]
        if options:
            for opt in options:
                # This allows to have the loaded options to have key
                # also as the title/name of the option
                patch_option = next(filter(lambda po: opt["key"] in {po["key"], po["name"]}, patch["options"]), None)
                if patch_option:
                    opt["key"] = patch_option["key"]

                    pair = self.format_option(opt)
                    self._PATCHES[:0] = [self._options_arg, pair]
                    if bundle_id is not None:
                        self._BUNDLE_PATCHES[bundle_id][:0] = [self._options_arg, pair]
                else:
                    logger.warning(
                        "Failed to find matching patch option for loaded option key "
                        f"'{opt['key']}' in patch '{patch['name']}'! "
                        "Maybe the option key is not valid for this patch?",
                    )
        self._PATCHES[:0] = [self._enable_arg, patch["name"]]
        if bundle_id is not None:
            self._BUNDLE_PATCHES[bundle_id][:0] = [self._enable_arg, patch["name"]]

    def exclude(self: Self, patch: PatchInfo) -> None:
        """The `exclude` function adds a given patch to the list of excluded patches.

        Parameters
        ----------
        patch : PatchInfo
            The patch dict to be excluded.
        """
        bundle_id = patch.get("bundle_file")
        self._PATCHES.extend([self._disable_arg, patch["name"]])
        if bundle_id is not None:
            self._BUNDLE_PATCHES.setdefault(bundle_id, []).extend([self._disable_arg, patch["name"]])

    def get_excluded_patches(self: Self) -> list[str]:
        """The function `get_excluded_patches` is a getter method that returns a list of excluded patches.

        Returns
        -------
            The method is returning a list of excluded patches.
        """
        return self._EXCLUDED

    def get_all_patches(self: Self) -> list[str | list[str]]:
        """The function "get_all_patches" is a getter method that returns the list of all patches.

        Returns
        -------
            The method is returning a list of all patches in the format
            `["-e"], patch1, ["-e", "--some-flag"], patch2, ["-d"], patch2]`
        """
        return self._PATCHES

    def invert_patch(self: Self, name: str) -> bool:
        """The function `invert_patch` takes a name as input, it toggles the status of the patch.

        Parameters
        ----------
        name : str
            The `name` parameter is a string that represents the name of a patch.

        Returns
        -------
            a boolean value. It returns True if the patch name is found in the list of patches and
        successfully inverted, and False if the patch name is not found in the list.
        """
        try:
            name = name.lower().replace(" ", "-")
            indices = [i for i in range(len(self._PATCHES)) if self._PATCHES[i] == name]
            for patch_index in indices:
                if self._PATCHES[patch_index - 1] == self._enable_arg:
                    self._PATCHES[patch_index - 1] = self._disable_arg
                else:
                    self._PATCHES[patch_index - 1] = self._enable_arg
        except ValueError:
            return False
        else:
            return True

    def enable_exclusive_mode(self: Self) -> None:
        """Enable exclusive mode - only explicitly enabled patches will run, all others disabled by default."""
        logger.info("Enabling exclusive mode for fast testing - only keeping one patch enabled.")
        # Clear all patches and keep only the first one enabled
        if self._PATCHES:
            # Find the first enable argument and its patch name
            for idx in range(0, len(self._PATCHES), 2):
                if idx < len(self._PATCHES) and self._PATCHES[idx] == self._enable_arg and idx + 1 < len(self._PATCHES):
                    first_patch = self._PATCHES[idx + 1]
                    # Clear all patches and set only the first one
                    self._PATCHES = [self._enable_arg, first_patch]
                    # Sync bundle patches: keep only entries for the surviving patch
                    for bundle_id in list(self._BUNDLE_PATCHES):
                        bundle_items = self._BUNDLE_PATCHES[bundle_id]
                        kept: list[str | list[str]] = []
                        for i in range(0, len(bundle_items), 2):
                            if (
                                i + 1 < len(bundle_items)
                                and bundle_items[i] == self._enable_arg
                                and bundle_items[i + 1] == first_patch
                            ):
                                kept = [self._enable_arg, first_patch]
                                break
                        if kept:
                            self._BUNDLE_PATCHES[bundle_id] = kept
                        else:
                            del self._BUNDLE_PATCHES[bundle_id]
                    break

    def fetch_patch_options(self: Self, name: str, options_list: list[LoadedPatchOption]) -> LoadedPatchOption | None:
        """The function `fetch_patch_options` finds patch options for the patch.

        Parameters
        ----------
        name : str
            Then `name` parameter is a string that represents the name of the patch.
        options_list : list[LoadedOption]
            Then `options_list` parameter is a list of dictionary that represents the options for all patches.
        """
        return next(
            filter(lambda obj: obj.get("patchName") == name, options_list),
            None,
        )

    def _load_options_from_ymlstr(self: Self, yaml_content: str) -> list[LoadedPatchOption]:
        """Load options from a YAML string.

        Parameters
        ----------
        yaml_content : str
            The YAML content as a string

        Returns
        -------
        list[LoadedPatchOption]
            List of patch options from the YAML content
        """
        yaml = YAML()
        options_yaml: dict[str, dict[str, Any]] = yaml.load(yaml_content)
        options: list[LoadedPatchOption] = []
        for patch_name, patch_options in options_yaml.items():
            options_list: list[LoadedOption] = []
            for option_key, option_value in patch_options.items():
                options_list.append(LoadedOption(key=option_key, value=option_value))
            if len(options_list) > 0:
                options.append(
                    LoadedPatchOption(
                        patchName=patch_name,
                        options=options_list,
                    ),
                )
        return options

    def _load_options_from_file(self: Self, file_name: str) -> list[LoadedPatchOption]:
        """Load options from a single file.

        Parameters
        ----------
        file_name : str
            The options file name

        Returns
        -------
        list[LoadedPatchOption]
            List of patch options from the file
        """
        try:
            with self.config.temp_folder.joinpath(file_name).open() as file:
                yaml_content = file.read()
                return self._load_options_from_ymlstr(yaml_content)
        except FileNotFoundError as e:
            logger.warning(str(e))
            return []

    def _merge_options(
        self: Self,
        base_options: list[LoadedPatchOption],
        override_options: list[LoadedPatchOption],
    ) -> list[LoadedPatchOption]:
        """Merge base with overridden options.

        App-specific options override global options for the same patch name.

        Parameters
        ----------
        base_options : list[LoadedPatchOption]
            Options from the base options file
        override_options : list[LoadedPatchOption]
            Options from the override options file

        Returns
        -------
        list[LoadedPatchOption]
            Merged options list
        """
        # Create a dict keyed by patchName for easy lookup and merging
        merged: dict[str, LoadedPatchOption] = {}

        # Add base options first
        for opt in base_options:
            patch_name = opt.get("patchName")
            if patch_name:
                merged[patch_name] = opt

        # Override/add with app-specific options
        for opt in override_options:
            patch_name = opt.get("patchName")
            if patch_name:
                merged[patch_name] = opt

        return list(merged.values())

    def _load_patch_options(self: Self, app: APP) -> list[LoadedPatchOption]:
        """Load patch options from file.

        Loads global options first, then merges app-specific options on top.
        App-specific options override global options for the same patch name.

        Parameters
        ----------
        app : APP
            The app instance

        Returns
        -------
        list[LoadedPatchOption]
            List of patch options
        """
        # Load global options first
        global_options = self._load_options_from_file(self.config.global_options_file)

        # If app uses a different options file, load and merge it
        if app.options_file != self.config.global_options_file:
            logger.info(f"Loading app-specific options from {app.options_file} and merging with global options")
            app_options = self._load_options_from_file(app.options_file)
            global_options = self._merge_options(global_options, app_options)

        # If app has raw options defined, load and merge them as well
        if app.options_raw.strip():
            app_options_raw = self._load_options_from_ymlstr(app.options_raw)
            global_options = self._merge_options(global_options, app_options_raw)

        return global_options or []

    _NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")

    def _normalize_patch_name(self: Self, patch_name: str, *, normalize: bool) -> str:
        """Normalize patch name to lowercase dash-separated form.

        Converts any non-alphanumeric sequence to a single dash and strips
        leading/trailing dashes.  E.g. ``Fix /s/ links`` → ``fix-s-links``.

        Parameters
        ----------
        patch_name : str
            The original patch name
        normalize : bool
            Whether to normalize

        Returns
        -------
        str
            Normalized patch name
        """
        if not normalize:
            return patch_name
        name = patch_name.lower()
        name = self._NORMALIZE_PATTERN.sub("-", name)
        return name.strip("-")

    def _get_bundle_index(self: Self, patch: PatchInfo) -> int | None:
        """Resolve the 1-indexed bundle position for a patch's source bundle."""
        bundle_file = patch.get("bundle_file")
        if bundle_file and bundle_file in self._bundle_index_map:
            return self._bundle_index_map[bundle_file]
        return None

    def _matches_exclude(self: Self, entry: str, patch_name: str, bundle_index: int | None) -> bool:
        """Check if an exclude entry applies to a given patch and bundle.

        Delegates to :func:`src._bundle_selector.entry_matches`.
        """
        return _entry_matches_fn(entry, patch_name, bundle_index)

    def _should_include_regular_patch(self: Self, patch: PatchInfo, normalized_name: str, app: APP) -> bool:
        """Determine if a regular patch should be included.

        Parameters
        ----------
        patch : PatchInfo
            The patch dict
        normalized_name : str
            The normalized patch name
        app : APP
            The app instance

        Returns
        -------
        bool
            True if patch should be included
        """
        check_name = normalized_name if app.normalize_patch_names else patch["name"]
        bundle_index = self._get_bundle_index(patch)
        return self._check_exclude_request(app.exclude_request, check_name, bundle_index)

    def _check_exclude_request(
        self: Self,
        exclude_request: list[str],
        check_name: str,
        bundle_index: int | None,
    ) -> bool:
        """Check exclude entries, supporting ``EXCEPT``-prefixed allowlist mode.

        Normal mode (no ``EXCEPT::`` entries): return False if any entry matches.
        Allowlist mode (first entry starts with ``EXCEPT::``): return True only if
        an entry (after stripping the ``EXCEPT::`` prefix) matches.
        """
        # Check if the first entry uses EXCEPT allowlist prefix
        except_prefix = "EXCEPT::"
        has_allowlist = any(e.startswith(except_prefix) for e in exclude_request)

        if has_allowlist:
            return any(
                self._matches_exclude(
                    e.removeprefix(except_prefix),
                    check_name,
                    bundle_index,
                )
                for e in exclude_request
            )

        return not any(self._matches_exclude(e, check_name, bundle_index) for e in exclude_request)

    def _should_include_universal_patch(self: Self, patch: PatchInfo, normalized_name: str, app: APP) -> bool:
        """Determine if a universal patch should be included.

        Parameters
        ----------
        patch : PatchInfo
            The patch dict
        normalized_name : str
            The normalized patch name
        app : APP
            The app instance

        Returns
        -------
        bool
            True if patch should be included
        """
        patch_name = patch["name"]
        bundle_index = self._get_bundle_index(patch)
        check_name = normalized_name if app.normalize_patch_names else patch_name
        include_list = app.include_request
        return check_name in include_list and self._check_exclude_request(
            app.exclude_request,
            check_name,
            bundle_index,
        )

    def _process_regular_patches(
        self: Self,
        patches: list[PatchInfo],
        app: APP,
        options_list: list[LoadedPatchOption],
    ) -> None:
        """Process regular patches for include/exclude.

        Parameters
        ----------
        patches : list[PatchInfo]
            List of regular patches
        app : APP
            The app instance
        options_list : list[LoadedPatchOption]
            List of patch options
        """
        for patch in patches:
            patch_name = patch["name"]
            normalized_name = self._normalize_patch_name(patch_name, normalize=app.normalize_patch_names)

            if self._should_include_regular_patch(patch, normalized_name, app):
                self.include(patch, options_list)
            else:
                self.exclude(patch)

    def _process_universal_patches(
        self: Self,
        universal_patches: list[PatchInfo],
        app: APP,
        options_list: list[LoadedPatchOption],
    ) -> None:
        """Process universal patches for include.

        Parameters
        ----------
        universal_patches : list[PatchInfo]
            List of universal patches
        app : APP
            The app instance
        options_list : list[LoadedPatchOption]
            List of patch options
        """
        for patch in universal_patches:
            patch_name = patch["name"]
            normalized_name = self._normalize_patch_name(patch_name, normalize=app.normalize_patch_names)

            if self._should_include_universal_patch(patch, normalized_name, app):
                self.include(patch, options_list)

    def include_exclude_patch(
        self: Self,
        app: APP,
        patches: list[PatchInfo],
        patches_dict: dict[str, list[PatchInfo]],
    ) -> None:
        """The function `include_exclude_patch` includes and excludes patches for a given app."""
        # We configure patch argument templates before include/exclude so generated flags match current CLI profile.
        self._configure_patch_args(app)
        # Start fresh per-app bundle tracking - repopulated by include()/exclude() during processing below
        self._BUNDLE_PATCHES.clear()
        # Build bundle_file → 1-indexed map for per-bundle exclude matching
        self._bundle_index_map = {}
        for idx, bundle in enumerate(app.patch_bundles):
            self._bundle_index_map[bundle["file_name"]] = idx + 1
        options_list = self._load_patch_options(app)

        self._process_regular_patches(patches, app, options_list)
        self._process_universal_patches(patches_dict["universal_patch"], app, options_list)

    def _build_base_args(self: Self, app: APP) -> list[str]:
        """Build base arguments for ReVanced CLI."""
        # We build absolute paths early so command assembly no longer relies on index-based path rewriting.
        cli_path = str(self.config.temp_folder.joinpath(app.resource["cli"]["file_name"]))
        apk_path = str(self.config.temp_folder.joinpath(app.download_file_name))

        # This starts the CLI invocation with jar launcher and selected patch command keyword.
        args: list[str] = ["-jar", cli_path]
        append_cli_argument(args, self._patch_args["CMD"])
        # APK argument can be positional or flagged depending on configured profile.
        append_cli_argument(args, self._patch_args["APK"], [apk_path])
        return args

    def _add_patch_bundles(self: Self, args: list[str], app: APP) -> None:
        """Add patch bundle arguments to the command."""
        if hasattr(app, "patch_bundles") and app.patch_bundles:
            # Multiple bundles are appended one-by-one and keep profile-specific flag formatting.
            for bundle in app.patch_bundles:
                bundle_path = str(self.config.temp_folder.joinpath(bundle["file_name"]))
                append_cli_argument(args, self._patch_args["PATCHES"], [bundle_path])
                # Some CLI families require a companion flag per patches file group (e.g., v6 `-b` bypass verification).
                append_cli_argument(args, self._patch_args["PATCHES_POST"])
        else:
            # Single bundle fallback stays compatible with older resource metadata.
            bundle_path = str(self.config.temp_folder.joinpath(app.resource["patches"]["file_name"]))
            append_cli_argument(args, self._patch_args["PATCHES"], [bundle_path])
            # Some CLI families require a companion flag per patches file group (e.g., v6 `-b` bypass verification).
            append_cli_argument(args, self._patch_args["PATCHES_POST"])

    def _add_output_and_keystore_args(self: Self, args: list[str], app: APP) -> None:
        """Add output file and keystore arguments."""
        # Output file path is always resolved in the temp directory used by the builder.
        output_path = str(self.config.temp_folder.joinpath(app.get_output_file_name()))
        append_cli_argument(args, self._patch_args["OUTPUT"], [output_path])
        # Keystore path is always resolved in the temp directory used by the builder.
        keystore_path = str(self.config.temp_folder.joinpath(app.keystore_name))
        append_cli_argument(args, self._patch_args["KEYSTORE"], [keystore_path])
        # Force flag keeps current behavior unless user profile explicitly disables it.
        append_cli_argument(args, self._patch_args["FORCE"])

    def _add_keystore_flags(self: Self, args: list[str], app: APP) -> None:
        """Add keystore-specific flags if needed."""
        if app.old_key:
            # https://github.com/ReVanced/revanced-cli/issues/272#issuecomment-1740587534
            append_cli_argument(args, self._patch_args["KEYSTORE_OLD"])

    def _add_architecture_args(self: Self, args: list[str], app: APP) -> None:
        """
        Add architecture-specific arguments.

        Note: Strip only, if the app config has set the `ARCHS_TO_BUILD` != set(possible_archs)
        """
        excluded = set(possible_archs) - set(app.archs_to_build)
        if len(excluded) == 0:
            return

        # Morphe-style striplibs keeps selected architectures instead of excluding architecture-by-architecture.
        if is_arg_enabled(self._patch_args["STRIPLIBS"]):
            append_cli_argument(args, self._patch_args["STRIPLIBS"], [",".join(app.archs_to_build)])
            return

        # Legacy rip-lib behavior is preserved for profiles that expose a compatible argument.
        if is_arg_enabled(self._patch_args["RIP_LIB"]):
            append_cli_argument(args, self._patch_args["RIP_LIB"], list(excluded))

    def _add_temporary_files_args(self: Self, args: list[str], app: APP) -> None:
        """Add an isolated temporary-files directory for CLIs that expose one."""
        # Morphe defaults to a shared temp path, so configured profiles pass a per-app directory for parallel builds.
        append_cli_argument(
            args,
            self._patch_args["TEMPORARY_FILES_PATH"],
            [app.get_cli_temporary_files_path(self.config)],
        )

    def _emit_patches(self: Self, args: list[str], items: list[str | list[str]]) -> None:
        """Append patch entries (enable/disable/option flags + names) to the arg list."""
        for item in items:
            if isinstance(item, list):
                args.extend(item)
            else:
                args.append(item)

    # noinspection IncorrectFormatting
    def patch_app(
        self: Self,
        app: APP,
    ) -> None:
        """The function `patch_app` is used to patch an app using the Revanced CLI tool.

        Parameters
        ----------
        app : APP
            The `app` parameter is an instance of the `APP` class. It represents an application that needs
        to be patched.
        """
        # We refresh app-specific patch argument templates here in case patch_app is used independently.
        self._configure_patch_args(app)
        args = self._build_base_args(app)

        if self.config.ci_test:
            self.enable_exclusive_mode()

        has_multiple_bundles = hasattr(app, "patch_bundles") and len(app.patch_bundles) > 1

        if has_multiple_bundles and self._BUNDLE_PATCHES:
            # Emit interleaved: -p bundle1 -e p1 -e p2 ... -p bundle2 -e p3 -e p4 ...
            # so the Morphe CLI (which scopes -e/-d to the preceding -p) receives correct grouping.
            for bundle in app.patch_bundles:
                bundle_path = str(self.config.temp_folder.joinpath(bundle["file_name"]))
                append_cli_argument(args, self._patch_args["PATCHES"], [bundle_path])
                append_cli_argument(args, self._patch_args["PATCHES_POST"])
                self._emit_patches(args, self._BUNDLE_PATCHES.get(bundle["file_name"], []))
        else:
            # Single bundle or no per-bundle tracking - original behavior
            self._add_patch_bundles(args, app)
            if self._PATCHES:
                self._emit_patches(args, self._PATCHES)

        self._add_output_and_keystore_args(args, app)

        self._add_keystore_flags(args, app)

        self._add_architecture_args(args, app)
        self._add_temporary_files_args(args, app)
        # Purge behavior remains enabled by default and can be remapped per CLI profile.
        append_cli_argument(args, self._patch_args["PURGE"])
        # Continue-on-error is profile-controlled because Morphe supports it but ReVanced may reject unknown flags.
        append_cli_argument(args, self._patch_args["CONTINUE_ON_ERROR"])
        append_cli_argument(args, self._patch_args["BYTECODE_MODE"])

        output_file_path = self.config.temp_folder.joinpath(app.get_output_file_name())
        if output_file_path.exists():
            # Removing the target first prevents a stale APK from masking a failed patch command.
            output_file_path.unlink()

        start = perf_counter()
        logger.debug(f"Sending request to revanced cli for building with args java {args}")
        # stderr is merged into stdout so CLI failures are visible in the existing build log stream.
        process = Popen(["java", *args], stdout=PIPE, stderr=STDOUT)
        output = process.stdout
        if not output:
            msg = "Failed to send request for patching."
            raise PatchingFailedError(msg)
        for line in output:
            logger.debug(line.decode(), flush=True, end="")
        # A non-zero CLI exit means the APK was not patched even if the command produced log output.
        return_code = process.wait()
        if return_code != 0:
            output_was_written = output_file_path.is_file() and output_file_path.stat().st_size > 0
            if self._patch_args["CONTINUE_ON_ERROR"] and output_was_written:
                # Morphe reports skipped patch failures with a non-zero code, but the produced APK is still usable.
                logger.warning(
                    f"ReVanced CLI exited with code {return_code} for {app.app_name}; "
                    f"continuing because {output_file_path.name} was produced.",
                )
                return
            msg = f"ReVanced CLI exited with code {return_code} for {app.app_name}."
            raise PatchingFailedError(msg)
        logger.info(f"Patching completed for app {app} in {perf_counter() - start:.2f} seconds.")
