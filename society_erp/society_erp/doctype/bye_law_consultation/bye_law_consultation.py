# Copyright (c) 2026, Society ERP and contributors
# For license information, please see license.txt

from __future__ import annotations

import hashlib
import os

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import get_file_path


class ByeLawConsultation(Document):
    def validate(self):
        if self.final_pdf:
            self.final_pdf_sha256 = self._compute_file_sha256(self.final_pdf)
        else:
            self.final_pdf_sha256 = ""

    @staticmethod
    def _compute_file_sha256(file_url: str) -> str:
        file_path = get_file_path(file_url)
        if not file_path or not os.path.isfile(file_path):
            return ""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
