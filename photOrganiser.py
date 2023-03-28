#!/usr/bin/env python3
"""
PhoTools > PhotOrganiser

- Author: Dan Bright, dan@uplandsdynamic.com.
- Licence: GPLv3.
- Description: A script to search all images under 
    a directory (recursively) for those matching given information, 
    and to move all found images into new folders based on the 
    information contained in the tag.
- Documentation: To follow ...

"""

import argparse
import subprocess
import json
import re
import shutil
import uuid
from math import floor
from distutils.util import strtobool
from pathlib import Path
from datetime import datetime

global _verbose_output


class AVAILABLE_META_TYPES:
    IPTC: str = "IPTC"
    ALL: tuple = (IPTC,)


class AVAILABLE_TAG_TYPES:
    KEYWORDS: str = "KEYWORDS"
    ALL: tuple = (KEYWORDS,)


class AVAILABLE_TAG_INFO_SEARCH:
    YEAR: str = "YEAR"
    ALL: tuple = (YEAR,)


class AVAILABLE_FILE_TYPES:
    JPG: str = "JPG"
    JPEG: str = "JPEG"
    TIF: str = "TIF"
    TIFF: str = "TIFF"
    PNG: str = "PNG"
    ALL: tuple = (JPG, JPEG, TIF, TIFF, PNG)


def _v(message: str) -> None:
    global _verbose_output
    print(f"{message}", end="\n\n") if _verbose_output else None
    _write_log(message)


def _get_files(root_dir: Path) -> tuple:
    found_paths = [p for p in root_dir.rglob("*") if p.is_file()]
    valid_paths = []
    excluded_paths = []
    for p in found_paths:
        if p.suffix.upper().strip(".") in AVAILABLE_FILE_TYPES.ALL:
            valid_paths.append(p)
        else:
            excluded_paths.append(p)
    return valid_paths, excluded_paths


def _get_iptc_keywords(file_paths: list[Path]) -> list[dict]:
    results: list = []
    print("Reading tags...")
    for idx, f in enumerate(file_paths):
        tags: list = []
        read = subprocess.run(
            ["exiv2", "-PI", f],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        meta_data = read.stdout.splitlines()
        for item in meta_data:
            item_data = item.split()
            tags.append(" ".join(item_data[3:]))
        results.append({"file_path": f, "tags": tags, "errors": read.stderr})
        _show_progress(idx, len(file_paths))
    print("\nTask complete.", end="\n\n")
    return results


def find_target_tags(files: list, tag_info_search: str) -> list[dict]:
    results: list = []
    if tag_info_search == AVAILABLE_TAG_INFO_SEARCH.YEAR:
        # Extracts YEARS from IPTC KEYWORD tags that include the "DATE" token, e.g.: [DATE: 1984]
        pattern = r"(?i)date.*(\d{4}?)"
        for f in files:
            for tag in f["tags"]:
                match = re.search(pattern, tag, re.IGNORECASE)
                if match:
                    break
            results.append(
                {
                    "file_path": f["file_path"],
                    "toi": match.group(1) if match else None,
                    "errors": "",
                }
            )
    return results


def _move_images(images: list, root_dir: Path, rename_files: bool) -> tuple(list[dict]):
    successful: list[dict] = []
    errors: list[dict] = []
    print("Moving images...")
    for idx, img in enumerate(images):
        try:
            target_dir: Path = (
                root_dir / Path(img["toi"])
                if img["toi"]
                else root_dir / Path("unorganised")
            )
            target_dir.mkdir(parents=True, exist_ok=True)
            try:
                new_path: Path = Path(
                    shutil.move(
                        img["file_path"],
                        target_dir / _gen_filename(img["file_path"].suffix)
                        if rename_files
                        else target_dir,
                    )
                ).resolve()
                successful.append(
                    {"new_filepath": new_path, "old_filepath": img["file_path"]}
                )
            except shutil.Error as e:
                _v("File already exists as this path. Not moving.")
        except Exception as e:
            errors.append({"old_filepath": img["file_path"], "error": str(e)})
        _show_progress(idx, len(images))
    print("\nTask complete.", end="\n\n")
    return successful, errors


def _gen_filename(suffix: str) -> Path:
    return Path(str(uuid.uuid4()) + suffix)


def _show_progress(current: int, total: int) -> None:
    print(
        f"Progress: [{current}/{total}][{floor((current/total)*100)}%]",
        end="\r",
        flush=True,
    )


def _format_json(input: list) -> list[dict]:
    for r in input:
        if "file_path" in r:
            r["file_path"] = str(r["file_path"])
        if "old_filepath" in r:
            r["old_filepath"] = str(r["old_filepath"])
        if "new_filepath" in r:
            r["new_filepath"] = str(r["new_filepath"])
    return json.dumps(input, indent=4, sort_keys=True)


def _write_log(message: str) -> None:
    log_path = Path(".")
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path / "photOrganiser.log", "a+") as file:
        file.seek(0)
        data = file.read(100)
        if len(data) > 0:
            file.write("\n")
        else:
            file.write("# Output log for the fotorganizer script.\n\n")
        file.write(f"\n{dt}   {message}")


