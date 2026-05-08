#!/usr/bin/env python3

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_ORIGIN = "http://127.0.0.1:8010"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_BRIEF = "做一个 30 秒的城市科技感短片，使用稳定 fixture 素材完成 smoke 验证。"
DEFAULT_FIXTURE_PLAN_MESSAGE = (
    "把方案改成更适合 deterministic fixture smoke 的中文关键词："
    "场景1：城市 黄昏 车流；"
    "场景2：咖啡 特写 手工艺；"
    "场景3：海边 日落 风景；"
    "场景4：雪山 航拍 自然"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ClipForge fixture smoke flow against local services.")
    parser.add_argument("--api-origin", default=DEFAULT_API_ORIGIN)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    return parser


def request_json(method: str, url: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def print_failure(
    kind: str,
    message: str,
    session_payload: dict | None = None,
    task_payload: dict | None = None,
    events: list[dict] | None = None,
) -> int:
    print(f"SMOKE FAILED [{kind}] {message}")
    if session_payload:
        print(
            f"session_status={session_payload.get('status')} "
            f"current_step={session_payload.get('currentStep')}"
        )
    if task_payload:
        print(
            f"task_status={task_payload.get('status')} "
            f"task_step={task_payload.get('currentStep')}"
        )
    if events:
        for item in events[-5:]:
            print(f"- {item.get('eventType')} {item.get('step')} {item.get('message')}")
    return 1


def main() -> int:
    args = build_parser().parse_args()
    api_origin = args.api_origin.rstrip("/")
    deadline = time.time() + args.timeout

    print(f"Starting fixture smoke against {api_origin}")
    print("Checking /api/agent/sessions")
    print(f"Brief: {args.brief}")
    print("SMOKE OK marker reserved for completed smoke runs")

    try:
        created = request_json(
            "POST",
            f"{api_origin}/api/agent/sessions",
            {"message": args.brief},
        )
        session_id = created["id"]
        grounding = created.get("grounding") or {}
        candidates = grounding.get("candidates") or []
        candidate_ids = [candidate.get("id") for candidate in candidates[:2] if candidate.get("id")]
        if not candidate_ids:
            return print_failure("candidate_missing", "session 创建后没有可确认的 grounding candidates", session_payload=created)

        request_json(
            "POST",
            f"{api_origin}/api/agent/sessions/{session_id}/grounding/confirm",
            {"candidateIds": candidate_ids},
        )

        request_json(
            "POST",
            f"{api_origin}/api/agent/sessions/{session_id}/messages",
            {"message": DEFAULT_FIXTURE_PLAN_MESSAGE},
        )

        confirmed = request_json(
            "POST",
            f"{api_origin}/api/agent/sessions/{session_id}/confirm",
        )
        job_id = confirmed.get("activeJobId")
        if not job_id:
            return print_failure("job_missing", "session confirm 后没有 activeJobId", session_payload=confirmed)

        while time.time() < deadline:
            session_payload = request_json("GET", f"{api_origin}/api/agent/sessions/{session_id}")
            events_payload = request_json("GET", f"{api_origin}/api/agent/sessions/{session_id}/events")
            task_payload = request_json("GET", f"{api_origin}/api/agent/tasks/{job_id}")

            status = session_payload.get("status")
            if status == "done":
                video_url = session_payload.get("videoUrl") or task_payload.get("videoUrl")
                if not video_url:
                    return print_failure(
                        "artifact_missing",
                        "session/task 已完成，但没有 videoUrl",
                        session_payload=session_payload,
                        task_payload=task_payload,
                        events=events_payload,
                    )

                output_path = Path("backend/output") / f"{session_id}.mp4"
                if not output_path.exists():
                    return print_failure(
                        "artifact_missing",
                        f"输出文件不存在: {output_path}",
                        session_payload=session_payload,
                        task_payload=task_payload,
                        events=events_payload,
                    )

                print("SMOKE OK")
                print(f"session_id={session_id}")
                print(f"job_id={job_id}")
                print(f"video_url={video_url}")
                print(f"output_path={output_path}")
                return 0

            if status == "failed":
                return print_failure(
                    "session_failed",
                    "session 进入 failed 状态",
                    session_payload=session_payload,
                    task_payload=task_payload,
                    events=events_payload,
                )

            time.sleep(args.poll_interval)

        last_session = request_json("GET", f"{api_origin}/api/agent/sessions/{session_id}")
        last_events = request_json("GET", f"{api_origin}/api/agent/sessions/{session_id}/events")
        last_task = request_json("GET", f"{api_origin}/api/agent/tasks/{job_id}")
        return print_failure(
            "timeout",
            f"超过 {args.timeout} 秒仍未完成",
            session_payload=last_session,
            task_payload=last_task,
            events=last_events,
        )
    except HTTPError as exc:
        return print_failure("api_error", f"HTTPError {exc.code}: {exc.reason}")
    except URLError as exc:
        return print_failure("api_error", f"URLError: {exc.reason}")


if __name__ == "__main__":
    raise SystemExit(main())
