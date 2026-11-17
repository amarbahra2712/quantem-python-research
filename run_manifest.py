# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 15:07:03 2026

@author: quant
"""

"""
NEXUS Run Manifest
==================

Purpose
-------
Create a permanent, machine-readable record describing exactly
how one NEXUS backtest run was configured.

Responsibilities
----------------
- Generate a unique run identifier.
- Create a dedicated results directory for each run.
- Snapshot all supplied configuration objects.
- Record engine architecture/version metadata.
- Record strategy identity.
- Record historical source-file identity.
- Calculate source-file SHA-256 hashes.
- Write the run manifest as JSON.
- Provide a stable foundation for future run outputs.

Does Not
--------
- Execute trades.
- Generate strategy signals.
- Calculate performance statistics.
- Evaluate prop-firm rules.
- Produce tear sheets.
- Modify NexusEngine.

Architecture
------------
Every NEXUS run receives its own directory:

    10_results/runs/<run_id>/

The manifest is written to:

    manifest.json

Future outputs can be added to the same run directory without
changing the manifest architecture.

Multi-Position Compatibility
----------------------------
The manifest records the engine's position and order models.

The current engine may therefore record:

    position_model = single_position
    order_model = direct_entry

Future versions may record:

    position_model = position_book
    order_model = order_book

Additional future configuration sections such as:

    order_book
    position_book
    basket_management
    portfolio_risk

