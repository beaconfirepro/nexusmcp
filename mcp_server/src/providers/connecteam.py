"""
Connecteam client — API key authentication.
Auth: X-API-KEY header (not bearer/OAuth).
https://developer.connecteam.com/docs/authentication-1
Base URL: https://api.connecteam.com
Pagination: limit/offset parameters.
"""
import logging

from src.providers.base import BaseProviderClient

logger = logging.getLogger("mcp_server.providers.connecteam")


class ConnecteamClient(BaseProviderClient):
    def __init__(self, api_key: str, base_url: str):
        super().__init__("connecteam", base_url)
        self._api_key = api_key

    def _headers(self) -> dict:
        # https://developer.connecteam.com/docs/authentication-1
        # "Include X-API-KEY: <your_key> in request headers"
        return {"X-API-KEY": self._api_key, "Accept": "application/json"}

    # ── Typed tools ──

    async def get_me(self) -> dict:
        """GET /me — verify API key and get account info."""
        return await self.request("GET", "/me", headers=self._headers())

    async def list_users(self, limit: int = 50, offset: int = 0) -> dict:
        """List users with pagination."""
        return await self.request(
            "GET", "/users",
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )

    async def get_user(self, user_id: str) -> dict:
        return await self.request("GET", f"/users/{user_id}", headers=self._headers())

    async def create_user(self, user_data: dict) -> dict:
        return await self.request("POST", "/users", headers=self._headers(), json_body=user_data)

    async def update_user(self, user_id: str, user_data: dict) -> dict:
        return await self.request("PUT", f"/users/{user_id}", headers=self._headers(), json_body=user_data)

    async def delete_user(self, user_id: str) -> dict:
        return await self.request("DELETE", f"/users/{user_id}", headers=self._headers())

    async def list_shifts(self, limit: int = 50, offset: int = 0) -> dict:
        """List scheduler shifts."""
        return await self.request(
            "GET", "/scheduler/shifts",
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )

    async def create_shift(self, shift_data: dict) -> dict:
        return await self.request("POST", "/scheduler/shifts", headers=self._headers(), json_body=shift_data)

    async def list_time_clock_entries(self, limit: int = 50, offset: int = 0) -> dict:
        """List time clock entries."""
        return await self.request(
            "GET", "/time-clock",
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )

    async def list_jobs(self, params: dict | None = None) -> dict | list:
        # GET /jobs/v1/jobs
        # https://developer.connecteam.com/reference/get_jobs_jobs_v1_jobs_get
        return await self.request("GET", "/jobs/v1/jobs", headers=self._headers(), params=params)

    async def list_job_custom_fields(self, params: dict | None = None) -> dict | list:
        # GET /jobs/v1/custom-fields
        # https://developer.connecteam.com/reference/get_resource_custom_fields_jobs_v1_custom_fields_get
        return await self.request("GET", "/jobs/v1/custom-fields", headers=self._headers(), params=params)

    async def create_jobs(self, jobs: list) -> dict | list:
        # POST /jobs/v1/jobs — body is a top-level array of job objects.
        # https://developer.connecteam.com/reference/create_jobs_jobs_v1_jobs_post
        return await self.request("POST", "/jobs/v1/jobs", headers=self._headers(), json_body=jobs)

    async def update_job(self, job_id: str, job_data: dict) -> dict | list:
        # PUT /jobs/v1/jobs/{jobId} — single object; nested sub-jobs not supported.
        # https://developer.connecteam.com/reference/update_job_jobs_v1_jobs__jobid__put
        return await self.request("PUT", f"/jobs/v1/jobs/{job_id}", headers=self._headers(), json_body=job_data)

    async def list_forms(self, limit: int = 50, offset: int = 0) -> dict:
        return await self.request(
            "GET", "/forms",
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )

    async def list_tasks(self, limit: int = 50, offset: int = 0) -> dict:
        return await self.request(
            "GET", "/tasks",
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )

    # ── Escape-hatch ──

    async def generic_request(
        self, method: str, path: str,
        query: dict | None = None, body: dict | list | None = None,
    ) -> dict | list | str:
        """Call ANY Connecteam endpoint. path should start with /."""
        return await self.request(
            method, path,
            headers=self._headers(),
            params=query,
            json_body=body,
        )