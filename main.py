"""
MCP server for the HRMS/Webex integration.

This converts the original HRMS helper/API code into an MCP server using
the official Python MCP SDK's FastMCP interface.

Install:
    pip install "mcp[cli]" requests

Run:
    python hrms_mcp_server.py

For Claude Desktop / other MCP clients, configure the command as:
    python /absolute/path/to/hrms_mcp_server.py

The existing project modules `config.py` and (optionally) `utils.files`
are not required by this file. Configuration is read from environment
variables first, with a fallback to the original CONFIG.HRMS structure.

Environment variables:
    HRMS_HR_CODE
    HRMS_API_BASE
    HRMS_DEFAULT_USER_ID
    HRMS_DEFAULT_SIGNED_ARRAY
    HRMS_WEBEX_API_BASE
"""

from __future__ import annotations

import base64
import csv
import sys
import io
import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Union
import requests
from mcp.server.mcpserver import MCPServer


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

try:
    from config import CONFIG  # type: ignore
except ImportError:
    CONFIG = None


def _config_value(env_name: str, config_name: str, default: str = "") -> str:
    value = os.getenv(env_name)
    if value is not None:
        return value

    if CONFIG is not None:
        try:
            value = getattr(CONFIG.HRMS, config_name)
            return "" if value is None else str(value)
        except AttributeError:
            pass

    return default


HR_CODE = _config_value("HRMS_HR_CODE", "HR_CODE")
API_BASE = _config_value("HRMS_API_BASE", "API_BASE")
DEFAULT_USER_ID = _config_value("HRMS_DEFAULT_USER_ID", "DEFAULT_USER_ID")
DEFAULT_SIGNED_ARRAY = _config_value(
    "HRMS_DEFAULT_SIGNED_ARRAY", "DEFAULT_SIGNED_ARRAY"
)
WEBEX_API_BASE = _config_value("HRMS_WEBEX_API_BASE", "WEBEX_API_BASE")
DATE_FMT = "%m/%d/%Y"

REQUEST_TIMEOUT = float(os.getenv("HRMS_REQUEST_TIMEOUT", "10"))
LOG_FILE = os.getenv("HRMS_LOG_FILE", "response.log")




logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("hrms-mcp")


# ---------------------------------------------------------------------------
# MCP application
# ---------------------------------------------------------------------------

mcp = MCPServer(
    "HRMS MCP Server",
    instructions=(
        "HRMS MCP server exposing employee, attendance, project, leave, "
        "holiday, Webex and employee-table operations."
    ),
)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_date(date_str: Optional[str]):
    """Parse an MM/DD/YYYY date string."""
    return datetime.strptime(date_str, DATE_FMT).date() if date_str else None


@lru_cache(maxsize=128)
def resolve_user(query: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Resolve a user query to exactly one user.

    Returns:
        (user_dict, None) on success
        (None, error_dict) on failure
    """
    users = find_user(query)
    if not users:
        return None, {"error": f"No user found matching query: {query}"}

    if len(users) > 1:
        return None, {
            "error": f"Multiple users found for '{query}'. Please be more specific.",
            "matches": [u.get("name") for u in users],
        }

    return users[0], None


def log_response(data: Any, filename: str = LOG_FILE) -> None:
    """Prepend an API response to a local log file."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            old_content = f.read()
    except FileNotFoundError:
        old_content = ""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}]\n")
        f.write(json.dumps(data, indent=2, default=str))
        f.write("\n" + "=" * 50 + "\n")
        f.write(old_content)


def atob(b64: str) -> str:
    """JS-like atob: decode a base64 string into a latin-1 string."""
    raw = base64.b64decode(b64)
    return raw.decode("latin-1")


def btoa(binary_str: str) -> str:
    """JS-like btoa: encode a latin-1 string into base64."""
    if not isinstance(binary_str, str):
        raise TypeError("btoa expects a str")

    raw = binary_str.encode("latin-1")
    return base64.b64encode(raw).decode("ascii")


def encode(data: Dict[str, Any]) -> Dict[str, str]:
    """Encode a dictionary into the API's base64 JSON envelope."""
    return {
        "data": base64.b64encode(
            json.dumps(data).encode("utf-8")
        ).decode("ascii")
    }


def decode(res: Dict[str, Any]) -> Any:
    """Decode the API's base64 JSON response."""
    data = res["res"]
    return json.loads(base64.b64decode(data).decode("utf-8"))