can be added without changing the core manifest design.
"""


from dataclasses import (
    asdict,
    dataclass,
    is_dataclass,
)

from datetime import (
    date,
    datetime,
    time,
    timezone,
)

from pathlib import Path

import hashlib
import json


# ============================================================
# RUN CONTEXT
# ============================================================

@dataclass(frozen=True)
class RunContext:
    """
    Identity and filesystem locations for one NEXUS run.
    """

    run_id: str

    created_at_utc: datetime

    run_dir: Path

    manifest_path: Path


# ============================================================
# JSON SERIALISATION
# ============================================================

def _to_json_safe(
    value,
):
    """
    Convert common NEXUS configuration values into JSON-safe
    representations.
    """

    if value is None:

        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        return value

    if isinstance(
        value,
        Path,
    ):

        return str(
            value
        )

    if isinstance(
        value,
        (
            datetime,
            date,
            time,
        ),
    ):

        return value.isoformat()

    if is_dataclass(
        value
    ):

        return _to_json_safe(
            asdict(
                value
            )
        )

    if isinstance(
        value,
        dict,
    ):

        return {
            str(key): _to_json_safe(
                item
            )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):

        return [
            _to_json_safe(
                item
            )
            for item in value
        ]

    # --------------------------------------------------------
    # Support NumPy-style scalar values where present.
    # --------------------------------------------------------

    if hasattr(
        value,
        "item",
    ):

        try:

            return _to_json_safe(
                value.item()
            )

        except Exception:

            pass

    # --------------------------------------------------------
    # Last-resort readable representation.
    # --------------------------------------------------------

    return str(
        value
    )


# ============================================================
# FILE HASH
# ============================================================

def _calculate_sha256(
    file_path: Path,
) -> str:
    """
    Calculate SHA-256 hash for one source file.
    """

    sha256 = hashlib.sha256()

    with open(
        file_path,
        mode="rb",
    ) as file_handle:

        while True:

            chunk = file_handle.read(
                1024 * 1024
            )

            if not chunk:

                break

            sha256.update(
                chunk
            )

    return sha256.hexdigest()


# ============================================================
# FILE DESCRIPTION
# ============================================================

def _describe_source_file(
    file_path: Path,
    project_root: Path,
):
    """
    Build a reproducibility descriptor for one input file.
    """

    file_path = (
        Path(
            file_path
        )
        .resolve()
    )

    project_root = (
        Path(
            project_root
        )
        .resolve()
    )

    if not file_path.exists():

        raise FileNotFoundError(
            "Cannot describe missing source file:\n"
            f"{file_path}"
        )

    try:

        relative_path = (
            file_path.relative_to(
                project_root
            )
        )

        stored_path = str(
            relative_path
        )

    except ValueError:

        stored_path = str(
            file_path
        )

    return {
        "path": stored_path,

        "filename": (
            file_path.name
        ),

        "size_bytes": (
            file_path.stat()
            .st_size
        ),

        "sha256": (
            _calculate_sha256(
                file_path
            )
        ),
    }


# ============================================================
# CREATE RUN CONTEXT
# ============================================================

def create_run_context(
    project_root: Path,
) -> RunContext:
    """
    Create the identity and results directory for one NEXUS
    backtest run.
    """

    created_at_utc = (
        datetime.now(
            timezone.utc
        )
    )

    run_id = (
        "run_"
        + created_at_utc.strftime(
            "%Y%m%dT%H%M%S_%fZ"
        )
    )

    run_dir = (
        Path(
            project_root
        )
        / "10_results"
        / "runs"
        / run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    manifest_path = (
        run_dir
        / "manifest.json"
    )

    return RunContext(
        run_id=run_id,

        created_at_utc=(
            created_at_utc
        ),

        run_dir=(
            run_dir
        ),

        manifest_path=(
            manifest_path
        ),
    )


# ============================================================
# WRITE INITIAL MANIFEST
# ============================================================

def write_initial_manifest(
    context: RunContext,
    project_root: Path,
    strategy_name: str,
    engine_metadata: dict,
    config_sections: dict,
    data_files: dict,
) -> Path:
    """
    Write the initial NEXUS run manifest.

    This is deliberately written before the full backtest so
    that configuration provenance survives even if the run
    subsequently fails.
    """

    source_files = {}

    for name, file_path in (
        data_files.items()
    ):

        source_files[
            name
        ] = (
            _describe_source_file(
                file_path=(
                    Path(
                        file_path
                    )
                ),

                project_root=(
                    Path(
                        project_root
                    )
                ),
            )
        )

    manifest = {
        "manifest_schema_version": 1,

        "run": {
            "run_id": (
                context.run_id
            ),

            "status": "STARTED",

            "created_at_utc": (
                context.created_at_utc
                .isoformat()
            ),

            "strategy_name": (
                strategy_name
            ),
        },

        "engine": (
            _to_json_safe(
                engine_metadata
            )
        ),

        "configuration": (
            _to_json_safe(
                config_sections
            )
        ),

        "data_sources": (
            source_files
        ),

        "results": None,
    }

    with open(
        context.manifest_path,
        mode="w",
        encoding="utf-8",
    ) as file_handle:

        json.dump(
            manifest,
            file_handle,
            indent=4,
            sort_keys=False,
        )

    return (
        context.manifest_path
    )

# ============================================================
# FINALISE RUN MANIFEST
# ============================================================

def finalise_run_manifest(
    context: RunContext,
    results_summary: dict,
) -> Path:
    """
    Mark a successfully completed NEXUS run as complete and
    store its key result summary.

    Parameters
    ----------
    context
        RunContext belonging to the current backtest.

    results_summary
        Dictionary containing the important outputs from the
        completed run.

        The function deliberately accepts a generic dictionary
        so future engine architectures can add information such
        as:

            orders_created
            positions_opened
            partial_closes
            baskets_created
            hedged_positions

        without changing the manifest infrastructure.
    """

    completed_at_utc = (
        datetime.now(
            timezone.utc
        )
    )

    # --------------------------------------------------------
    # Load existing manifest.
    # --------------------------------------------------------

    with open(
        context.manifest_path,
        mode="r",
        encoding="utf-8",
    ) as file_handle:

        manifest = json.load(
            file_handle
        )

    # --------------------------------------------------------
    # Update run state.
    # --------------------------------------------------------

    manifest[
        "run"
    ][
        "status"
    ] = "COMPLETED"

    manifest[
        "run"
    ][
        "completed_at_utc"
    ] = (
        completed_at_utc
        .isoformat()
    )

    manifest[
        "run"
    ][
        "duration_seconds"
    ] = (
        completed_at_utc
        - context.created_at_utc
    ).total_seconds()

    # --------------------------------------------------------
    # Store results.
    # --------------------------------------------------------

    manifest[
        "results"
    ] = (
        _to_json_safe(
            results_summary
        )
    )

    # --------------------------------------------------------
    # Write through a temporary file first.
    #
    # This reduces the risk of leaving a corrupted manifest
    # if the process is interrupted during the write.
    # --------------------------------------------------------

    temporary_path = (
        context.manifest_path
        .with_suffix(
            ".json.tmp"
        )
    )

    with open(
        temporary_path,
        mode="w",
        encoding="utf-8",
    ) as file_handle:

        json.dump(
            manifest,
            file_handle,
            indent=4,
            sort_keys=False,
        )

    temporary_path.replace(
        context.manifest_path
    )

    return (
        context.manifest_path
    )