def _validate_args(args: list[str | bool]) -> list[str | bool]:
    if args["root_dir"]:
        if type(args["root_dir"]) is not str or args["root_dir"][0] == ".":
            raise ValueError("Invalid root path. Aborting attempt.")
    if args["verbose"]:
        if type(args["verbose"]) is not bool:
            raise ValueError(
                "Verbose requires a True|False argument. Abandoning attempt."
            )
    if args["rename_files"]:
        if type(args["rename_files"]) is not bool:
            raise ValueError(
                "Rename files requires a True|False argument. Abandoning attempt."
            )
    if args["meta_type"]:
        if (
            type(args["meta_type"]) is not str
            or args["meta_type"].upper() not in AVAILABLE_META_TYPES.ALL
        ):
            raise ValueError("Invalid meta type option. Aborting attempt.")
        args["meta_type"] = args["meta_type"].upper()
    if args["tag_type"]:
        if (
            type(args["tag_type"]) is not str
            or args["tag_type"].upper() not in AVAILABLE_TAG_TYPES.ALL
        ):
            raise ValueError("Invalid tag type option. Aborting attempt.")
        args["tag_type"] = args["tag_type"].upper()
    if args["tag_info_search"]:
        if (
            type(args["tag_info_search"]) is not str
            or args["tag_info_search"].upper() not in AVAILABLE_TAG_INFO_SEARCH.ALL
        ):
            raise ValueError("Invalid tag search option. Aborting attempt.")
        args["tag_info_search"] = args["tag_info_search"].upper()
    return args


def _mode_selector(meta_type: str, tag_type: str):
    if (
        meta_type == AVAILABLE_META_TYPES.IPTC
        and tag_type == AVAILABLE_TAG_TYPES.KEYWORDS
    ):
        return _get_iptc_keywords


def execute(
    root_dir: str,
    verbose: bool = False,
    rename_files: bool = False,
    meta_type: str = "IPTC",
    tag_type: str = "KEYWORDS",
    tag_info_search: str = "YEAR",
) -> None:
    global _verbose_output
    newline: str = "\n"
    try:
        cleaned_args = _validate_args(
            {
                "root_dir": root_dir,
                "verbose": verbose,
                "rename_files": rename_files,
                "meta_type": meta_type,
                "tag_type": tag_type,
                "tag_info_search": tag_info_search,
            },
        )
        _verbose_output = verbose
        root_dir = Path(root_dir).resolve(strict=True)
        print("Starting process...", end="\n\n")
        found_paths, excluded_paths = _get_files(root_dir)
        results = _mode_selector(
            meta_type=cleaned_args["meta_type"], tag_type=cleaned_args["tag_type"]
        )(found_paths)
        image_matches = find_target_tags(
            files=results, tag_info_search=cleaned_args["tag_info_search"]
        )
        moved, move_failed = _move_images(image_matches, root_dir, rename_files)

        # print / log stuff
        _v(f"{len(found_paths)} files were found in or under {root_dir}.")
        _v(f"{len(excluded_paths)} files were excluded in or under {root_dir}.")
        _v(
            f"List of found files: {newline}{f'{newline}'.join([str(f) for f in found_paths]) if found_paths else 'None'}"
        )
        _v(
            f"List of excluded files: {newline}{f'{newline}'.join([str(f) for f in excluded_paths]) if excluded_paths else 'None'}"
        )
        _v(f"Tags that were read: \n\n{_format_json(results)}")
        _v(
            f"Tags of interest were detected in these images: \n\n{_format_json(image_matches)}"
        )
        _v(f"Moved files: \n\n{_format_json(moved)}")
        _v(f"Failed moves: \n\n{_format_json(move_failed)}")
    except FileNotFoundError as e:
        print("Root directory was not found. Aborting attempt.")
    except ValueError as e:
        print(str(e))


# driver
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Move all image files with tags-of-interest in their IPTC KEYWORD tags into tag-titled folders."
    )
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        help="Root image directory. Full path required.",
        required=True,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        type=lambda x: bool(strtobool(x)),
        help="Print verbose output.",
        required=False,
        choices=[True, False],
        default=False,
    )
    parser.add_argument(
        "-rf",
        "--rename_files",
        type=lambda x: bool(strtobool(x)),
        help="Rename moved files.",
        required=False,
        choices=[True, False],
        default=False,
    )
    parser.add_argument(
        "-t",
        "--meta_type",
        type=str,
        help="Type of meta data.",
        required=False,
        choices=["IPTC", "iptc"],
        default="IPTC",
    )
    parser.add_argument(
        "-tt",
        "--tag_type",
        type=str,
        help="Type of meta data tag.",
        required=False,
        choices=["KEYWORDS", "keywords"],
        default="KEYWORDS",
    )
    parser.add_argument(
        "-ts",
        "--tag_info_search",
        type=str,
        help="Meta tag information to search for.",
        required=False,
        choices=["YEAR", "year"],
        default="YEAR",
    )
    args = parser.parse_args()
    confirm = input(
        f"Your selected directory was {args.directory}.\nPlease confirm (Y)es, (N)o: "
    )
    execute(
        root_dir=args.directory,
        verbose=args.verbose,
        rename_files=args.rename_files,
        meta_type=args.meta_type,
        tag_type=args.tag_type,
        tag_info_search=args.tag_info_search,
    ) if confirm.lower() in ("yes", "y") else print("Aborting.")