def get_code(data: Dict[str, Any]) -> str:
    string = (
        f'{data["user_id"]}|'
        f'{data["employee_id"]}|'
        f'{data["username"]}|'
        f'{data["user_type"]}'
    )
    return btoa(string)


def post_request(
    endpoint: str,
    payload: Dict[str, Any],
    log: bool = False,
) -> Dict[str, Any]:
    """Generic POST handler with base64 encoding/decoding."""
    if not API_BASE:
        return {"error": "HRMS_API_BASE is not configured"}

    encoded_payload = encode(payload)

    try:
        resp = requests.post(
            f"{API_BASE}{endpoint}",
            json=encoded_payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200:
            data = decode(resp.json())

            if log:
                log_response(data)

            return data

        return {"error": f"HRMS request failed with HTTP {resp.status_code}"}

    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.exception("HRMS request failed: %s", endpoint)
        return {"error": f"Request failed: {str(exc)}"}


def build_user_payload(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the standard HRMS user payload."""
    payload: Dict[str, Any] = {
        "hrcode": HR_CODE,
        "user_id": user_id or DEFAULT_USER_ID,
        "project_status": 1,
        "signed_array": signed_array or DEFAULT_SIGNED_ARRAY,
    }

    if extra_fields:
        payload.update(extra_fields)

    return payload


def fetch_data_from_endpoint(
    endpoint: str,
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    payload = build_user_payload(user_id, signed_array)
    return post_request(endpoint, payload)


# ---------------------------------------------------------------------------
# HRMS operations
# ---------------------------------------------------------------------------

def find_user(query: str, limit: Optional[int] = 5) -> list[Dict[str, Any]]:
    q = str(query).strip().lower()
    users: list[Dict[str, Any]] = []

    endpoint = "/user/get_users"
    payload = build_user_payload()
    data = post_request(endpoint, payload)

    for user in data.get("response_data", []):
        name = str(user.get("name", "")).lower()
        user_id = str(user.get("user_id", "")).lower()
        employee_id = str(user.get("employee_id", "")).lower()
        username = str(user.get("username", "")).lower()

        try:
            user["signed_array"] = get_code(user)
        except (KeyError, TypeError):
            user["signed_array"] = user.get("signed_array", "")

        if (
            q == user_id
            or q == employee_id
            or q in name
            or q in username
        ):
            if limit is not None and len(users) >= limit:
                break

            users.append(user)

    return users


def get_today_log_status(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/attendance/total_logs_detail"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)
    return data.get("response_data", [])


def get_emp_projects(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/project/get_emp_projects"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)
    return data.get("response_data", [])


def get_user_mail_setting(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/setting/get_user_mail_setting"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)
    return data.get("response_data", [])


def get_attendance(
    start_date: str = "",
    end_date: str = "",
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/attendance/show_attendance"
    extra_fields = {
        "start_date": start_date,
        "end_date": end_date,
    }
    payload = build_user_payload(user_id, signed_array, extra_fields)
    data = post_request(endpoint, payload)
    return data.get("response_data", [])


def get_emp_project_log(
    start_date: str = "",
    end_date: str = "",
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    project_id: int = 0,
):
    endpoint = "/project/get_emp_project_log"

    payload = {
        "hrcode": HR_CODE,
        "project_id": project_id,
        "emp_id": user_id or DEFAULT_USER_ID,
        "module_id": 0,
        "activity_id": 0,
        "start_date": start_date,
        "end_date": end_date,
        "groupby": "none",
        "sortby": "ASC",
        "signed_array": signed_array or DEFAULT_SIGNED_ARRAY,
    }

    data = post_request(endpoint, payload)
    if "error" in data:
        return data
    return data.get("response_data", [])


def login(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    override_comment: str = "",
):
    endpoint = "/attendance/fill_attendance"
    extra_fields = {"override_comment": override_comment}

    payload = build_user_payload(user_id, signed_array, extra_fields)
    data = post_request(endpoint, payload)

    result = data.get("response_data", {})
    if not isinstance(result, dict):
        result = {"response_data": result}

    result["message"] = data.get("message", "")
    return result


def logout(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    override_comment: str = "",
):
    endpoint = "/attendance/fill_attendance"
    extra_fields = {"override_comment": override_comment}

    payload = build_user_payload(user_id, signed_array, extra_fields)
    data = post_request(endpoint, payload)

    result = data.get("response_data", {})
    if not isinstance(result, dict):
        result = {"response_data": result}

    result["message"] = data.get("message", "")
    return result


def get_project_modules(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    project_id: Optional[int] = None,
):
    endpoint = "/project/get_modules"
    extra_fields = {"project_id": project_id}

    payload = build_user_payload(user_id, signed_array, extra_fields)
    data = post_request(endpoint, payload)
    return data.get("response_data", {})


def get_project_activities(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    project_id: Optional[int] = None,
):
    endpoint = "/project/get_activities"
    extra_fields = {"project_id": project_id}

    payload = build_user_payload(user_id, signed_array, extra_fields)
    data = post_request(endpoint, payload)
    return data.get("response_data", {})


def generate_csv(
    data: list[Dict[str, Any]],
    user_id: Optional[str] = None,
    chat_id: str = "mcp",
) -> Dict[str, Any]:
    """
    Generate employee CSV data.

    The original implementation uploaded the CSV through Flask's
    FileStorage/save_file. MCP is transport-oriented, so this version
    returns the generated CSV as a UTF-8 string plus metadata. This avoids
    coupling the MCP server to Flask.
    """
    if not data:
        raise ValueError("No employee data found")

    headers = list(data[0].keys())

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(data)

    csv_text = output.getvalue()
    output.close()

    file_id = str(uuid.uuid4())
    filename = f"all_employees_{chat_id}.csv"

    return {
        "file_id": file_id,
        "filename": filename,
        "content_type": "text/csv",
        "user_id": user_id,
        "content": csv_text,
    }


def get_employee_leaves(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    endpoint = "/leavemanager/get_user_leave_record"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)

    leaves = data.get("response_data", [])
    result = []

    start = parse_date(start_date)
    end = parse_date(end_date)

    effective_user_id = user_id or DEFAULT_USER_ID

    for leave in leaves:
        applied_date = parse_date(leave.get("applied_date"))
        e_user_id = leave.get("user_id")

        if effective_user_id and str(e_user_id) != str(effective_user_id):
            continue

        if not applied_date:
            continue

        if start and applied_date < start:
            continue

        if end and applied_date > end:
            continue

        result.append(leave)

    return result


def get_employee_leaves_policy(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/setting/get_policy_setting"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)
    return data.get("response_data", {})


def get_holiday_and_leave_calendar(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    if not start_date or not end_date:
        raise ValueError("start_date and end_date are required")

    endpoint = "/leavemanager/get_holiday_leave_records"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)

    records = data.get("response_data", [])

    start = parse_date(start_date)
    end = parse_date(end_date)

    if start is None or end is None:
        raise ValueError("start_date and end_date must use MM/DD/YYYY")

    holidays = []
    leaves_by_date = defaultdict(list)

    for record in records:
        record_date = parse_date(record.get("date"))

        if not record_date:
            continue

        if record_date < start or record_date > end:
            continue

        name = record.get("name", "")

        if name.startswith("Leave:") or name.startswith("Half Day Leave:"):
            leaves_by_date[record_date.strftime(DATE_FMT)].append(name)
        else:
            holidays.append(
                {
                    "name": name,
                    "date": record_date.strftime(DATE_FMT),
                }
            )

    return {
        "holidays": holidays,
        "leaves": dict(leaves_by_date),
    }


def get_webex_token(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/user/get_user_spark_id"
    payload = build_user_payload(user_id, signed_array)
    data = post_request(endpoint, payload)

    result = data.get("response_data", data)

    if data.get("status") == "Success":
        return {"token": result}

    return {
        "error": data.get("message", "Error in getting the token")
    }


def fill_work_log(
    project_id: int,
    module_id: int,
    activity_id: int,
    work_desc: str,
    hour_clocked: str,
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
):
    endpoint = "/project/fill_daily_log"

    extra_fields = {
        "project_id1": project_id,
        "module_id1": module_id,
        "activity_id1": activity_id,
        "work_desc1": work_desc,
        "hour_clocked1": hour_clocked,
        "work_quantified11": "",
        "work_quantified21": "",
        "log_date1": "",
        "send_mail1": "false",
        "project_id2": 0,
        "module_id2": 0,
        "activity_id2": 0,
        "work_quantified12": "",
        "work_quantified22": "",
        "log_date2": "",
        "send_mail2": "false",
    }

    payload = build_user_payload(user_id, signed_array, extra_fields)
    data = post_request(endpoint, payload)

    result = data.get("response_data", data)

    if data.get("status") == "Success":
        return {"token": result}

    return {
        "error": data.get("message", "Error in filling the work log")
    }


# ---------------------------------------------------------------------------
# Webex
# ---------------------------------------------------------------------------

def get_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def get_employee_image(access_token: str) -> Dict[str, str]:
    if not WEBEX_API_BASE:
        return {"error": "HRMS_WEBEX_API_BASE is not configured"}

    url = f"{WEBEX_API_BASE}/people/me"

    try:
        res = requests.get(
            url,
            headers=get_headers(access_token),
            timeout=REQUEST_TIMEOUT,
        )
        res.raise_for_status()
        data = res.json()
    except (requests.RequestException, ValueError):
        return {"error": "Failed to fetch employee image."}

    return {
        "image_url": data.get(
            "avatar",
            "image is not available.",
        )
    }


# ---------------------------------------------------------------------------
# Employee table
# ---------------------------------------------------------------------------

employees_table_view_config = {
    "table_name": "Synapses All Employees",
    "uri": "/hrms/employees",
    "type": "TABLE_PAGINATED",
    "method": "GET",
    "query_params": {
        "limit": 10,
        "page": 1,
        "search": "",
        "sort_by": "",
        "sort_order": "",
    },
    "sortable_columns": [
        "name",
        "user_id",
        "employee_id",
        "designation",
        "status",
        "joining_date",
    ],
}


def get_employees_table(
    page: int = 1,
    limit: int = 10,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
) -> Dict[str, Any]:
    endpoint = "/user/get_users"
    payload = build_user_payload()
    data = post_request(endpoint, payload)

    cols = [
        {"_k": "user_id", "_v": "ID", "_t": "str"},
        {"_k": "name", "_v": "Name", "_t": "str"},
        {"_k": "username", "_v": "Email", "_t": "str"},
        {"_k": "gender", "_v": "Gender", "_t": "str"},
        {"_k": "status", "_v": "Status", "_t": "str"},
        {"_k": "designation", "_v": "Designation", "_t": "str"},
        {"_k": "employee_id", "_v": "Employee ID", "_t": "str"},
        {"_k": "user_type", "_v": "User Type", "_t": "str"},
        {"_k": "team_lead", "_v": "Team Lead", "_t": "str"},
        {"_k": "createdby", "_v": "Created By", "_t": "str"},
        {"_k": "firm_name", "_v": "Firm Name", "_t": "str"},
        {"_k": "org_name", "_v": "Org Name", "_t": "str"},
        {"_k": "is_org_manager", "_v": "Is Org Manager", "_t": "bool"},
        {"_k": "joining_date", "_v": "Joining Date", "_t": "str"},
        {"_k": "leaving_date", "_v": "Leaving Date", "_t": "str"},
        {
            "_k": "training_completion_date",
            "_v": "Training Completion Date",
            "_t": "str",
        },
        {"_k": "reporting_time", "_v": "Reporting Time", "_t": "str"},
        {"_k": "workinghour", "_v": "Working Hour", "_t": "str"},
        {"_k": "monthly_worklog_hr", "_v": "Monthly Worklog Hour", "_t": "str"},
        {"_k": "comp_off", "_v": "Comp Off", "_t": "str"},
        {"_k": "emergency_leave", "_v": "Emergency Leave", "_t": "str"},
        {"_k": "casual_leave", "_v": "Casual Leave", "_t": "str"},
        {"_k": "extended_leave", "_v": "Extended Leave", "_t": "str"},
        {"_k": "firm_id", "_v": "Firm ID", "_t": "str"},
        {"_k": "org_team_id", "_v": "Org Team ID", "_t": "str"},
        {"_k": "team_lead_id", "_v": "Team Lead ID", "_t": "str"},
        {"_k": "created_date", "_v": "Created Date", "_t": "str"},
    ]

    all_users = data.get("response_data", [])

    if search:
        search_lower = search.lower().strip()
        all_users = [
            user
            for user in all_users
            if search_lower in str(user.get("employee_id", "")).lower()
            or search_lower in str(user.get("user_id", "")).lower()
            or search_lower in str(user.get("name", "")).lower()
            or search_lower in str(user.get("username", "")).lower()
            or search_lower in str(user.get("designation", "")).lower()
            or search_lower in str(user.get("team_lead", "")).lower()
        ]

    if sort_by:
        sort_columns = [
            col.strip() for col in sort_by.split(",") if col.strip()
        ]
        sort_orders = [
            order.strip() for order in sort_order.split(",") if order.strip()
        ]

        while len(sort_orders) < len(sort_columns):
            sort_orders.append("asc")

        sortable_cols = [
            "name",
            "user_id",
            "employee_id",
            "designation",
            "status",
            "joining_date",
        ]

        date_columns = [
            "joining_date",
            "leaving_date",
            "created_date",
            "training_completion_date",
        ]

        valid_sorts = [
            (col, order)
            for col, order in zip(sort_columns, sort_orders)
            if col in sortable_cols
        ]

        try:
            for col, order in reversed(valid_sorts):
                reverse = order.lower() == "desc"

                if col in date_columns:

                    def date_sort_key(x, _col=col, _reverse=reverse):
                        date_str = x.get(_col, "")

                        if not date_str:
                            return (
                                datetime.max
                                if _reverse
                                else datetime.min
                            )

                        try:
                            return datetime.strptime(date_str, DATE_FMT)
                        except (TypeError, ValueError):
                            return (
                                datetime.max
                                if _reverse
                                else datetime.min
                            )

                    all_users.sort(
                        key=date_sort_key,
                        reverse=reverse,
                    )
                else:
                    all_users.sort(
                        key=lambda x, _col=col: (
                            str(x.get(_col, "")).lower()
                            if x.get(_col)
                            else ""
                        ),
                        reverse=reverse,
                    )
        except Exception:
            logger.exception("Employee table sorting failed")

    page = max(1, int(page))
    limit = max(1, int(limit))

    total_count = len(all_users)
    offset = (page - 1) * limit

    users = []

    for user in all_users[offset : offset + limit]:
        user_copy = dict(user)

        for col in cols:
            key = col["_k"]
            user_copy[key] = user_copy.get(key, "")

        users.append(user_copy)

    return {
        "cols": cols,
        "data": users,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
        },
    }


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_employee(
    query: str,
    limit: int = 5,
) -> list[Dict[str, Any]]:
    """
    Search employees by name, user ID, employee ID, username/email,
    and return matching employees.
    """
    return find_user(query, limit=max(1, min(limit, 50)))


@mcp.tool()
def resolve_employee(
    query: str,
) -> Dict[str, Any]:
    """
    Resolve an employee query to exactly one employee.

    If multiple employees match, the response contains the matching names
    and asks for a more specific query.
    """
    user, error = resolve_user(query)

    if error:
        return error

    return {"user": user}


@mcp.tool()
def attendance_status(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get the employee's current/today attendance log status."""
    return get_today_log_status(user_id, signed_array)


@mcp.tool()
def employee_projects(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get projects assigned to an employee."""
    return get_emp_projects(user_id, signed_array)


@mcp.tool()
def user_mail_settings(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get an employee's mail settings."""
    return get_user_mail_setting(user_id, signed_array)


@mcp.tool()
def attendance(
    start_date: str = "",
    end_date: str = "",
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """
    Get attendance records for a date range.

    Dates use MM/DD/YYYY, matching the original HRMS implementation.
    """
    return get_attendance(
        start_date,
        end_date,
        user_id,
        signed_array,
    )


@mcp.tool()
def employee_project_log(
    start_date: str = "",
    end_date: str = "",
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    project_id: int = 0,
) -> Any:
    """Get an employee's project work log for a date range."""
    return get_emp_project_log(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        signed_array=signed_array,
        project_id=project_id,
    )


@mcp.tool()
def check_in(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    override_comment: str = "",
) -> Any:
    """
    Check an employee in using the original HRMS attendance endpoint.
    """
    return login(
        user_id=user_id,
        signed_array=signed_array,
        override_comment=override_comment,
    )


@mcp.tool()
def check_out(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    override_comment: str = "",
) -> Any:
    """
    Check an employee out using the original HRMS attendance endpoint.
    """
    return logout(
        user_id=user_id,
        signed_array=signed_array,
        override_comment=override_comment,
    )


@mcp.tool()
def project_modules(
    project_id: int,
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get modules for a project."""
    return get_project_modules(
        user_id=user_id,
        signed_array=signed_array,
        project_id=project_id,
    )


@mcp.tool()
def project_activities(
    project_id: int,
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get activities for a project."""
    return get_project_activities(
        user_id=user_id,
        signed_array=signed_array,
        project_id=project_id,
    )


@mcp.tool()
def add_work_log(
    project_id: int,
    module_id: int,
    activity_id: int,
    work_desc: str,
    hour_clocked: str,
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """
    Add a daily work log entry to a project.
    """
    return fill_work_log(
        project_id=project_id,
        module_id=module_id,
        activity_id=activity_id,
        work_desc=work_desc,
        hour_clocked=hour_clocked,
        user_id=user_id,
        signed_array=signed_array,
    )


@mcp.tool()
def employee_leaves(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Any:
    """
    Get employee leave records, optionally filtered by applied date.

    Dates use MM/DD/YYYY.
    """
    return get_employee_leaves(
        user_id=user_id,
        signed_array=signed_array,
        start_date=start_date,
        end_date=end_date,
    )


@mcp.tool()
def employee_leave_policy(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get the employee's leave policy/settings."""
    return get_employee_leaves_policy(
        user_id=user_id,
        signed_array=signed_array,
    )


@mcp.tool()
def holiday_leave_calendar(
    start_date: str,
    end_date: str,
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """
    Get holidays and leave entries for a date range.

    Dates use MM/DD/YYYY.
    """
    return get_holiday_and_leave_calendar(
        user_id=user_id,
        signed_array=signed_array,
        start_date=start_date,
        end_date=end_date,
    )


@mcp.tool()
def webex_token(
    user_id: Optional[str] = None,
    signed_array: Optional[str] = None,
) -> Any:
    """Get the Webex token/spark ID through the HRMS endpoint."""
    return get_webex_token(
        user_id=user_id,
        signed_array=signed_array,
    )


@mcp.tool()
def employee_image(
    access_token: str,
) -> Dict[str, str]:
    """Get the current Webex user's employee/avatar image URL."""
    return get_employee_image(access_token)


@mcp.tool()
def employees_table(
    page: int = 1,
    limit: int = 10,
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
) -> Dict[str, Any]:
    """
    Get a paginated, searchable and sortable employee table.

    Supported sort columns:
    name, user_id, employee_id, designation, status, joining_date

    Multiple columns can be comma-separated.
    Example:
        sort_by="status,name"
        sort_order="asc,desc"
    """
    return get_employees_table(
        page=page,
        limit=limit,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@mcp.tool()
def employees_csv(
    search: str = "",
    sort_by: str = "",
    sort_order: str = "asc",
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a CSV representation of all employees matching the optional
    search/sort filters.

    The MCP result contains the CSV text directly because the original
    Flask FileStorage/save_file upload mechanism is not part of MCP.
    """
    table = get_employees_table(
        page=1,
        limit=10**9,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return generate_csv(
        table["data"],
        user_id=user_id,
        chat_id="mcp",
    )


@mcp.tool()
def hrms_config() -> Dict[str, Any]:
    """
    Return non-secret server configuration useful for diagnostics.

    Signed-array values and access tokens are intentionally not returned.
    """
    return {
        "hr_code_configured": bool(HR_CODE),
        "api_base_configured": bool(API_BASE),
        "default_user_id_configured": bool(DEFAULT_USER_ID),
        "default_signed_array_configured": bool(DEFAULT_SIGNED_ARRAY),
        "webex_api_base_configured": bool(WEBEX_API_BASE),
        "request_timeout": REQUEST_TIMEOUT,
        "date_format": DATE_FMT,
        "employee_table": employees_table_view_config,
    }


# ---------------------------------------------------------------------------
# Optional MCP resources
# ---------------------------------------------------------------------------

@mcp.resource("hrms://config")
def config_resource() -> str:
    """Expose non-secret HRMS configuration as an MCP resource."""
    return json.dumps(hrms_config(), indent=2)


@mcp.resource("hrms://employee-table/schema")
def employee_table_schema_resource() -> str:
    """Expose the employee table schema as an MCP resource."""
    return json.dumps(
        employees_table_view_config,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("========================================")
    logger.info("Starting HRMS MCP Server")
    logger.info("Server name: %s", mcp.name)
    logger.info("Transport: streamable-http")
    logger.info("Python: %s", sys.executable)
    logger.info("PID: %s", os.getpid())
    logger.info("Working directory: %s", os.getcwd())
    logger.info("Script: %s", os.path.abspath(__file__))
    logger.info("HRMS API configured: %s", bool(API_BASE))
    logger.info("Webex API configured: %s", bool(WEBEX_API_BASE))
    logger.info("========================================")

    port = int(os.environ.get("PORT", 8000))

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port
    )
