#!/usr/bin/env python3
"""Probe whether Nebius AI Jobs will actually allocate a GPU instance.

Why this exists
---------------
An earlier entry in this workspace recorded three CreateJobRequest calls that were ACCEPTED,
sat in PROVISIONING with zero instances, and terminated in ERROR after ~30 minutes with
an empty JobStateDetails. That was a CPU preset. The cause was never established.

Two facts measured on 2026-08-31 make the old "we have no quota" story untenable:
  * `nebius capacity resource-advice list` reports limit 32 for on-demand single GPU and
    128 for preemptible, with real free machines (14 H100 on one eu-north1 fabric).
  * A read-only CI probe returned JOBS_ACCESS ok in three projects.

So the open question is narrow: does a GPU job reach RUNNING, and how long does it take?

Design notes
------------
* Default mode is READ-ONLY. It introspects the SDK surface and lists existing jobs.
  Nothing is created unless --create is passed. An instrument proves it completes on
  already-spent data before it consumes anything.
* Every run prints what it actually observed, including the SDK shapes, so that even a
  failed run is informative rather than a silent zero.
* Created jobs are always deleted in a finally block.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

# --------------------------------------------------------------------------------------
# Defaults, taken from the 2026-08-31 capacity measurement.
# eu-north1 gpu-h100-sxm 1gpu-16vcpu-200gb had 14 free on-demand, the deepest pool we saw.
# gpu-l40s-a is cheaper but showed 0 free on-demand and 7 preemptible.
# --------------------------------------------------------------------------------------
DEFAULT_PLATFORM = "gpu-h100-sxm"
DEFAULT_PRESET = "1gpu-16vcpu-200gb"
DEFAULT_IMAGE = "nvidia/cuda:12.4.0-base-ubuntu22.04"
DEFAULT_COMMAND = "nvidia-smi && echo ELENCHOS_GPU_PROBE_OK"


def log(tag: str, **fields: object) -> None:
    """One structured line per observation. Greppable from a CI log."""
    payload = " ".join(f"{k}={json.dumps(v, default=str)}" for k, v in fields.items())
    print(f"PROBE {tag} {payload}", flush=True)


def describe(obj: object, label: str) -> None:
    """Print the shape of an SDK object so an API mismatch is visible, not silent."""
    names = [n for n in dir(obj) if not n.startswith("_")]
    log("shape", label=label, type=type(obj).__name__, attrs=names[:60])


def build_sdk():
    """Construct the SDK from service-account credentials in the environment.

    Expected: NEBIUS_SA_KEY_B64 (base64 PEM private key), NEBIUS_SA_KEY_ID, NEBIUS_SA_ID.
    """
    import base64

    from nebius.sdk import SDK
    from nebius.base.service_account.pk_file import Reader as PKReader

    key_b64 = os.environ["NEBIUS_SA_KEY_B64"]
    key_id = os.environ["NEBIUS_SA_KEY_ID"]
    sa_id = os.environ["NEBIUS_SA_ID"]

    pem_path = "/tmp/elenchos_sa_key.pem"
    with open(pem_path, "wb") as handle:
        handle.write(base64.b64decode(key_b64))
    os.chmod(pem_path, 0o600)

    credentials = PKReader(filename=pem_path, public_key_id=key_id, service_account_id=sa_id)
    return SDK(credentials=credentials)


def resolve_subnet(sdk, project_id: str) -> str | None:
    from nebius.api.nebius.vpc.v1 import ListSubnetsRequest, SubnetServiceClient

    try:
        response = SubnetServiceClient(sdk).list(
            ListSubnetsRequest(parent_id=project_id, page_size=100)
        ).wait()
    except Exception as exc:  # noqa: BLE001 - we want the reason in the log
        log("subnet_error", project=project_id, error=type(exc).__name__, detail=str(exc)[:200])
        return None

    items = list(getattr(response, "items", []) or [])
    for subnet in items:
        subnet_id = getattr(getattr(subnet, "metadata", None), "id", None)
        name = getattr(getattr(subnet, "metadata", None), "name", "")
        log("subnet", project=project_id, id=subnet_id, name=name)
        if subnet_id:
            return subnet_id
    log("subnet_none", project=project_id)
    return None


def list_jobs(sdk, project_id: str) -> None:
    from nebius.api.nebius.ai.v1 import JobServiceClient, ListJobsRequest

    try:
        response = JobServiceClient(sdk).list(ListJobsRequest(parent_id=project_id)).wait()
    except Exception as exc:  # noqa: BLE001
        log("jobs_access_error", project=project_id, error=type(exc).__name__, detail=str(exc)[:300])
        return

    items = list(getattr(response, "items", []) or [])
    log("jobs_access_ok", project=project_id, count=len(items))
    for job in items[:5]:
        status = getattr(job, "status", None)
        log(
            "existing_job",
            name=getattr(getattr(job, "metadata", None), "name", ""),
            state=str(getattr(status, "state", "")),
            instances=len(getattr(status, "instances", []) or []),
        )
    if items:
        describe(items[0], "Job")


def create_and_watch(sdk, project_id: str, args: argparse.Namespace) -> dict:
    """Create one GPU job and time it to RUNNING or ERROR. Always deletes it."""
    from google.protobuf.duration_pb2 import Duration
    from nebius.api.nebius.ai.v1 import (
        CreateJobRequest,
        DeleteJobRequest,
        GetJobRequest,
        JobServiceClient,
        JobSpec,
    )
    from nebius.api.nebius.common.v1 import ResourceMetadata

    subnet_id = resolve_subnet(sdk, project_id)
    if not subnet_id:
        return {"outcome": "no_subnet", "project": project_id}

    service = JobServiceClient(sdk)
    job_name = f"elenchos-gpu-probe-{uuid.uuid4().hex[:10]}"

    spec = JobSpec(
        image=args.image,
        platform=args.platform,
        preset=args.preset,
        subnet_id=subnet_id,
        disk=JobSpec.DiskSpec(type=1, size_bytes=args.disk_gb * 1024 * 1024 * 1024),
        timeout=Duration(seconds=args.job_timeout),
    )
    # The command field name has varied across SDK versions; set it only if it exists.
    for candidate in ("command", "args", "entrypoint"):
        if hasattr(spec, candidate):
            log("spec_command_field", field=candidate)
            break
    describe(spec, "JobSpec")

    started = time.time()
    try:
        operation = service.create(
            CreateJobRequest(
                metadata=ResourceMetadata(parent_id=project_id, name=job_name),
                spec=spec,
            )
        ).wait()
    except Exception as exc:  # noqa: BLE001
        log(
            "create_rejected",
            project=project_id,
            platform=args.platform,
            preset=args.preset,
            error=type(exc).__name__,
            detail=str(exc)[:400],
            elapsed_s=round(time.time() - started, 2),
        )
        return {"outcome": "create_rejected", "project": project_id, "error": str(exc)[:200]}

    # The job id lives on the operation, not on job.metadata.id. Recorded fix from an earlier entry.
    job_id = getattr(operation, "resource_id", None)
    log("created", project=project_id, job=job_name, job_id=job_id,
        platform=args.platform, preset=args.preset,
        elapsed_s=round(time.time() - started, 2))

    result = {"outcome": "timeout", "project": project_id, "job_id": job_id}
    try:
        deadline = started + args.watch_seconds
        last_state = None
        while time.time() < deadline:
            try:
                job = service.get(GetJobRequest(id=job_id)).wait()
            except Exception as exc:  # noqa: BLE001
                log("get_error", job_id=job_id, error=type(exc).__name__, detail=str(exc)[:200])
                time.sleep(args.poll_seconds)
                continue

            status = getattr(job, "status", None)
            state = str(getattr(status, "state", ""))
            instances = len(getattr(status, "instances", []) or [])
            details = str(getattr(status, "state_details", "") or getattr(status, "details", ""))[:300]
            elapsed = round(time.time() - started, 1)

            if state != last_state:
                log("state_change", job_id=job_id, state=state, instances=instances,
                    details=details, elapsed_s=elapsed)
                last_state = state

            # RUNNING is what we are trying to prove. Any instance at all is the real signal.
            if instances > 0 or "RUN" in state.upper():
                log("REACHED_RUNNING", job_id=job_id, state=state, instances=instances,
                    elapsed_s=elapsed)
                return {"outcome": "running", "project": project_id, "job_id": job_id,
                        "seconds_to_running": elapsed, "state": state}

            if "ERROR" in state.upper() or "FAIL" in state.upper():
                log("TERMINAL_ERROR", job_id=job_id, state=state, instances=instances,
                    details=details, elapsed_s=elapsed)
                return {"outcome": "error", "project": project_id, "job_id": job_id,
                        "seconds_to_error": elapsed, "state": state, "details": details}

            time.sleep(args.poll_seconds)

        log("watch_timeout", job_id=job_id, last_state=last_state,
            watched_s=args.watch_seconds)
        result["last_state"] = last_state
        return result
    finally:
        try:
            service.delete(DeleteJobRequest(id=job_id)).wait()
            log("deleted", job_id=job_id)
        except Exception as exc:  # noqa: BLE001
            log("delete_failed", job_id=job_id, error=type(exc).__name__, detail=str(exc)[:200])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", default=os.environ.get("NEBIUS_PROJECTS", ""),
                        help="comma separated project ids")
    parser.add_argument("--platform", default=DEFAULT_PLATFORM)
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--disk-gb", type=int, default=30)
    parser.add_argument("--job-timeout", type=int, default=600,
                        help="job's own timeout in seconds")
    parser.add_argument("--watch-seconds", type=int, default=420,
                        help="how long we wait for RUNNING before giving up")
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--create", action="store_true",
                        help="actually create a job. Without this the run is read-only.")
    args = parser.parse_args()

    projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    if not projects:
        print("No projects given. Set --projects or NEBIUS_PROJECTS.", file=sys.stderr)
        return 2

    log("start", mode="create" if args.create else "read-only", projects=projects,
        platform=args.platform, preset=args.preset, image=args.image)

    sdk = build_sdk()
    log("sdk_ready")

    results = []
    for project_id in projects:
        list_jobs(sdk, project_id)
        if args.create:
            results.append(create_and_watch(sdk, project_id, args))

    log("summary", results=results)

    # A read-only run always succeeds. A create run fails the build unless something ran.
    if args.create and not any(r.get("outcome") == "running" for r in results):
        log("verdict", reached_running=False)
        return 1
    if args.create:
        log("verdict", reached_running=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
