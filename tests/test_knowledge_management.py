import asyncio
import importlib
import inspect
from io import BytesIO
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class KnowledgeModelsContractTests(unittest.TestCase):
    def test_knowledge_source_summary_contract_fields(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        self.assertEqual(
            set(KnowledgeSourceSummary.model_fields.keys()),
            {
                "id",
                "name",
                "status",
                "contentType",
                "createdAt",
                "updatedAt",
                "errorSummary",
                "activeVersion",
                "processingVersion",
                "lastFailedVersion",
                "deletionRequestedAt",
            },
        )

    def test_knowledge_version_summary_contract_fields(self):
        from backend.models.knowledge import KnowledgeVersionSummary

        self.assertEqual(
            set(KnowledgeVersionSummary.model_fields.keys()),
            {
                "id",
                "versionNumber",
                "contentHash",
                "status",
                "createdAt",
                "updatedAt",
                "failedAt",
                "reason",
            },
        )


class KnowledgeRouterContractTests(unittest.TestCase):
    @staticmethod
    def _get_route(path: str, method: str):
        from backend.api.knowledge import router

        for route in router.routes:
            if route.path == path and method in route.methods:
                return route
        raise AssertionError(f"Route not found: {method} {path}")

    def test_knowledge_router_declares_expected_paths(self):
        from backend.api.knowledge import router

        paths = {route.path for route in router.routes}

        self.assertIn("/knowledge-sources/upload", paths)
        self.assertIn("/knowledge-sources/{source_id}", paths)

    def test_backend_main_registers_knowledge_router_under_api_prefix(self):
        module = importlib.import_module("backend.main")
        paths = {route.path for route in module.app.routes}

        self.assertIn("/api/knowledge-sources/upload", paths)
        self.assertIn("/api/knowledge-sources/{source_id}", paths)

    def test_upload_endpoint_declares_upload_file_shape(self):
        from fastapi import UploadFile

        route = self._get_route("/knowledge-sources/upload", "POST")
        parameter = inspect.signature(route.endpoint).parameters["file"]

        self.assertIs(parameter.annotation, UploadFile)
        self.assertEqual(parameter.default.media_type, "multipart/form-data")

    def test_upload_endpoint_raises_not_implemented_for_file_upload_calls(self):
        from fastapi import HTTPException, UploadFile

        route = self._get_route("/knowledge-sources/upload", "POST")
        upload = UploadFile(filename="knowledge.txt", file=BytesIO(b"hello"))

        with self.assertRaises(HTTPException) as context:
            asyncio.run(route.endpoint(file=upload))

        self.assertEqual(context.exception.status_code, 501)

    def test_knowledge_get_endpoint_returns_not_implemented(self):
        from fastapi import HTTPException

        route = self._get_route("/knowledge-sources/{source_id}", "GET")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(route.endpoint(source_id="source-123"))

        self.assertEqual(context.exception.status_code, 501)

    def test_knowledge_delete_endpoint_returns_not_implemented(self):
        from fastapi import HTTPException

        route = self._get_route("/knowledge-sources/{source_id}", "DELETE")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(route.endpoint(source_id="source-123"))

        self.assertEqual(context.exception.status_code, 501)


if __name__ == "__main__":
    unittest.main()
